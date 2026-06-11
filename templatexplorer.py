#!/usr/bin/env python3
"""Top-level shim: `python templatexplorer.py file.temx` runs the CLI."""
from templatexplorer.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
