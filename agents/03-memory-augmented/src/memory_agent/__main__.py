"""Expose the same CLI through ``python -m memory_agent``."""

from .cli import main

raise SystemExit(main())
