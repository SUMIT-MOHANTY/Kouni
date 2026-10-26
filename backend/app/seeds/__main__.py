"""
CLI Entry Point for Database Seeds.

This module allows running seeds via:
    python -m app.seeds

It delegates to the main seed runner in __init__.py
"""

import sys
from app.seeds import main

if __name__ == "__main__":
    sys.exit(main())
