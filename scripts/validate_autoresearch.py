#!/usr/bin/env python3
"""
Validates autoresearch/ state files and skill section completeness.
Run after any change to autoresearch/ or skills/autoresearch-*.md.

Usage:
    /home/hn533621/.conda/envs/amber_development/bin/python scripts/validate_autoresearch.py
"""
import json
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
ERRORS = []


def fail(msg):
    ERRORS.append(msg)
    print(f"  FAIL: {msg}")


def ok(msg):
    print(f"  OK:   {msg}")


# ─── State JSON schema ────────────────────────────────────────────────────────

def validate_state_json():
    print("\n[research_state.json]")
    path = BASE / "autoresearch" / "research_state.json"
    if not path.exists():
        fail("autoresearch/research_state.json not found")
        return

    with open(path) as f:
        state = json.load(f)

    required_keys = [
        "version", "loop_iteration", "phase", "current_study",
        "current_hypothesis", "hypothesis_queue", "completed_studies",
        "pending_slurm_job", "pending_capability_test",
        "capability_retry_count", "supported_system_types", "blocked_system_types",
    ]
    for key in required_keys:
        if key not in state:
            fail(f"Missing key: {key}")
        else:
            ok(f"Key present: {key}")

    valid_phases = ["propose", "capability_check", "experiment", "reason"]
    if state.get("phase") not in valid_phases:
        fail(f"phase must be one of {valid_phases}, got: {state.get('phase')}")
    else:
        ok(f"phase is valid: {state['phase']}")

    if not isinstance(state.get("hypothesis_queue"), list):
        fail("hypothesis_queue must be a list")
    else:
        ok(f"hypothesis_queue is list with {len(state['hypothesis_queue'])} items")

    for i, hyp in enumerate(state.get("hypothesis_queue", [])):
        hyp_keys = ["id", "title", "system_type", "target_system",
                    "question", "source", "source_ref", "priority", "rationale"]
        for k in hyp_keys:
            if k not in hyp:
                fail(f"hypothesis_queue[{i}] missing key: {k}")
        if not (0.0 <= hyp.get("priority", -1) <= 1.0):
            fail(f"hypothesis_queue[{i}].priority out of [0,1]: {hyp.get('priority')}")

    if not isinstance(state.get("supported_system_types"), list):
        fail("supported_system_types must be a list")
    else:
        ok(f"supported_system_types: {state['supported_system_types']}")


# ─── Required state files ─────────────────────────────────────────────────────

def validate_state_files():
    print("\n[autoresearch/ files]")
    required_files = [
        "autoresearch/research_state.json",
        "autoresearch/knowledge_base.md",
        "autoresearch/capability_log.md",
        "autoresearch/hypothesis_queue.md",
    ]
    for rel in required_files:
        p = BASE / rel
        if not p.exists():
            fail(f"Missing: {rel}")
        elif p.stat().st_size == 0:
            fail(f"Empty file: {rel}")
        else:
            ok(f"Exists and non-empty: {rel}")


# ─── Skill section checks ─────────────────────────────────────────────────────

REQUIRED_SKILL_SECTIONS = {
    "skills/autoresearch-loop.md": [
        "## Step 1", "## Step 2", "phase", "ScheduleWakeup", "research_state.json",
    ],
    "skills/autoresearch-propose.md": [
        "## Step 1", "## Step 2", "## Step 3", "## Step 4", "## Step 5",
        "priority", "system_type", "knowledge_base", "PubMed",
    ],
    "skills/autoresearch-capability.md": [
        "## Step 1", "## Step 2", "## Step 3", "## Step 4", "## Step 5", "## Step 6",
        "skills/draft", "conda install", "capability_log", "PASS", "FAIL", "retry",
    ],
    "skills/autoresearch-reflect.md": [
        "## Step 1", "## Step 2", "## Step 3", "## Step 4", "## Step 5",
        "STUDY_REPORT", "knowledge_base", "hypothesis",
    ],
}


def validate_skills():
    print("\n[skill files]")
    for rel, required_terms in REQUIRED_SKILL_SECTIONS.items():
        p = BASE / rel
        if not p.exists():
            fail(f"Missing skill: {rel}")
            continue
        content = p.read_text()
        for term in required_terms:
            if term not in content:
                fail(f"{rel}: missing required term '{term}'")
            else:
                ok(f"{rel}: contains '{term}'")


# ─── CLAUDE.md check ──────────────────────────────────────────────────────────

def validate_claude_md():
    print("\n[CLAUDE.md]")
    claude_md = BASE / "CLAUDE.md"
    if not claude_md.exists():
        fail("CLAUDE.md not found")
        return
    content = claude_md.read_text()
    required = [
        "autoresearch-loop.md",
        "autoresearch-propose.md",
        "autoresearch-capability.md",
        "autoresearch-reflect.md",
        "Autoresearch Mode",
    ]
    for term in required:
        if term in content:
            ok(f"CLAUDE.md contains: {term}")
        else:
            fail(f"CLAUDE.md missing: {term}")


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("Autoresearch State Validation")
    print("=" * 60)

    validate_state_files()
    validate_state_json()
    validate_skills()
    validate_claude_md()

    print("\n" + "=" * 60)
    if ERRORS:
        print(f"RESULT: FAIL — {len(ERRORS)} error(s)")
        for e in ERRORS:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("RESULT: PASS — all checks OK")
        sys.exit(0)
