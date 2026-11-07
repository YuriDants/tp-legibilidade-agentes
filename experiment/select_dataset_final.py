from pathlib import Path
import ast
import csv
import hashlib
import shutil

INVENTORY = Path("experiment/refactory_inventory.csv")
OUT_CSV = Path("experiment/selected_60_final.csv")
OUT_DIR = Path("experiment/dataset_final/original")

N_PER_QUESTION = 12
MIN_IDENTIFIERS = 3
MIN_MEANINGFUL = 2

GENERIC = {
    "i","j","k","x","y","z","a","b","c","d","e","f",
    "n","m","s","t","v","r","res","ret","tmp","temp"
}


def meaningful_names(path):
    try:
        tree = ast.parse(Path(path).read_text())
    except Exception:
        return []

    names = set()

    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        args = (
            list(fn.args.posonlyargs)
            + list(fn.args.args)
            + list(fn.args.kwonlyargs)
        )

        if fn.args.vararg:
            args.append(fn.args.vararg)
        if fn.args.kwarg:
            args.append(fn.args.kwarg)

        for a in args:
            if a.arg not in {"self", "cls"}:
                names.add(a.arg)

        for n in ast.walk(fn):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                names.add(n.id)

    return sorted(
        n for n in names
        if len(n) >= 3 and n.lower() not in GENERIC
    )


def evenly_spaced(rows, n):
    if len(rows) < n:
        raise ValueError(f"Somente {len(rows)} candidatos para {n}")

    idxs = [
        round(i * (len(rows) - 1) / (n - 1))
        for i in range(n)
    ]

    result = []
    used = set()

    for idx in idxs:
        if idx not in used:
            result.append(rows[idx])
            used.add(idx)

    if len(result) < n:
        for idx, row in enumerate(rows):
            if idx not in used:
                result.append(row)
                used.add(idx)
                if len(result) == n:
                    break

    return result[:n]


rows = list(csv.DictReader(INVENTORY.open()))
valid = []
seen_source = set()

for r in rows:
    if not (
        r["syntax_ok"] == "1"
        and r["timeout"] == "0"
        and int(r["errors"]) == 0
        and int(r["passed"]) >= 1
        and int(r["failed"]) >= 1
        and int(r["identifier_count"]) >= MIN_IDENTIFIERS
    ):
        continue

    meaningful = meaningful_names(r["file"])

    if len(meaningful) < MIN_MEANINGFUL:
        continue

    source = Path(r["file"]).read_text(errors="replace")
    source_hash = hashlib.sha256(source.encode()).hexdigest()

    key = (r["question"], source_hash)

    if key in seen_source:
        continue

    seen_source.add(key)

    r["meaningful_count"] = len(meaningful)
    r["meaningful_names"] = ";".join(meaningful)
    r["failure_rate"] = int(r["failed"]) / int(r["total_tests"])
    r["source_hash"] = source_hash

    valid.append(r)


selected = []

for q in sorted(set(r["question"] for r in valid)):
    candidates = [r for r in valid if r["question"] == q]

    candidates.sort(
        key=lambda r: (
            int(r["loc"]),
            float(r["failure_rate"]),
            -int(r["meaningful_count"]),
            r["bug_id"],
        )
    )

    if len(candidates) < 12:
        raise SystemExit(
            f"{q}: somente {len(candidates)} candidatos elegíveis"
        )

    n = len(candidates)

    strata = [
        ("small", candidates[:n//3]),
        ("medium", candidates[n//3:2*n//3]),
        ("large", candidates[2*n//3:]),
    ]

    for size_class, group in strata:
        group.sort(
            key=lambda r: (
                float(r["failure_rate"]),
                -int(r["meaningful_count"]),
                int(r["loc"]),
                r["bug_id"],
            )
        )

        chosen = evenly_spaced(group, 4)

        for r in chosen:
            r["size_class"] = size_class
            selected.append(r)


if len(selected) != 60:
    raise SystemExit(f"Esperado 60, obtido {len(selected)}")


# Copia dataset
if OUT_DIR.exists():
    shutil.rmtree(OUT_DIR)

OUT_DIR.mkdir(parents=True)

for r in selected:
    dest = OUT_DIR / r["question"] / r["bug_id"]
    dest.mkdir(parents=True)

    shutil.copy2(r["file"], dest / "bug.py")

    global_file = (
        Path("data") / r["question"] / "code" / "global.py"
    )

    if global_file.exists():
        shutil.copy2(global_file, dest / "global.py")

    shutil.copytree(
        Path("data") / r["question"] / "ans",
        dest / "ans"
    )


fields = [
    "question",
    "bug_id",
    "size_class",
    "loc",
    "identifier_count",
    "meaningful_count",
    "meaningful_names",
    "total_tests",
    "passed",
    "failed",
    "failure_rate",
    "failed_tests",
    "source_hash",
    "file",
]

with OUT_CSV.open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()

    for r in selected:
        writer.writerow({k: r[k] for k in fields})


print("=== FINAL DATASET ===")

for q in sorted(set(r["question"] for r in selected)):
    candidates = sum(
        1 for r in valid if r["question"] == q
    )
    chosen = [
        r for r in selected
        if r["question"] == q
    ]

    print(
        f"{q}: candidates={candidates:3} "
        f"selected={len(chosen):2} "
        f"meaningful(min/avg/max)="
        f"{min(int(r['meaningful_count']) for r in chosen)}/"
        f"{sum(int(r['meaningful_count']) for r in chosen)/len(chosen):.1f}/"
        f"{max(int(r['meaningful_count']) for r in chosen)}"
    )

print()
print(f"TOTAL SELECTED: {len(selected)}")
print(f"Manifest: {OUT_CSV}")
print(f"Dataset:  {OUT_DIR}")

print("\n=== SELECTED CASES ===")
for r in selected:
    print(
        f"{r['bug_id']:<18} "
        f"{r['question']:<11} "
        f"{r['size_class']:<6} "
        f"LOC={int(r['loc']):2} "
        f"meaningful={int(r['meaningful_count']):2} "
        f"fail={int(r['failed'])}/{int(r['total_tests'])}"
    )
