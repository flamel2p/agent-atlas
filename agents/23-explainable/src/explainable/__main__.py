"""Run the same read-only JSON CLI exposed by the installed console script."""

from .cli import main

raise SystemExit(main())
