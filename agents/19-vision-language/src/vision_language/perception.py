"""Own bounded local image reads and exact rectangular-diagram perception.

A component is a maximal four-neighbor region of one exact RGB color. A scan
labels at most 64 nonwhite components, then measures each component's area and
exclusive bounding box. Only solid interior rectangles in the three supported
colors become object observations. Any unsupported pixels, clipping, fragments,
contact, or gray occlusion block exact answers globally.

The file descriptor rejects a symlink in the final path component and special
files before reads. Ancestor directories resolve normally. This is a bounded
user-selected read, not a filesystem sandbox or a hard execution timeout.
"""

from dataclasses import replace
import hashlib
import io
import os
from pathlib import Path
import stat
import warnings
import zlib

from PIL import Image, UnidentifiedImageError

from .domain import Bounds, Color, ImageProvenance, InputFailure, Observation, Scene

MAX_BYTES = 1024 * 1024
MIN_DIMENSION = 8
MAX_DIMENSION = 256
MAX_PIXELS = MAX_DIMENSION * MAX_DIMENSION
MAX_COMPONENTS = 64
WHITE = (255, 255, 255)
GRAY = (128, 128, 128)
COLORS: dict[tuple[int, int, int], Color] = {
    (255, 0, 0): "red",
    (0, 180, 0): "green",
    (0, 0, 255): "blue",
}


def _read_image(path: str | Path) -> bytes:
    fd = None
    try:
        # NONBLOCK prevents a FIFO from blocking before fstat rejects it.
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise InputFailure("not_regular_file")
        if info.st_size > MAX_BYTES:
            raise InputFailure("image_byte_limit")
        chunks = []
        remaining = MAX_BYTES
        while remaining:
            chunk = os.read(fd, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        # Check growth without reading a forbidden byte beyond the ceiling.
        if os.fstat(fd).st_size > MAX_BYTES:
            raise InputFailure("image_byte_limit")
        return b"".join(chunks)
    except (OSError, ValueError, TypeError) as error:
        raise InputFailure("image_unreadable") from error
    finally:
        if fd is not None:
            os.close(fd)


def _verify_png_chunks(data: bytes, provenance: ImageProvenance) -> None:
    """Check framing, critical chunk order, and every CRC including IEND.

    This is not a pixel decoder. Pillow owns format semantics and decompression;
    this gate closes its acceptance of a missing or damaged final chunk CRC.
    """

    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise InputFailure("invalid_png", provenance)
    offset = 8
    view = memoryview(data)
    seen_idat = False
    ended_idat = False
    seen_plte = False
    while offset + 12 <= len(data):
        length = int.from_bytes(data[offset:offset + 4], "big")
        chunk_type = data[offset + 4:offset + 8]
        end = offset + 12 + length
        if end > len(data):
            break
        expected_crc = int.from_bytes(data[end - 4:end], "big")
        if zlib.crc32(view[offset + 4:end - 4]) & 0xFFFFFFFF != expected_crc:
            break
        if not all(65 <= char <= 90 or 97 <= char <= 122 for char in chunk_type) or not 65 <= chunk_type[2] <= 90:
            break
        if offset == 8:
            if chunk_type != b"IHDR" or length != 13:
                break
        elif chunk_type == b"IHDR":
            break
        # PNG uppercase first letters mark critical chunks. Unknown critical
        # content cannot be ignored while claiming to understand the image.
        if not chunk_type[0] & 0x20 and chunk_type not in (b"IHDR", b"PLTE", b"IDAT", b"IEND"):
            break
        if chunk_type == b"PLTE":
            if seen_plte or seen_idat or not 0 < length <= 768 or length % 3:
                break
            seen_plte = True
        if chunk_type == b"IDAT":
            if ended_idat:
                break
            seen_idat = True
        elif seen_idat:
            ended_idat = True
        if chunk_type == b"IEND":
            if seen_idat and length == 0 and end == len(data):
                return
            break
        offset = end
    raise InputFailure("invalid_png", provenance)


def _decode(data: bytes) -> tuple[Image.Image, ImageProvenance]:
    provenance = ImageProvenance(hashlib.sha256(data).hexdigest(), len(data))
    _verify_png_chunks(data, provenance)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data), formats=["PNG"]) as candidate:
                width, height = candidate.size
                provenance = replace(provenance, width=width, height=height, format=candidate.format, mode=candidate.mode)
                if not (MIN_DIMENSION <= width <= MAX_DIMENSION and MIN_DIMENSION <= height <= MAX_DIMENSION):
                    raise InputFailure("image_dimension_limit", provenance)
                if width * height > MAX_PIXELS:
                    raise InputFailure("image_pixel_limit", provenance)
                # Pillow reduces 16-bit truecolor to RGB8. Reject that conversion
                # rather than silently treating nearby sample values as exact.
                if candidate.mode != "RGB" or data[24] != 8 or "transparency" in candidate.info:
                    raise InputFailure("unsupported_image_mode", provenance)
                if candidate.n_frames != 1 or candidate.is_animated:
                    raise InputFailure("animated_image", provenance)
                # verify checks PNG chunks before any pixel materialization.
                candidate.verify()
            with Image.open(io.BytesIO(data), formats=["PNG"]) as candidate:
                candidate.load()
                return candidate.copy(), provenance
    except InputFailure:
        raise
    except (OSError, ValueError, SyntaxError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise InputFailure("invalid_png", provenance) from error


def inspect_image(path: str | Path) -> Scene:
    """Read once, decode verified bytes, then return immutable pixel evidence."""

    image, provenance = _decode(_read_image(path))
    try:
        width, height = image.size
        pixels = image.get_flattened_data()
    finally:
        image.close()
    labels = [-1] * len(pixels)
    components: list[tuple[tuple[int, int, int], Bounds, int]] = []
    issues: set[str] = set()

    for index, color in enumerate(pixels):
        if color == WHITE or labels[index] >= 0:
            continue
        if len(components) >= MAX_COMPONENTS:
            issues.add("component_limit")
            break
        label = len(components)
        labels[index] = label
        pending = [index]
        left = right = index % width
        top = bottom = index // width
        area = 0
        while pending:
            current = pending.pop()
            x, y = current % width, current // width
            left, right = min(left, x), max(right, x)
            top, bottom = min(top, y), max(bottom, y)
            area += 1
            neighbors = []
            if x:
                neighbors.append(current - 1)
            if x + 1 < width:
                neighbors.append(current + 1)
            if y:
                neighbors.append(current - width)
            if y + 1 < height:
                neighbors.append(current + width)
            for neighbor in neighbors:
                if labels[neighbor] < 0 and pixels[neighbor] == color:
                    labels[neighbor] = label
                    pending.append(neighbor)
        components.append((color, (left, top, right + 1, bottom + 1), area))

    rectangles: list[tuple[Color, Bounds, int]] = []
    for color, bounds, area in components:
        if color == GRAY:
            issues.add("gray_occluder")
            continue
        if color not in COLORS:
            issues.add("unknown_color")
            continue
        left, top, right, bottom = bounds
        complete = True
        if left == 0 or top == 0 or right == width or bottom == height:
            issues.add("boundary_clipping")
            complete = False
        if right - left < 3 or bottom - top < 3:
            issues.add("thin_region")
            complete = False
        if area != (right - left) * (bottom - top):
            issues.add("nonrectangular_region")
            complete = False
        if complete:
            rectangles.append((COLORS[color], bounds, area))

    # Eight-neighbor contact catches diagonal object contact that four-neighbor
    # segmentation intentionally keeps separate. A full merged same-color
    # rectangle is observationally one rectangle; pixels expose no internal seam.
    for index, label in enumerate(labels):
        if label < 0 or pixels[index] not in COLORS:
            continue
        x, y = index % width, index // width
        for dx, dy in ((1, 0), (-1, 1), (0, 1), (1, 1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height:
                neighbor = ny * width + nx
                if labels[neighbor] >= 0 and labels[neighbor] != label and pixels[neighbor] in COLORS:
                    issues.add("object_contact")

    rectangles.sort(key=lambda item: (item[1][1], item[1][0], item[1][3], item[1][2], item[0]))
    observations = tuple(Observation(f"object-{number}", color, bounds, area) for number, (color, bounds, area) in enumerate(rectangles, 1))
    return Scene(provenance, observations, tuple(sorted(issues)))
