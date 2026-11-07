from pathlib import Path
import runpy
import sys

root = Path(__file__).parent

base_ns = {}
global_file = root / "global.py"
if global_file.exists():
    base_ns = runpy.run_path(str(global_file))

ns = runpy.run_path(str(root / "bug.py"), init_globals=base_ns)

inputs = sorted((root / "ans").glob("input_*.txt"))
outputs = sorted((root / "ans").glob("output_*.txt"))

passed = 0
failed = 0

for inp, out in zip(inputs, outputs):
    expr = inp.read_text().strip()
    expected = out.read_text().strip()

    try:
        got = str(eval(expr, ns)).strip()
        ok = got == expected
    except Exception as e:
        got = f"{type(e).__name__}: {e}"
        ok = False

    if ok:
        passed += 1
    else:
        failed += 1
        print(
            f"FAIL {inp.name}: got={got!r} expected={expected!r}"
        )

print(f"RESULT: {passed}/{len(inputs)} passed; {failed} failed")
sys.exit(0 if failed == 0 else 1)
