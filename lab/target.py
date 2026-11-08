"""Lets one test file check either your code or the reference answer.

LAB_TARGET=starter (the default) loads exercises/<name>/starter.py.
LAB_TARGET=solution loads answers/<name>/solution.py.
"""
import importlib.util
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(exercise: str):
    which = os.environ.get("LAB_TARGET", "starter")
    if which == "solution":
        path = ROOT / "answers" / exercise / "solution.py"
    else:
        path = ROOT / "exercises" / exercise / "starter.py"
    spec = importlib.util.spec_from_file_location(
        f"{exercise}_{which}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture(exercise: str, name: str) -> Path:
    return ROOT / "exercises" / exercise / "fixtures" / name
