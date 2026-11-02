"""CLI entrypoint for running `python -m text_frontend`."""

from __future__ import annotations
import sys
from pathlib import Path

# Add project root to path if running module directly
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from try_lines import main

if __name__ == "__main__":
    main()
