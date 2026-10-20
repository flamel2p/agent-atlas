"""Optional image and native-process boundary; recognition remains untrusted.

PNG/JPEG snapshots are validated without transformations. Fixed Tesseract calls
receive bytes through stdin; bounded nonblocking pipes avoid retained scratch and
unbounded communicate() buffers. Every process is reaped, including on interrupts.
This POSIX adapter bounds normal operation; it is not a native-code OS sandbox.
"""

import csv
import hashlib
import io
import os
import re
import selectors
import shutil
import signal
import subprocess
import time
import warnings

from .invoice import Document, InvoiceError, Page
from .source import MAX_TOKENS, page_from_data

MAX_PIXELS = 12_000_000
MAX_STDOUT = 2 * 1024 * 1024
MAX_STDERR = 64 * 1024
PROCESS_SECONDS = 10.0
STAGE_SECONDS = 35.0
HEADER = ("level", "page_num", "block_num", "par_num", "line_num", "word_num", "left", "top", "width", "height", "conf", "text")


def _run(args: list[str], data: bytes, deadline: float, stdout_limit: int = MAX_STDOUT) -> bytes:
    """Drain and cap both streams before allocation; kill/reap on every exit."""
    stop = min(deadline, time.monotonic() + PROCESS_SECONDS)
    if time.monotonic() >= stop:
        raise InvoiceError("ocr_timeout")
    try:
        process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, shell=False, start_new_session=True)
    except OSError:
        raise InvoiceError("ocr_unavailable") from None
    output, errors = bytearray(), bytearray()
    offset = 0
    try:
        with selectors.DefaultSelector() as selector:
            for stream in (process.stdout, process.stderr):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ)
            if data:
                os.set_blocking(process.stdin.fileno(), False)
                selector.register(process.stdin, selectors.EVENT_WRITE)
            else:
                process.stdin.close()
            while selector.get_map():
                remaining = stop - time.monotonic()
                if remaining <= 0:
                    raise InvoiceError("ocr_timeout")
                for key, _ in selector.select(min(remaining, 0.1)):
                    stream = key.fileobj
                    if stream is process.stdin:
                        try:
                            offset += os.write(stream.fileno(), memoryview(data)[offset:offset + 65536])
                        except BrokenPipeError:
                            offset = len(data)
                        if offset == len(data):
                            selector.unregister(stream)
                            stream.close()
                        continue
                    target = output if stream is process.stdout else errors
                    limit = stdout_limit if stream is process.stdout else MAX_STDERR
                    chunk = os.read(stream.fileno(), min(65536, limit - len(target) + 1))
                    if not chunk:
                        selector.unregister(stream)
                        stream.close()
                    elif len(target) + len(chunk) > limit:
                        raise InvoiceError("ocr_output_limit")
                    else:
                        target.extend(chunk)
            try:
                return_code = process.wait(timeout=max(0, stop - time.monotonic()))
            except subprocess.TimeoutExpired:
                raise InvoiceError("ocr_timeout") from None
            if return_code != 0:
                raise InvoiceError("ocr_failed")
            return bytes(output)
    except OSError:
        raise InvoiceError("ocr_failed") from None
    finally:
        # The dedicated process group also prevents descendants retaining pipes
        # after the direct child exits. No timeout/error ever retries recognition.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close()


def _image_size(data: bytes) -> tuple[int, int]:
    try:
        from PIL import Image
    except ImportError:
        raise InvoiceError("pillow_unavailable") from None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data), formats=("PNG", "JPEG")) as image:
                width, height = image.size
                if width * height > MAX_PIXELS:
                    raise InvoiceError("pixel_limit")
                if getattr(image, "n_frames", 1) != 1:
                    raise InvoiceError("multiframe_image")
                image.verify()
            with Image.open(io.BytesIO(data), formats=("PNG", "JPEG")) as image:
                # PNG EXIF access can consume the stream. Verify the first open
                # before touching EXIF, then inspect/decode the same byte snapshot.
                if image.getexif().get(274, 1) != 1:
                    raise InvoiceError("image_orientation")
                image.load()
                return width, height
    except InvoiceError:
        raise
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise InvoiceError("invalid_image") from None


def _parse_tsv(data: bytes, number: int, size: tuple[int, int]) -> Page:
    """Keep every nonblank word row, including missing (-1) or weak scores."""
    try:
        text = data.decode("utf-8")
        rows = csv.reader(io.StringIO(text), delimiter="\t", quoting=csv.QUOTE_NONE)
        if next(rows, None) != list(HEADER):
            raise InvoiceError("invalid_ocr_output")
        tokens = []
        for index, row in enumerate(rows, 1):
            if len(row) != len(HEADER):
                raise InvoiceError("invalid_ocr_output")
            values = [int(value) for value in row[:10]]
            level, page, block, paragraph, line, word, left, top, width, height = values
            score = float(row[10])
            if level not in range(1, 6) or page != 1 or any(value < 0 for value in values[2:]):
                raise InvoiceError("invalid_ocr_output")
            if left + width > size[0] or top + height > size[1]:
                raise InvoiceError("invalid_ocr_output")
            if level != 5:
                if row[11].strip() or score != -1:
                    raise InvoiceError("invalid_ocr_output")
                continue
            if not row[11].strip():
                if score != -1:
                    raise InvoiceError("invalid_ocr_output")
                continue
            if word < 1:
                raise InvoiceError("invalid_ocr_output")
            tokens.append({"id": f"w{index}", "text": row[11], "line_key": [block, paragraph, line],
                           "bbox": [left, top, left + width, top + height],
                           "ocr_score": None if score == -1 else score})
            if len(tokens) > MAX_TOKENS:
                raise InvoiceError("token_limit")
        return page_from_data({"number": number, "width": size[0], "height": size[1], "tokens": tokens}, number)
    except (ValueError, UnicodeError, csv.Error, OverflowError):
        raise InvoiceError("invalid_ocr_output") from None


def image_document(snapshots: tuple[bytes, ...]) -> Document:
    """Charge decoding time to the stage deadline; bound every process call.

    Native Pillow decoding is synchronous and cannot be preempted by this clock.
    Expiry prevents the next process call or report; it is not decoder isolation.
    """
    deadline = time.monotonic() + STAGE_SECONDS
    sizes = tuple(_image_size(data) for data in snapshots)
    executable = shutil.which("tesseract")
    if executable is None:
        raise InvoiceError("ocr_unavailable")
    version = _run([executable, "--version"], b"", deadline, MAX_STDERR)
    match = re.match(rb"tesseract ([0-9]+(?:\.[0-9]+){1,3})(?:\s|$)", version)
    if not match:
        raise InvoiceError("invalid_ocr_version")
    languages = _run([executable, "--list-langs"], b"", deadline, MAX_STDERR)
    if b"eng" not in languages.splitlines():
        raise InvoiceError("ocr_language_unavailable")
    pages = []
    count = 0
    for number, (data, size) in enumerate(zip(snapshots, sizes), 1):
        tsv = _run([executable, "stdin", "stdout", "-l", "eng", "--psm", "6", "tsv"], data, deadline)
        page = _parse_tsv(tsv, number, size)
        pages.append(page)
        count += len(page.tokens)
        if count > MAX_TOKENS:
            raise InvoiceError("token_limit")
        if time.monotonic() >= deadline:
            raise InvoiceError("ocr_timeout")
    return Document("local_ocr", tuple(hashlib.sha256(data).hexdigest() for data in snapshots),
                    tuple(pages), "tesseract " + match[1].decode("ascii"))
