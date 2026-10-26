#!/usr/bin/env python3
"""Run ASTRAL on one input group as a memory-gated, low-priority queue, so
other jobs on the machine are not harmed.

Each input is run by run_astral.run_one (same conversion, ASTER command,
scoring and results CSV as run_astral.py), with three differences:

- An input starts only when there is memory for it: MemAvailable, minus the
  memory still to be claimed by the inputs already running (the per-input
  estimate each, less what they already use), must cover the estimate plus
  --reserve-gb, which is always left free for everything else. The estimate
  starts at --job-mem-gb and, once inputs have finished, becomes 1.15 times
  the largest peak memory measured so far. Inputs that do not fit wait in
  the queue; nothing running is ever stopped.
- ASTRAL runs at the lowest CPU priority (nice 19), so other jobs get the
  CPU first and ASTRAL uses only what is left over.
- --threads sets ASTER's threads per input (recorded in the CSV).

Finished inputs are skipped, so an interrupted queue resumes with the same
command. Run from the repository root:

    QWQFM/.venv/bin/python baselines/scripts/run_astral_queued.py --only 101 \
        --max-jobs 4 --threads 8 --job-mem-gb 21 --reserve-gb 6
"""

import argparse
import multiprocessing as mp
import os
import queue
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_astral as ra  # noqa: E402

GB = 1024 ** 3


def mem_available_gb():
    with open("/proc/meminfo") as handle:
        for line in handle:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024 / GB
    raise RuntimeError("MemAvailable not found in /proc/meminfo")


def tree_rss_gb(root_pid):
    """Resident memory of a process and all its descendants."""
    children, rss = {}, {}
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/stat") as handle:
                fields = handle.read().rsplit(")", 1)[1].split()
            children.setdefault(int(fields[1]), []).append(int(entry))
            rss[int(entry)] = int(fields[21]) * os.sysconf("SC_PAGE_SIZE")
        except (FileNotFoundError, ProcessLookupError, IndexError, ValueError):
            continue
    total, stack = 0, [root_pid]
    while stack:
        pid = stack.pop()
        total += rss.get(pid, 0)
        stack.extend(children.get(pid, []))
    return total / GB


def finished(spec):
    out = ra.OUT_DIR / spec["group"] / spec["name"]
    tree = out / "astral.tre"
    return (ra.read_json(out / "run.json") is not None and ra.read_json(out / "score.json") is not None
            and tree.exists() and tree.stat().st_size > 0)


def worker(spec, threads, results):
    os.nice(19)  # inherited by the converter, ASTER and the scorer
    try:
        results.put(("ok", spec["name"], ra.run_one(spec, threads)))
    except Exception as error:  # report and let the queue go on
        results.put(("error", spec["name"], repr(error)))


def log(message):
    print(f"{time.strftime('%F %T')} {message}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", required=True, help="one group: 11 15 37 48 biological 101 144 200")
    parser.add_argument("--max-jobs", type=int, default=2, help="inputs run at once at most (default 2)")
    parser.add_argument("--threads", type=int, default=1, help="ASTER threads per input (default 1)")
    parser.add_argument("--job-mem-gb", type=float, default=21.0,
                        help="peak memory of one input (default 21 GB, a 101-taxon replicate)")
    parser.add_argument("--reserve-gb", type=float, default=6.0,
                        help="memory always left free for other jobs (default 6 GB)")
    parser.add_argument("--poll", type=float, default=20.0, help="seconds between checks (default 20)")
    args = parser.parse_args()

    specs = [s for s in ra.runs() if s["group"] == args.only]
    if not specs:
        sys.exit(f"no inputs found for group {args.only}")
    rows, errors = {}, []

    def estimate_gb():
        peaks = [float(r["max_rss_mb"]) / 1024 for r in rows.values() if r.get("max_rss_mb")]
        return 1.15 * max(peaks) if peaks else args.job_mem_gb

    pending = []
    for spec in specs:
        if finished(spec):  # only rebuilds the CSV row from the saved files
            row = ra.run_one(spec)
            rows[(row["group"], row["input_file"])] = row
        else:
            pending.append(spec)
    if rows:
        ra.write_csv(rows)
    log(f"{len(specs)} inputs in group {args.only}: {len(rows)} already finished, {len(pending)} queued; "
        f"up to {args.max_jobs} at once, {args.threads} threads each, "
        f"{estimate_gb():.1f} GB estimated per input, {args.reserve_gb:g} GB kept free, nice 19")

    results = mp.Queue()
    running = {}  # name -> Process
    blocked_logged = False
    while pending or running:
        while True:
            try:
                status, name, payload = results.get_nowait()
            except queue.Empty:
                break
            if status == "ok":
                rows[(payload["group"], payload["input_file"])] = payload
                ra.write_csv(rows)
                log(f"[{len(rows)}/{len(specs)}] {name}: RF {payload['rf'] or '-'}, "
                    f"quartet score {payload['quartet_score_fraction']}, time {payload['end_to_end_seconds']} s, "
                    f"RSS {payload['max_rss_mb']} MB")
            else:
                errors.append(name)
                log(f"ERROR {name}: {payload}")
        for name in [n for n, p in running.items() if not p.is_alive()]:
            running.pop(name).join()

        if pending and len(running) < args.max_jobs:
            job_gb = estimate_gb()
            still_to_claim = sum(max(0.0, job_gb - tree_rss_gb(p.pid)) for p in running.values())
            free = mem_available_gb() - still_to_claim
            if free >= job_gb + args.reserve_gb:
                spec = pending.pop(0)
                process = mp.Process(target=worker, args=(spec, args.threads, results), daemon=False)
                process.start()
                running[spec["name"]] = process
                blocked_logged = False
                log(f"started {spec['name']} ({len(running)} running, {len(pending)} queued, "
                    f"{free:.1f} GB usable before start, {job_gb:.1f} GB estimated per input)")
                time.sleep(args.poll)  # let it begin claiming memory before the next check
                continue
            if not blocked_logged:
                log(f"waiting for memory: {free:.1f} GB usable, need "
                    f"{job_gb + args.reserve_gb:.1f} GB ({len(running)} running, {len(pending)} queued)")
                blocked_logged = True
        time.sleep(args.poll)

    log(f"done: {len(rows)}/{len(specs)} finished, {len(errors)} errors {errors if errors else ''}")
    log(f"Saved {ra.CSV_PATH}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
