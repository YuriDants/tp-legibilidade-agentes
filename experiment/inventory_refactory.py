from pathlib import Path
import ast
import csv
import json
import runpy
import subprocess
import sys


def worker(question_dir, code_file):
    q = Path(question_dir)
    code = Path(code_file)

    inputs = sorted((q / "ans").glob("input_*.txt"))
    outputs = sorted((q / "ans").glob("output_*.txt"))

    result = {
        "total_tests": len(inputs),
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "failed_tests": [],
        "error_tests": [],
    }

    try:
        # O Refactory permite um global.py por exercício com imports,
        # funções e variáveis globais usadas pelos casos de teste.
        global_file = q / "code" / "global.py"
        base_ns = {}

        if global_file.exists():
            base_ns = runpy.run_path(str(global_file))

        ns = runpy.run_path(str(code), init_globals=base_ns)

    except Exception as e:
        result["errors"] = len(inputs)
        result["error_tests"] = [f"LOAD:{type(e).__name__}:{e}"]
        print(json.dumps(result))
        return

    for inp, out in zip(inputs, outputs):
        expr = inp.read_text().strip()
        expected = out.read_text().strip()

        try:
            got = eval(expr, ns)
            got_text = str(got).strip()

            if got_text == expected:
                result["passed"] += 1
            else:
                result["failed"] += 1
                result["failed_tests"].append(inp.stem)

        except Exception as e:
            result["errors"] += 1
            result["error_tests"].append(
                f"{inp.stem}:{type(e).__name__}:{e}"
            )

    print(json.dumps(result))


def source_metrics(path):
    text = path.read_text(errors="replace")

    loc = sum(
        1 for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )

    try:
        tree = ast.parse(text)
    except SyntaxError:
        return loc, 0, 0, False

    functions = sum(
        isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        for n in ast.walk(tree)
    )

    identifiers = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.arg):
            identifiers.add(node.arg)
        elif isinstance(node, ast.Name) and isinstance(
            node.ctx, (ast.Store, ast.Load)
        ):
            identifiers.add(node.id)

    return loc, functions, len(identifiers), True


def master():
    root = Path("data")
    output = Path("experiment/refactory_inventory.csv")

    rows = []

    files = []
    for q in sorted(root.glob("question_*")):
        for code in sorted((q / "code/wrong").glob("*.py")):
            files.append((q, code))

    total = len(files)

    print(f"Found {total} wrong programs")

    for idx, (q, code) in enumerate(files, 1):
        loc, functions, identifiers, syntax_ok = source_metrics(code)

        row = {
            "question": q.name,
            "bug_id": code.stem,
            "file": str(code),
            "loc": loc,
            "functions": functions,
            "identifier_count": identifiers,
            "syntax_ok": int(syntax_ok),
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "timeout": 0,
            "failed_tests": "",
            "error_tests": "",
        }

        if syntax_ok:
            try:
                p = subprocess.run(
                    [
                        sys.executable,
                        __file__,
                        "--worker",
                        str(q),
                        str(code),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                if p.returncode == 0 and p.stdout.strip():
                    data = json.loads(p.stdout.strip().splitlines()[-1])

                    row["total_tests"] = data["total_tests"]
                    row["passed"] = data["passed"]
                    row["failed"] = data["failed"]
                    row["errors"] = data["errors"]
                    row["failed_tests"] = ";".join(data["failed_tests"])
                    row["error_tests"] = ";".join(data["error_tests"])
                else:
                    row["errors"] = 1
                    row["error_tests"] = (
                        p.stderr.strip().replace("\n", " ")[:500]
                    )

            except subprocess.TimeoutExpired:
                row["timeout"] = 1

            except Exception as e:
                row["errors"] = 1
                row["error_tests"] = f"{type(e).__name__}:{e}"

        rows.append(row)

        if idx % 100 == 0 or idx == total:
            print(f"[{idx}/{total}]")

    fields = [
        "question",
        "bug_id",
        "file",
        "loc",
        "functions",
        "identifier_count",
        "syntax_ok",
        "total_tests",
        "passed",
        "failed",
        "errors",
        "timeout",
        "failed_tests",
        "error_tests",
    ]

    with output.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print()
    print(f"Inventory written to: {output}")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--worker":
        worker(sys.argv[2], sys.argv[3])
    else:
        master()
