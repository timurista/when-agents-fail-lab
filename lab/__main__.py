"""The lab runner.

  python3 -m lab list                 every exercise and its status
  python3 -m lab check 03             run exercise 3's checks on your code
  python3 -m lab check 03 --solution  run them on the reference answer
  python3 -m lab check all --solution what CI runs
  python3 -m lab reveal 03            print the answer, after one attempt

The answer stays hidden until you have run `check` on your own code at
least once. Predict, then test, then look: the order is the lesson.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ATTEMPTS = ROOT / ".lab-attempts.json"


def exercises():
    return sorted(p for p in (ROOT / "exercises").iterdir()
                  if p.is_dir() and p.name[:2] == "ex")


def find(num: str) -> Path:
    # "4", "04" -> ex04_...; "4b", "04b" -> ex04b_...
    digits = num.rstrip("abcdefghijklmnopqrstuvwxyz")
    if not digits.isdigit():
        sys.exit(f"no exercise {num}; try: python3 -m lab list")
    prefix = f"ex{int(digits):02d}{num[len(digits):]}_"
    for p in exercises():
        if p.name.startswith(prefix):
            return p
    sys.exit(f"no exercise {num}; try: python3 -m lab list")


def attempts() -> dict:
    return json.loads(ATTEMPTS.read_text()) if ATTEMPTS.exists() else {}


def run(path: Path, solution: bool) -> bool:
    env = dict(os.environ, LAB_TARGET="solution" if solution else "starter",
               PYTHONPATH=str(ROOT))
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", str(path),
         "-p", "test_*.py"],
        env=env, cwd=ROOT)
    return result.returncode == 0


def main(argv):
    if not argv or argv[0] == "list":
        done = attempts()
        for p in exercises():
            mark = "attempted" if p.name in done else ""
            print(f"  {p.name:<40} {mark}")
        return 0
    cmd, *rest = argv
    solution = "--solution" in rest
    if cmd in {"check", "reveal"} and not [a for a in rest
                                            if a != "--solution"]:
        print(f"usage: python3 -m lab {cmd} NN | all")
        return 2
    if cmd == "check":
        targets = exercises() if rest[0] == "all" else [find(rest[0])]
        ok = True
        for p in targets:
            print(f"== {p.name} ({'solution' if solution else 'yours'})", flush=True)
            passed = run(p, solution)
            ok = ok and passed
            if not solution:
                done = attempts()
                done[p.name] = done.get(p.name, 0) + 1
                ATTEMPTS.write_text(json.dumps(done, indent=2))
        return 0 if ok else 1
    if cmd == "reveal":
        p = find(rest[0])
        if p.name not in attempts():
            print("Run `python3 -m lab check "
                  f"{rest[0]}` on your own code first.")
            return 1
        answer = ROOT / "answers" / p.name
        for f in sorted(answer.iterdir()):
            if f.suffix in {".py", ".md"}:
                print(f"--- {f.relative_to(ROOT)}\n{f.read_text()}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
