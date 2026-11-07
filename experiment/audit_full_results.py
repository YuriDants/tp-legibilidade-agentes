from pathlib import Path
from collections import Counter, defaultdict
import csv
import hashlib

ROOT = Path.cwd()
RESULTS = ROOT / "experiment/full_results/full_results.csv"
MANIFEST = ROOT / "experiment/selected_60_final.csv"

def truthy(v):
    return str(v or "").strip().lower() in {
        "1", "true", "yes", "y", "t"
    }

def nonempty(v):
    return str(v or "").strip() != ""

rows = list(csv.DictReader(RESULTS.open(encoding="utf-8")))
manifest = list(csv.DictReader(MANIFEST.open(encoding="utf-8")))

print("=" * 72)
print("AUDIT — FULL EXPERIMENT")
print("=" * 72)

print(f"CSV rows:           {len(rows)}")
print(f"Manifest cases:     {len(manifest)}")
print(f"CSV columns:        {len(rows[0]) if rows else 0}")

if rows:
    print("\nColumns:")
    print(", ".join(rows[0].keys()))

# ------------------------------------------------------------------
# Expected experimental keys
# ------------------------------------------------------------------

keys = [
    (
        r.get("question", ""),
        r.get("bug_id", ""),
        r.get("condition", ""),
        r.get("agent", ""),
    )
    for r in rows
]

unique_keys = set(keys)
duplicates = [k for k, n in Counter(keys).items() if n != 1]

print("\n--- COMPLETENESS ---")
print(f"Unique run keys:    {len(unique_keys)}")
print(f"Duplicate keys:     {len(duplicates)}")

expected_cases = {
    (r["question"], r["bug_id"])
    for r in manifest
}

observed_cases = {
    (r.get("question", ""), r.get("bug_id", ""))
    for r in rows
}

print(f"Expected bugs:      {len(expected_cases)}")
print(f"Observed bugs:      {len(observed_cases)}")
print(f"Missing bugs:       {len(expected_cases - observed_cases)}")
print(f"Unexpected bugs:    {len(observed_cases - expected_cases)}")

# ------------------------------------------------------------------
# Group counts
# ------------------------------------------------------------------

groups = Counter(
    (r.get("agent", ""), r.get("condition", ""))
    for r in rows
)

print("\n--- GROUP COUNTS ---")
for key in sorted(groups):
    print(f"{key[0]:15s} {key[1]:12s}: {groups[key]}")

# Each selected bug should have the four expected runs
expected_combos = {
    ("codex", "original"),
    ("codex", "obfuscated"),
    ("antigravity", "original"),
    ("antigravity", "obfuscated"),
}

per_bug = defaultdict(set)
for r in rows:
    per_bug[(r.get("question", ""), r.get("bug_id", ""))].add(
        (r.get("agent", ""), r.get("condition", ""))
    )

bad_bug_combos = {
    bug: combos
    for bug, combos in per_bug.items()
    if combos != expected_combos
}

print(f"Bugs without exactly 4 expected combinations: {len(bad_bug_combos)}")

# ------------------------------------------------------------------
# Success / infrastructure
# ------------------------------------------------------------------

successes = sum(str(r.get("success", "")).strip() == "1" for r in rows)
failures = len(rows) - successes

print("\n--- REPAIR OUTCOME ---")
print(f"Success:            {successes}")
print(f"Failure:            {failures}")

checks = {
    "harness_error": lambda r: nonempty(r.get("harness_error")),
    "agent_timeout": lambda r: truthy(r.get("agent_timeout")),
    "policy_violation": lambda r: truthy(r.get("policy_violation")),
}

print("\n--- INFRASTRUCTURE / POLICY ---")

for field, fn in checks.items():
    if rows and field in rows[0]:
        bad = [r for r in rows if fn(r)]
        print(f"{field:20s}: {len(bad)}")
    else:
        print(f"{field:20s}: column not present")

# Other fields worth checking if available
optional_zero_fields = [
    "protected_files_changed",
    "protected_changes",
]

for field in optional_zero_fields:
    if rows and field in rows[0]:
        bad = [r for r in rows if nonempty(r.get(field))]
        print(f"{field:20s}: {len(bad)} non-empty")

if rows and "bug_changed" in rows[0]:
    bad = [r for r in rows if not truthy(r.get("bug_changed"))]
    print(f"{'bug_changed=false':20s}: {len(bad)}")

if rows and "post_exit_code" in rows[0]:
    bad = [
        r for r in rows
        if str(r.get("post_exit_code", "")).strip() not in {"0", "0.0"}
    ]
    print(f"{'post_exit_code!=0':20s}: {len(bad)}")

# ------------------------------------------------------------------
# Missing essential values
# ------------------------------------------------------------------

print("\n--- REQUIRED FIELDS ---")

essential = [
    "question",
    "bug_id",
    "condition",
    "agent",
    "model",
    "success",
    "run_order",
]

for field in essential:
    if not rows or field not in rows[0]:
        print(f"{field:20s}: MISSING COLUMN")
    else:
        missing = sum(not nonempty(r.get(field)) for r in rows)
        print(f"{field:20s}: {missing} empty")

# ------------------------------------------------------------------
# SHA-256
# ------------------------------------------------------------------

digest = hashlib.sha256(RESULTS.read_bytes()).hexdigest()

print("\n--- FINGERPRINT ---")
print(f"full_results.csv SHA256:")
print(digest)

# ------------------------------------------------------------------
# Final verdict
# ------------------------------------------------------------------

problems = []

if len(rows) != 240:
    problems.append(f"expected 240 rows, found {len(rows)}")

if len(unique_keys) != 240:
    problems.append(f"expected 240 unique run keys, found {len(unique_keys)}")

if duplicates:
    problems.append("duplicate/multiplicity run keys exist")

if expected_cases != observed_cases:
    problems.append("manifest case set != result case set")

if bad_bug_combos:
    problems.append("some bugs do not have all four expected combinations")

if successes != 240:
    problems.append(f"not all runs succeeded ({successes}/240)")

for field, fn in checks.items():
    if rows and field in rows[0] and any(fn(r) for r in rows):
        problems.append(f"{field} contains problematic runs")

print("\n" + "=" * 72)

if problems:
    print("AUDIT RESULT: REVIEW REQUIRED")
    for p in problems:
        print(f"- {p}")
else:
    print("AUDIT RESULT: PASS")
    print("The 240-run result set is structurally complete and clean.")

print("=" * 72)
