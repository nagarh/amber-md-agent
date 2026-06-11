"""Aggregate per-study judge JSON into a /100 scorecard."""
import json
import sys
from pathlib import Path

from Benchmark.scripts import schema, scoring
from Benchmark.scripts.weights import DIFFICULTY_WEIGHTS

CHECKPOINTS = ("C1", "C2", "C3", "C4", "C5")


def _load(results_dir):
    objs = []
    for path in sorted(Path(results_dir).glob("study_*.json")):
        obj = json.loads(path.read_text())
        schema.validate(obj)
        objs.append(obj)
    return objs


def summarize(results_dir):
    objs = _load(results_dir)
    total_count = len(objs)
    scored = [o for o in objs if not o["blocked"]]
    blocked = total_count - len(scored)

    rows = []
    for o in scored:
        s = scoring.score_study(o["checkpoints"])
        rows.append({"obj": o, "total": s["total"],
                     "difficulty": o["difficulty"]})

    flat = (sum(r["total"] for r in rows) / len(rows) * 100.0) if rows else 0.0

    wnum = sum(r["total"] * DIFFICULTY_WEIGHTS[r["difficulty"]] for r in rows)
    wden = sum(DIFFICULTY_WEIGHTS[r["difficulty"]] for r in rows)
    weighted = (wnum / wden * 100.0) if wden else 0.0

    per_tier = {}
    for tier in DIFFICULTY_WEIGHTS:
        tier_rows = [r["total"] for r in rows if r["difficulty"] == tier]
        if tier_rows:
            per_tier[tier] = sum(tier_rows) / len(tier_rows)

    per_dim = {}
    for cid in CHECKPOINTS:
        credits = [r["obj"]["checkpoints"][cid]["credit"]
                   for r in rows
                   if r["obj"]["checkpoints"][cid]["applicable"]]
        if credits:
            per_dim[cid] = sum(credits) / len(credits)

    return {
        "flat_score": flat,
        "weighted_score": weighted,
        "per_tier": per_tier,
        "per_dimension": per_dim,
        "coverage": {"attempted": len(scored), "blocked": blocked,
                     "total": total_count},
        "blocked_studies": [o["study_id"] for o in objs if o["blocked"]],
        "rows": [{"study_id": r["obj"]["study_id"], "total": r["total"],
                  "difficulty": r["difficulty"]} for r in rows],
    }


def render_scorecard(summary):
    lines = ["# Benchmark Scorecard", ""]
    lines.append(f"**Headline (flat) score:** {summary['flat_score']:.1f}/100")
    lines.append(f"**Difficulty-weighted score:** {summary['weighted_score']:.1f}/100")
    cov = summary["coverage"]
    lines.append(f"**Coverage:** {cov['attempted']}/{cov['total']} attempted, "
                 f"{cov['blocked']} blocked")
    if summary["blocked_studies"]:
        lines.append(f"**Blocked studies:** {', '.join(summary['blocked_studies'])}")
    lines += ["", "## Per-difficulty-tier (mean study score)", ""]
    for tier, val in summary["per_tier"].items():
        lines.append(f"- {tier}: {val:.3f}")
    lines += ["", "## Per-dimension (mean credit — lowest = weakest skill)", ""]
    for cid, val in sorted(summary["per_dimension"].items(),
                           key=lambda kv: kv[1]):
        lines.append(f"- {cid}: {val:.3f}")
    lines += ["", "## Per-study", "", "| study | difficulty | score |",
              "|---|---|---|"]
    for r in summary["rows"]:
        lines.append(f"| {r['study_id']} | {r['difficulty']} | {r['total']:.3f} |")
    return "\n".join(lines) + "\n"


def main():
    repo = Path(__file__).resolve().parents[2]
    results_dir = repo / "Benchmark" / "results"
    out = repo / "Benchmark" / "BENCHMARK_SCORECARD.md"
    summary = summarize(results_dir)
    out.write_text(render_scorecard(summary))
    print(f"wrote {out}")
    print(f"flat {summary['flat_score']:.1f}/100  "
          f"weighted {summary['weighted_score']:.1f}/100")


if __name__ == "__main__":
    sys.exit(main())
