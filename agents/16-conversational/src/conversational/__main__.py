"""Module execution uses the same bounded CLI boundary as the installed command."""

from .cli import main

raise SystemExit(main())
