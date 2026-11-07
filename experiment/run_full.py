from pathlib import Path
import csv
import random
import traceback

import run_pilot as rp


ROOT = Path.cwd()
MANIFEST = ROOT / "experiment/selected_60_final.csv"

rp.RUN_ROOT = ROOT / "experiment/full_runs"
rp.LOG_ROOT = ROOT / "experiment/full_results/logs"
rp.RESULT_CSV = ROOT / "experiment/full_results/full_results.csv"

RESULT_CSV = rp.RESULT_CSV

SEED = 20261107


def key_of(row):
    return (
        row["question"],
        row["bug_id"],
        row["condition"],
        row["agent"],
    )


def save(rows):
    if not rows:
        return

    RESULT_CSV.parent.mkdir(parents=True, exist_ok=True)

    fields = sorted(
        set().union(*(r.keys() for r in rows))
    )

    with RESULT_CSV.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fields,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def main():
    prompt = rp.PROMPT_FILE.read_text().strip()

    manifest = list(
        csv.DictReader(
            MANIFEST.open(encoding="utf-8")
        )
    )

    cases = [
        (r["question"], r["bug_id"])
        for r in manifest
    ]

    assert len(cases) == 60
    assert len(set(cases)) == 60

    jobs = []

    for question, bug in cases:
        for condition in ["original", "obfuscated"]:
            for agent in ["codex", "antigravity"]:
                jobs.append(
                    (question, bug, condition, agent)
                )

    assert len(jobs) == 240

    rng = random.Random(SEED)
    rng.shuffle(jobs)

    # Recupera checkpoint existente.
    rows = []
    completed = {}

    if RESULT_CSV.exists():
        rows = list(
            csv.DictReader(
                RESULT_CSV.open(encoding="utf-8")
            )
        )

        for r in rows:
            completed[key_of(r)] = r

        print(
            f"RESUME: {len(completed)}/240 "
            "runs already completed"
        )
    else:
        RESULT_CSV.parent.mkdir(
            parents=True,
            exist_ok=True
        )
        rp.LOG_ROOT.mkdir(
            parents=True,
            exist_ok=True
        )

    for order, job in enumerate(jobs, 1):
        question, bug, condition, agent = job

        key = (
            question,
            bug,
            condition,
            agent,
        )

        if key in completed:
            print(
                f"[{order}/240] SKIP completed | "
                f"{agent} | {condition} | "
                f"{question}/{bug}",
                flush=True,
            )
            continue

        print()
        print(
            f"[{order}/240] "
            f"completed={len(completed)}/240",
            flush=True,
        )

        try:
            row = rp.run_one(
                question,
                bug,
                condition,
                agent,
                prompt,
            )

            row["harness_error"] = ""

        except Exception as e:
            traceback.print_exc()

            row = {
                "question": question,
                "bug_id": bug,
                "condition": condition,
                "agent": agent,
                "model": (
                    rp.CODEX_MODEL
                    if agent == "codex"
                    else rp.ANTIGRAVITY_MODEL
                ),
                "success": 0,
                "harness_error":
                    f"{type(e).__name__}: {e}",
            }

        row["run_order"] = order
        row["shuffle_seed"] = SEED

        rows.append(row)
        completed[key] = row

        save(rows)

        successes = sum(
            int(r.get("success") or 0)
            for r in rows
        )

        print(
            f"CHECKPOINT: {len(completed)}/240 | "
            f"successful={successes}",
            flush=True,
        )

    print()
    print("=" * 78)
    print("FULL EXPERIMENT COMPLETE")
    print("=" * 78)

    print(f"Runs: {len(completed)}/240")

    successes = sum(
        int(r.get("success") or 0)
        for r in rows
    )

    print(
        f"Successful repairs: "
        f"{successes}/{len(rows)}"
    )
    print(f"Results: {RESULT_CSV}")


if __name__ == "__main__":
    main()
