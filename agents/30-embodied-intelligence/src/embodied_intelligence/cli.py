"""Bounded JSON CLI, local regular-file reads and packaged fixture selection.

This boundary never prints user arguments or exception text. Explicit flushing
keeps both argparse help and JSON output inside the closed-pipe handler.
"""

import argparse
from importlib.resources import files
import json
import os
import stat
import sys

from .schema import InvalidRequest, MAX_BYTES, parse_request
from .simulator import run

FIXTURES = ('normal', 'replan', 'emergency', 'obstacle', 'replay', 'tick-limit')


class InvalidArguments(ValueError):
    pass


class InputUnavailable(OSError):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise InvalidArguments


def read_input(path: str) -> bytes:
    """Reject special files and final symlinks before bounded binary reading."""
    descriptor = None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise InputUnavailable
        with os.fdopen(descriptor, 'rb') as stream:
            descriptor = None
            return stream.read(MAX_BYTES + 1)
    except (OSError, ValueError):
        raise InputUnavailable from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _write(report: dict) -> None:
    sys.stdout.write(json.dumps(report, ensure_ascii=True, separators=(',', ':'), allow_nan=False) + '\n')
    sys.stdout.flush()


def _execute(argv: list[str] | None) -> int:
    parser = Parser(prog='embodied-cart', description='Run a synthetic integer cart. No hardware or physical safety claim.',
                    allow_abbrev=False)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--fixture', choices=FIXTURES)
    group.add_argument('--input', metavar='PATH')
    try:
        arguments = parser.parse_args(argv)
        if arguments.input is not None:
            data = read_input(arguments.input)
        else:
            name = arguments.fixture or 'normal'
            data = files('embodied_intelligence').joinpath('fixtures', name + '.json').read_bytes()
        request = parse_request(data)
        report = run(request)
        _write(report)
        return 0 if report['outcome'] in ('complete', 'halted') else 1
    except InvalidArguments:
        _write({'outcome': 'invalid-input', 'error': 'invalid_arguments'})
        return 2
    except InvalidRequest:
        _write({'outcome': 'invalid-input', 'error': 'invalid_request'})
        return 2
    except (InputUnavailable, OSError):
        _write({'outcome': 'invalid-input', 'error': 'input_unavailable'})
        return 2


def main(argv: list[str] | None = None) -> int:
    try:
        try:
            return _execute(argv)
        except SystemExit as result:
            # argparse's successful help exit still needs its buffered bytes flushed.
            sys.stdout.flush()
            return int(result.code or 0)
        except KeyboardInterrupt:
            _write({'outcome': 'cancelled', 'reason': 'interrupted'})
            return 130
    except BrokenPipeError:
        # Avoid a second failing flush during interpreter shutdown in buffered mode.
        sink = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(sink, sys.stdout.fileno())
        finally:
            os.close(sink)
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
