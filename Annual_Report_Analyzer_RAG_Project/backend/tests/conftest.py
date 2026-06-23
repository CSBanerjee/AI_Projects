import sys
import os

# ── Add backend/ to path so pytest can find main.py and app/ ─────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))