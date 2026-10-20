"""One source selection, one extraction call, one JSON result and exit status.

Diagnostics expose stable failure codes only. Successful evidence intentionally
contains supplied invoice text; callers choose whether to persist stdout.
"""

import argparse
import json
from pathlib import Path

from .invoice import InvoiceError
from .source import EXAMPLES, Example, ImagePages, TokenFile, extract_invoice


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise InvoiceError("invalid_arguments")


def main(argv: list[str] | None = None) -> int:
    try:
        parser = _Parser(description="Extract a synthetic invoice or inspect local OCR evidence.")
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument("--example", choices=EXAMPLES)
        mode.add_argument("--tokens", type=Path)
        mode.add_argument("--images", nargs="+", type=Path)
        args = parser.parse_args(argv)
        source = Example(args.example) if args.example else TokenFile(args.tokens) if args.tokens else ImagePages(tuple(args.images))
        report = extract_invoice(source)
        result, code = report.to_dict(), 0 if report.status == "extracted" else 2
    except KeyboardInterrupt:
        result, code = {"status": "cancelled", "error": {"code": "cancelled"}}, 130
    except InvoiceError as error:
        result, code = {"status": "error", "error": {"code": error.code}}, 1
    except Exception:
        result, code = {"status": "error", "error": {"code": "processing_error"}}, 1
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False))
    return code
