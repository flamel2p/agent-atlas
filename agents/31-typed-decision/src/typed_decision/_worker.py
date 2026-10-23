"""Fixed fixture worker. No library imports, path reads, model, or shell calls.

The host has already checked the size and fixture request binding. The worker
copies the response's JSON lexical representation through Decimal-aware code,
so fixture probabilities do not lose precision. Failure/hang are explicit
synthetic fault modes, selected by fixture configuration rather than state text.
"""

import json
import sys
import time
from decimal import Decimal


def encode(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + encode(v)
                              for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ",".join(encode(v) for v in value) + "]"
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def main():
    fixture = json.loads(sys.stdin.buffer.read(65_537), parse_float=Decimal, parse_int=Decimal)
    if fixture["behavior"] == "fail":
        return 3
    if fixture["behavior"] == "hang":
        time.sleep(60)
    sys.stdout.buffer.write(encode(fixture["response"]).encode("utf-8"))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
