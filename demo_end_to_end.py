#!/usr/bin/env python3
"""Compatibility wrapper for the demo entry moved to examples/."""
from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).parent / "examples" / "demo_end_to_end.py"), run_name="__main__")
