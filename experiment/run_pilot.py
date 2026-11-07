from pathlib import Path
import csv
import difflib
import hashlib
import json
import re
import shutil
import subprocess
import time
import traceback


ROOT = Path.cwd()
DATASET = ROOT / "experiment/dataset_final"
RUNNER_TEMPLATE = ROOT / "experiment/run_tests_template.py"
PROMPT_FILE = ROOT / "experiment/agent_prompt.txt"

RUN_ROOT = ROOT / "experiment/pilot_runs"
LOG_ROOT = ROOT / "experiment/pilot_results/logs"
RESULT_CSV = ROOT / "experiment/pilot_results/pilot_results.csv"

CODEX_MODEL = "gpt-6.1-sol"
ANTIGRAVITY_MODEL = "gemini-4-argon-medium"

TIMEOUT_SECONDS = 660


PILOT_CASES = [
    ("question_1", "wrong_1_320"),
    ("question_2", "wrong_2_326"),
    ("question_3", "wrong_3_050"),
    ("question_4", "wrong_4_227"),
    ("question_5", "wrong_5_073"),
]


def sha256(path):
    h = hashlib.sha256()

    with open(path, "rb") as f:
        while True:
            block = f.read(65536)
            if not block:
                break
            h.update(block)

    return h.hexdigest()


def snapshot_files(root):
    result = {}

    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(root))
            result[rel] = sha256(p)

    return result


def protected_changes(before, after):
    """
    bug.py pode mudar.
    Qualquer outro arquivo criado/removido/modificado é violação.
    """
    changed = []

    all_names = sorted(set(before) | set(after))

    for name in all_names:
        if name == "bug.py":
            continue

        if before.get(name) != after.get(name):
            changed.append(name)

    return changed


def run_tests(workdir):
    p = subprocess.run(
        ["python3", "run_tests.py"],
        cwd=workdir,
        capture_output=True,
        text=True,
        timeout=30,
    )

    output = (p.stdout or "") + (p.stderr or "")

    m = re.search(
        r"RESULT:\s*(\d+)/(\d+)\s+passed;\s*(\d+)\s+failed",
        output
    )

    if m:
        passed = int(m.group(1))
        total = int(m.group(2))
        failed = int(m.group(3))
    else:
        passed = None
        total = None
        failed = None

    return {
        "returncode": p.returncode,
        "passed": passed,
        "total": total,
        "failed": failed,
        "output": output.strip(),
    }


def patch_stats(before_text, after_text):
    diff = list(
        difflib.unified_diff(
            before_text.splitlines(),
            after_text.splitlines(),
            lineterm="",
        )
    )

    added = 0
    removed = 0

    for line in diff:
        if line.startswith("+++") or line.startswith("---"):
            continue

        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1

    return added, removed, "\n".join(diff)


def parse_codex_usage(events_file):
    usage = {
        "input_tokens": None,
        "cached_input_tokens": None,
        "output_tokens": None,
        "reasoning_tokens": None,
        "command_executions": 0,
    }

    if not events_file.exists():
        return usage

    with events_file.open(errors="replace") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except Exception:
                continue

            if obj.get("type") == "item.completed":
                item = obj.get("item", {})

                if item.get("type") == "command_execution":
                    usage["command_executions"] += 1

            if obj.get("type") == "turn.completed":
                u = obj.get("usage", {})

                usage["input_tokens"] = u.get("input_tokens")
                usage["cached_input_tokens"] = u.get(
                    "cached_input_tokens"
                )
                usage["output_tokens"] = u.get("output_tokens")
                usage["reasoning_tokens"] = u.get(
                    "reasoning_output_tokens"
                )

    return usage


def parse_antigravity(result_file):
    result = {
        "internal_duration_seconds": None,
        "turns": None,
        "input_tokens": None,
        "cache_read_tokens": None,
        "output_tokens": None,
        "reasoning_tokens": None,
        "reported_total_tokens": None,
    }

    if not result_file.exists():
        return result

    try:
        obj = json.loads(result_file.read_text(errors="replace"))
    except Exception:
        return result

    result["internal_duration_seconds"] = obj.get(
        "duration_seconds"
    )
    result["turns"] = obj.get("num_turns")

    u = obj.get("usage", {})

    result["input_tokens"] = u.get("input_tokens")
    result["cache_read_tokens"] = u.get("cache_read_tokens")
    result["output_tokens"] = u.get("output_tokens")
    result["reasoning_tokens"] = u.get("thinking_tokens")
    result["reported_total_tokens"] = u.get("total_tokens")

    return result


def prepare_workspace(question, bug, condition, agent):
    src = DATASET / condition / question / bug

    dst = (
        RUN_ROOT
        / agent
        / condition
        / question
        / bug
    )

    if dst.exists():
        shutil.rmtree(dst)

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)

    shutil.copy2(
        RUNNER_TEMPLATE,
        dst / "run_tests.py"
    )

    return dst


def run_codex(workdir, logdir, prompt):
    events = logdir / "events.jsonl"
    stderr = logdir / "stderr.log"
    final = logdir / "final.txt"

    cmd = [
        "codex",
        "exec",
        "-m", CODEX_MODEL,
        "--approve-for-me",
        "--skip-git-repo-check",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--json",
        "-o", str(final),
        "-C", str(workdir),
        prompt,
    ]

    start = time.monotonic()

    with events.open("w") as out, stderr.open("w") as err:
        try:
            p = subprocess.run(
                cmd,
                stdout=out,
                stderr=err,
                text=True,
                timeout=TIMEOUT_SECONDS,
            )

            timed_out = 0
            rc = p.returncode

        except subprocess.TimeoutExpired:
            timed_out = 1
            rc = None

    wall = time.monotonic() - start

    usage = parse_codex_usage(events)

    return {
        "agent_returncode": rc,
        "agent_timeout": timed_out,
        "wall_seconds": wall,
        "internal_duration_seconds": None,
        "turns": None,
        "input_tokens": usage["input_tokens"],
        "cached_input_tokens": usage["cached_input_tokens"],
        "cache_read_tokens": None,
        "output_tokens": usage["output_tokens"],
        "reasoning_tokens": usage["reasoning_tokens"],
        "reported_total_tokens": None,
        "command_executions": usage["command_executions"],
    }


def run_antigravity(workdir, logdir, prompt):
    result_file = logdir / "result.json"
    stderr = logdir / "stderr.log"

    cmd = [
        "agy",
        "-p", prompt,
        "--model", ANTIGRAVITY_MODEL,
        "--effort", "medium",
        "--output-format", "json",
        "--sandbox",
        "--dangerously-skip-permissions",
        "--print-timeout", "10m",
    ]

    start = time.monotonic()

    with result_file.open("w") as out, stderr.open("w") as err:
        try:
            p = subprocess.run(
                cmd,
                cwd=workdir,
                stdout=out,
                stderr=err,
                text=True,
                timeout=TIMEOUT_SECONDS,
            )

            timed_out = 0
            rc = p.returncode

        except subprocess.TimeoutExpired:
            timed_out = 1
            rc = None

    wall = time.monotonic() - start

    usage = parse_antigravity(result_file)

    return {
        "agent_returncode": rc,
        "agent_timeout": timed_out,
        "wall_seconds": wall,
        "internal_duration_seconds":
            usage["internal_duration_seconds"],
        "turns": usage["turns"],
        "input_tokens": usage["input_tokens"],
        "cached_input_tokens": None,
        "cache_read_tokens": usage["cache_read_tokens"],
        "output_tokens": usage["output_tokens"],
        "reasoning_tokens": usage["reasoning_tokens"],
        "reported_total_tokens":
            usage["reported_total_tokens"],
        "command_executions": None,
    }


def run_one(question, bug, condition, agent, prompt):
    print()
    print("=" * 78)
    print(
        f"{agent.upper()} | {condition.upper()} | "
        f"{question}/{bug}"
    )
    print("=" * 78)

    workdir = prepare_workspace(
        question, bug, condition, agent
    )

    logdir = (
        LOG_ROOT
        / agent
        / condition
        / question
        / bug
    )

    if logdir.exists():
        shutil.rmtree(logdir)

    logdir.mkdir(parents=True, exist_ok=True)

    original_bug = (workdir / "bug.py").read_text(
        errors="replace"
    )

    before_snapshot = snapshot_files(workdir)

    baseline = run_tests(workdir)

    print(
        f"Baseline: "
        f"{baseline['passed']}/{baseline['total']} passed"
    )

    if baseline["returncode"] == 0:
        raise RuntimeError(
            f"{question}/{bug}/{condition} "
            "already passes before agent"
        )

    if agent == "codex":
        metrics = run_codex(
            workdir, logdir, prompt
        )
    elif agent == "antigravity":
        metrics = run_antigravity(
            workdir, logdir, prompt
        )
    else:
        raise ValueError(agent)

    after_snapshot = snapshot_files(workdir)

    protected = protected_changes(
        before_snapshot,
        after_snapshot
    )

    post = run_tests(workdir)

    repaired_bug = (workdir / "bug.py").read_text(
        errors="replace"
    )

    added, removed, diff = patch_stats(
        original_bug,
        repaired_bug
    )

    (logdir / "patch.diff").write_text(
        diff,
        encoding="utf-8"
    )

    (logdir / "post_test.txt").write_text(
        post["output"],
        encoding="utf-8"
    )

    bug_changed = int(
        before_snapshot.get("bug.py")
        != after_snapshot.get("bug.py")
    )

    policy_violation = int(bool(protected))

    # Critério externo de sucesso:
    # 1. suíte passa;
    # 2. somente bug.py foi alterado;
    # 3. bug.py realmente mudou.
    success = int(
        post["returncode"] == 0
        and not protected
        and bug_changed
    )

    print(
        f"After:    "
        f"{post['passed']}/{post['total']} passed"
    )
    print(
        f"Success:  {success} | "
        f"wall={metrics['wall_seconds']:.2f}s | "
        f"patch=+{added}/-{removed}"
    )

    if protected:
        print(
            "PROTECTED FILE CHANGES:",
            ", ".join(protected)
        )

    row = {
        "question": question,
        "bug_id": bug,
        "condition": condition,
        "agent": agent,
        "model": (
            CODEX_MODEL
            if agent == "codex"
            else ANTIGRAVITY_MODEL
        ),

        "baseline_passed": baseline["passed"],
        "baseline_total": baseline["total"],
        "baseline_failed": baseline["failed"],

        "post_passed": post["passed"],
        "post_total": post["total"],
        "post_failed": post["failed"],

        "success": success,
        "bug_changed": bug_changed,
        "policy_violation": policy_violation,
        "protected_changes": ";".join(protected),

        "patch_added_lines": added,
        "patch_removed_lines": removed,
        "patch_total_lines": added + removed,

        **metrics,
    }

    return row


def main():
    prompt = PROMPT_FILE.read_text().strip()

    if RUN_ROOT.exists():
        shutil.rmtree(RUN_ROOT)

    if RESULT_CSV.parent.exists():
        shutil.rmtree(RESULT_CSV.parent)

    RESULT_CSV.parent.mkdir(parents=True)
    LOG_ROOT.mkdir(parents=True)

    rows = []

    # piloto não será usado como resultado científico;
    # ordem simples e determinística para depuração.
    jobs = []

    for question, bug in PILOT_CASES:
        for condition in ["original", "obfuscated"]:
            for agent in ["codex", "antigravity"]:
                jobs.append(
                    (question, bug, condition, agent)
                )

    for idx, job in enumerate(jobs, 1):
        question, bug, condition, agent = job

        print()
        print(f"[{idx}/{len(jobs)}]")

        try:
            row = run_one(
                question,
                bug,
                condition,
                agent,
                prompt,
            )

        except Exception as e:
            traceback.print_exc()

            row = {
                "question": question,
                "bug_id": bug,
                "condition": condition,
                "agent": agent,
                "model": (
                    CODEX_MODEL
                    if agent == "codex"
                    else ANTIGRAVITY_MODEL
                ),
                "success": 0,
                "harness_error":
                    f"{type(e).__name__}: {e}",
            }

        rows.append(row)

        # checkpoint após todo run
        fields = sorted(
            set().union(
                *(r.keys() for r in rows)
            )
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

    print()
    print("=" * 78)
    print("PILOT COMPLETE")
    print("=" * 78)

    successes = sum(
        int(r.get("success", 0) or 0)
        for r in rows
    )

    print(
        f"Successful repairs: {successes}/{len(rows)}"
    )
    print(f"Results: {RESULT_CSV}")


if __name__ == "__main__":
    main()
