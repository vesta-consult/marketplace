"""Gemeinsame Test-Einstellungen: Plugin-Skripte importierbar machen."""
from __future__ import annotations

import sys
from pathlib import Path

SKRIPTE = Path(__file__).resolve().parent.parent / "scripts"
if str(SKRIPTE) not in sys.path:
    sys.path.insert(0, str(SKRIPTE))
