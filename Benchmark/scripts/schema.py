"""Validate a single judge output object."""
from Benchmark.scripts.weights import DIFFICULTY_WEIGHTS

CHECKPOINTS = ("C1", "C2", "C3", "C4", "C5")
TOP_FIELDS = ("study_id", "orig_id", "title", "checkpoints", "blocked",
              "difficulty", "paper_checked", "answer_key_ok")


class SchemaError(ValueError):
    pass


def validate(obj):
    for field in TOP_FIELDS:
        if field not in obj:
            raise SchemaError(f"missing top-level field: {field}")

    if obj["difficulty"] not in DIFFICULTY_WEIGHTS:
        raise SchemaError(f"bad difficulty: {obj['difficulty']!r}")

    for flag in ("blocked", "paper_checked", "answer_key_ok"):
        if not isinstance(obj[flag], bool):
            raise SchemaError(f"{flag} must be bool")

    cps = obj["checkpoints"]
    for cid in CHECKPOINTS:
        if cid not in cps:
            raise SchemaError(f"missing checkpoint: {cid}")
        entry = cps[cid]
        for key in ("credit", "applicable", "note"):
            if key not in entry:
                raise SchemaError(f"{cid} missing {key}")
        if not isinstance(entry["applicable"], bool):
            raise SchemaError(f"{cid}.applicable must be bool")
        credit = entry["credit"]
        if not isinstance(credit, (int, float)) or not (0.0 <= credit <= 1.0):
            raise SchemaError(f"{cid}.credit out of [0,1]: {credit!r}")

    # Mandatory-paper-read rule: no paper -> C5 must be unscored (N/A).
    if not obj["paper_checked"] and cps["C5"]["applicable"]:
        raise SchemaError("paper_checked is false but C5 is applicable; "
                          "C5 must be N/A when the source paper was not read")
    return True
