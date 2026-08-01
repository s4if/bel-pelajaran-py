"""Thin launcher.

* Dev:   ``python run.py start configs/konfig.toml``  (or use ``bel`` after install)
* Exe:   this file is the PyInstaller entrypoint (see README → Packaging)

Keeping it at the project root means relative imports resolve whether the app is
run from source or frozen.
"""

import sys

from app.cli import main

if __name__ == "__main__":
    sys.exit(main())
