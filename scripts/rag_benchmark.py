#!/usr/bin/env python
"""Stress-test: OLD (page TF-IDF) vs NEW passage-only vs NEW passage+LLM-rerank.
Queries are deliberately awful: vague, jargon-free, indirect, misspelled."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from rag_amber import PageIndex
import rag_rerank as RR

QUERIES = [
    ("how do I keep the temperature steady during my run",        "thermostat: ntt / temp0 / tautp / gamma_ln"),
    ("what nonbonded cutoff should I use with PME explicit solvent","PME direct-space cut (~8-10 A) in &cntrl"),
    ("how do I stop my molecule from blowing up at the very start", "minimization / slow heating / restraints"),
    ("keep the box from changing size",                            "constant volume NVT, ntb=1 (no barostat)"),
    ("the setting that controls how hot the simulation is",        "temp0 / ntt thermostat"),
    ("thermostadt for langevan dynamcs",                           "Langevin: ntt=3, gamma_ln (misspelled)"),
    ("how often should I save the coordinates",                    "ntwx trajectory write frequency"),
    ("my simulation crashed right after it started what do I check","instability: minimize, dt, SHAKE, close contacts"),
]

def short(txt, n=150):
    return " ".join(txt.split())[:n]

def main():
    idx = PageIndex(); idx.load(RR.DEFAULT_INDEX)
    RR._INDEX = idx
    for q, gold in QUERIES:
        print("\n" + "=" * 100)
        print(f"Q: {q}\nGOLD: {gold}")
        # OLD: page-level TF-IDF
        old = idx.query(q, top_k=3)
        print("\n  OLD (page TF-IDF) top-3:")
        for r in old:
            print(f"    p.{r['page']:<4} {short(r['section_path'],55):<55} | {short(r['text'],90)}")
        # NEW passage-only (no rerank)
        praw = RR.passage_recall(idx, q, pool=3)
        print("  NEW passage-only top-3:")
        for r in praw:
            print(f"    p.{r['page']:<4} {short(r['section_path'],55):<55} | {short(r['best_passage'],90)}")
        # NEW passage + LLM rerank (pool 20 -> 3)
        try:
            new = RR.enhanced_query(q, top_k=3, pool=20, rerank=True)
            print("  NEW passage+RERANK top-3:")
            for r in new:
                print(f"    p.{r['page']:<4} {short(r['section_path'],55):<55} | {short(r['snippet'],90)}")
        except Exception as e:
            print(f"  RERANK ERROR: {e}")

if __name__ == "__main__":
    main()
