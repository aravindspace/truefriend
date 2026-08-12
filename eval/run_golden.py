"""P1.21 — the golden-set eval runner (§15, all three layers).

For each scenario: (optionally seed another person's private memory) → run one
real turn through the full brain under the harness → read the final graph state
back from the checkpointer → run the deterministic checks (§15 layer 1) and the
independent LLM judge (§15 layer 2). Writes a markdown report; every judged run
is a Langfuse trace when tracing is on (§15 layer 3).

Checkpointed: a scenario whose result is already in the JSONL is skipped, so an
interrupted or partial run resumes. Deterministic assertions are the hard gate;
judge scores are reported as averages and a floor.

Usage
-----
    python eval/run_golden.py                 # full set, resume if partial
    python eval/run_golden.py --fresh         # ignore prior results
    python eval/run_golden.py --only grief    # scenarios whose id/category matches
    python eval/run_golden.py --no-judge      # deterministic layer only (cheap, offline)
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from langchain_core.messages import HumanMessage

from arjun.graph.build import build_brain
from arjun.graph.state import initial_state
from arjun.harness.budgets import get_budget
from arjun.harness.runner import TurnRequest, run_turn
from arjun.memory.stores import make_checkpointer, make_store
from arjun.memory.namespaces import ReadScope

from eval.checks import CheckResult, run_checks
from eval.judge import Verdict, judge_turn
from eval.scenario import Scenario, load_scenarios

RESULTS_DIR = Path(__file__).resolve().parent / "results"
JUDGE_PASS_FLOOR = 3  # any rubric axis below this on any scenario is flagged


def _seed_other_person(store, scenario: Scenario) -> None:
    """Write a DIFFERENT person's private profile + episode so a privacy probe
    can prove it never surfaces (§7.4). Idempotent per run."""
    seed = scenario.seed_other_person
    if seed is None:
        return
    scope = ReadScope(seed.person_id)
    store.put(scope.person("profile"), "name", {"text": f"Name: {seed.name}"})
    store.put(scope.person("profile"), "uniquename", {"text": f"Uniquename: {seed.uniquename}"})
    store.put(scope.person("episodes"), "seed", {"text": seed.episode})


def _final_state(graph, session: str) -> dict:
    """The state left in the checkpointer after the turn (§20.1 end)."""
    snapshot = graph.get_state({"configurable": {"thread_id": session}})
    return dict(snapshot.values)


def run_one(graph, store, scenario: Scenario, *, with_judge: bool) -> dict:
    _seed_other_person(store, scenario)
    session = f"eval_{scenario.id}"
    # A fresh guest each scenario keeps turns independent; privacy probes rely
    # on the current person being someone OTHER than the seeded person.
    person_id = f"guest_eval_{scenario.id}"
    reply = run_turn(
        TurnRequest(person_or_guest=person_id, message=scenario.message),
        graph,
        session=session,
        step_timeout=180,
    )
    state = _final_state(graph, session)

    checks = run_checks(scenario, reply, state)
    verdict = judge_turn(scenario.message, reply, state, scenario.judge_focus) if with_judge else None

    return {
        "id": scenario.id,
        "category": scenario.category,
        "reply": reply,
        "checks": [c.__dict__ for c in checks],
        "deterministic_pass": all(c.passed for c in checks),
        "verdict": verdict.model_dump() if verdict else None,
    }


def _load_prior(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    done = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            done[record["id"]] = record
    return done


def _write_report(results: list[dict], report_path: Path) -> None:
    total = len(results)
    det_pass = sum(r["deterministic_pass"] for r in results)
    judged = [r for r in results if r["verdict"]]

    lines = [
        "# P1.21 — Golden set evaluation report",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Scenarios: {total} · Deterministic pass: **{det_pass}/{total}**",
        "",
        "## 1. Deterministic assertions (hard gate — §15 layer 1)",
        "",
        "| Scenario | Category | Pass | Failing checks |",
        "|---|---|---|---|",
    ]
    for r in results:
        failing = [f"{c['name']}: {c['detail']}" for c in r["checks"] if not c["passed"]]
        mark = "✅" if r["deterministic_pass"] else "❌"
        lines.append(f"| {r['id']} | {r['category']} | {mark} | {'; '.join(failing) or '—'} |")

    if judged:
        axes = list(Verdict.model_fields.keys())
        axes.remove("reason")
        lines += ["", "## 2. LLM judge (§15 layer 2 — independent judge family)", "",
                  "| Axis | Mean | Min |", "|---|---|---|"]
        for axis in axes:
            vals = [r["verdict"][axis] for r in judged]
            lines.append(f"| {axis} | {sum(vals) / len(vals):.2f} | {min(vals)} |")

        below = [(r["id"], axis, r["verdict"][axis])
                 for r in judged for axis in axes if r["verdict"][axis] < JUDGE_PASS_FLOOR]
        lines += ["", f"### Axes below the floor ({JUDGE_PASS_FLOOR})", ""]
        if below:
            lines += [f"- `{sid}` — {axis}={score}" for sid, axis, score in below]
        else:
            lines.append("_None — every axis met the floor on every scenario._")

    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fresh", action="store_true", help="ignore prior results")
    parser.add_argument("--only", help="run only scenarios whose id or category contains this")
    parser.add_argument("--no-judge", action="store_true", help="deterministic layer only")
    args = parser.parse_args()

    scenarios = load_scenarios()
    if args.only:
        scenarios = [s for s in scenarios if args.only in s.id or args.only in s.category]
    if not scenarios:
        raise SystemExit("no scenarios matched")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    jsonl_path = RESULTS_DIR / "golden_results.jsonl"
    if args.fresh and jsonl_path.exists():
        jsonl_path.unlink()
    prior = _load_prior(jsonl_path)

    # One brain + store for the whole run (the store persists seeded people).
    store = make_store(RESULTS_DIR / "eval_store.db")
    graph = build_brain(store=store, checkpointer=make_checkpointer(RESULTS_DIR / "eval_checkpoints.db"))

    results: list[dict] = []
    for index, scenario in enumerate(scenarios, start=1):
        if scenario.id in prior:
            results.append(prior[scenario.id])
            print(f"[{index}/{len(scenarios)}] {scenario.id} — cached")
            continue
        print(f"[{index}/{len(scenarios)}] {scenario.id} — running…", flush=True)
        record = run_one(graph, store, scenario, with_judge=not args.no_judge)
        with open(jsonl_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        results.append(record)
        mark = "OK" if record["deterministic_pass"] else "FAIL"
        print(f"    → deterministic {mark}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = RESULTS_DIR / f"golden_report_{stamp}.md"
    _write_report(results, report_path)
    det_pass = sum(r["deterministic_pass"] for r in results)
    print(f"\nReport: {report_path}")
    print(f"Deterministic: {det_pass}/{len(results)} passed")
    raise SystemExit(0 if det_pass == len(results) else 1)


if __name__ == "__main__":
    main()
