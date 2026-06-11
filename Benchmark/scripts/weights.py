"""Single source of truth for benchmark scoring weights.

CHECKPOINT_WEIGHTS sum to 1.0. When a checkpoint is N/A for a study,
scoring.renormalize() drops it and rescales the rest back to 1.0.
"""

CHECKPOINT_WEIGHTS = {
    "C1": 0.20,  # system built
    "C2": 0.15,  # methodology + process compliance (process is a minor sub-part)
    "C3": 0.15,  # ran to completion
    "C4": 0.20,  # analysis correct
    "C5": 0.30,  # result matches literature
}

DIFFICULTY_WEIGHTS = {
    "easy": 1,
    "medium": 2,
    "hard": 3,
    "very-hard": 4,
}
