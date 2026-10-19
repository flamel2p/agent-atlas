"""Route ``python -m planning_agent`` through the same CLI and exit-code contract."""

from .cli import main

raise SystemExit(main())
