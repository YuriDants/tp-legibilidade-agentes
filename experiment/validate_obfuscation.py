from pathlib import Path
import csv
import json
import runpy
import subprocess
import sys


MANIFEST = Path("experiment/selected_60_final.csv")
ROOT = Path("experiment/dataset_final")


def run_case(case_dir):
    case = Path(case_dir)

    global_file = case / "global.py"
    base_ns = {}

    if global_file.exists():
        base_ns = runpy.run_path(str(global_file))

    ns = runpy.run_path(
        str(case / "bug.py"),
        init_globals=base_ns
    )

    observed = {}

    inputs = sorted((case / "ans").glob("input_*.txt"))

    for inp in inputs:
        expr = inp.read_text().strip()

        try:
            value = eval(expr, ns)

            observed[inp.name] = {
                "kind": "value",
                "value": str(value).strip(),
            }

        except Exception as e:
            observed[inp.name] = {
                "kind": "exception",
                "type": type(e).__name__,
                "message": str(e),
            }

    print(json.dumps(observed, sort_keys=True))


def invoke(case):
    p = subprocess.run(
        [
            sys.executable,
            __file__,
            "--worker",
            str(case),
        ],
        capture_output=True,
        text=True,
        timeout=5,
    )

    if p.returncode != 0:
        return {
            "__runner_error__": (
                p.stderr.strip() or p.stdout.strip()
            )
        }

    return json.loads(p.stdout.strip().splitlines()[-1])


def main():
    rows = list(csv.DictReader(MANIFEST.open()))

    identical = 0
    different = []

    print("=== VALIDATING ORIGINAL vs OBFUSCATED ===")

    for r in rows:
        q = r["question"]
        bug = r["bug_id"]

        original = ROOT / "original" / q / bug
        obfuscated = ROOT / "obfuscated" / q / bug

        try:
            a = invoke(original)
            b = invoke(obfuscated)

            same = a == b

        except subprocess.TimeoutExpired:
            same = False
            a = {"timeout": True}
            b = {"timeout": True}

        if same:
            identical += 1
            status = "IDENTICAL"
        else:
            status = "DIFFERENT"
            different.append((q, bug, a, b))

        print(
            f"{bug:<18} {q:<11} {status}"
        )

    print()
    print("=== SUMMARY ===")
    print(f"Total cases:       {len(rows)}")
    print(f"Identical:         {identical}")
    print(f"Different:         {len(different)}")

    if different:
        print("\n=== DIFFERENCES ===")

        for q, bug, a, b in different:
            print(f"\n{q}/{bug}")
            print("ORIGINAL:")
            print(json.dumps(a, indent=2))
            print("OBFUSCATED:")
            print(json.dumps(b, indent=2))

    if identical == len(rows):
        print()
        print("VALIDATION: PASS")
        print(
            "All obfuscated programs reproduce exactly "
            "the same observable behavior as their originals."
        )
    else:
        print()
        print("VALIDATION: FAIL")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        run_case(sys.argv[2])
    else:
        main()
