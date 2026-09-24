"""Friendly interpreter guard for the demo/diagnostic entry scripts.

The teardown imports chain (``services`` -> ``orchestrator`` -> PyYAML) require
``yaml`` at import time. Because these scripts are run interactively from
arbitrary shells, whoever launches them should get a clear message pointing at
the environment that works, instead of a bare ``ModuleNotFoundError``.
"""

import os
import sys


def guard_dependencies(*modules: str) -> None:
    """Exit with a readable hint if any hard dependency is not importable.

    Uses ``importlib.util.find_spec`` so the heavy/torch-y stack is not
    imported just to be probed.
    """
    import importlib.util

    missing = [name for name in modules if not importlib.util.find_spec(name)]
    if not missing:
        return

    known_good = r"C:\Users\cecilia\anaconda3\python.exe"
    print("=" * 74, file=sys.stderr)
    print(f"Missing Python modules: {', '.join(missing)}", file=sys.stderr)
    print(f"You are running: {sys.executable}", file=sys.stderr)
    if os.path.exists(known_good):
        print(f"Use the known-good interpreter:\n    {known_good} {os.path.basename(sys.argv[0])}", file=sys.stderr)
    print("Inside that environment, ensure deps are installed, e.g.:", file=sys.stderr)
    print("    pip install pyyaml paddleocr paddlepaddle playwright fast_flights openrouter", file=sys.stderr)
    print("=" * 74, file=sys.stderr)
    sys.exit(1)
