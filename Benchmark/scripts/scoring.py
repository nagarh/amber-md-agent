"""Per-study scoring: turn judge credit fractions into a weighted total.

Judge supplies per checkpoint: {"credit": 0..1, "applicable": bool, "note": str}.
We renormalize CHECKPOINT_WEIGHTS over the applicable checkpoints so every
study total stays on [0, 1] and remains comparable across studies.
"""
from Benchmark.scripts.weights import CHECKPOINT_WEIGHTS

CHECKPOINTS = ("C1", "C2", "C3", "C4", "C5")


def score_study(checkpoints):
    """checkpoints: dict id -> {"credit": float, "applicable": bool}.

    Returns {"total": float, "checkpoints": {id: {"score","max","credit"}}}.
    Raises KeyError if a checkpoint is missing, ValueError on bad input.
    """
    for cid in CHECKPOINTS:
        if cid not in checkpoints:
            raise KeyError(f"missing checkpoint {cid}")

    applicable = [c for c in CHECKPOINTS if checkpoints[c].get("applicable", True)]
    if not applicable:
        raise ValueError("at least one checkpoint must be applicable")

    base_sum = sum(CHECKPOINT_WEIGHTS[c] for c in applicable)

    out = {}
    total = 0.0
    for cid in CHECKPOINTS:
        entry = checkpoints[cid]
        is_app = entry.get("applicable", True)
        credit = float(entry["credit"])
        if not (0.0 <= credit <= 1.0):
            raise ValueError(f"{cid} credit {credit} out of [0,1]")
        max_w = (CHECKPOINT_WEIGHTS[cid] / base_sum) if is_app else 0.0
        score = max_w * credit if is_app else 0.0
        out[cid] = {"credit": credit, "max": max_w, "score": score}
        total += score

    return {"total": total, "checkpoints": out}
