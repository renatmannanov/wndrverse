import os
import sys

# Repo root on sys.path so tests import core.* / bot.* without per-file sys.path hacks.
sys.path.insert(0, os.path.dirname(__file__))
