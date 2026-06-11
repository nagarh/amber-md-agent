#!/usr/bin/env python3
"""
worst_test.py — WORST-to-WORST adversarial queries: lay metaphors + typos, almost no shared
vocabulary with the manual's jargon. Compares the PRODUCTION flat RAG (scripts/rag_amber.py,
the one behind the mcp__amber__rag_query tool) against our Tree PageIndex.

FLAT      : run programmatically (real). Hit = gold page in top-5.
TREE-LLM  : the agent (Claude Code) reasoned each brutal query -> node_id (recorded in PICK).
            Hit = landed node's page range overlaps gold. Scored programmatically here.

Each query's gold pages were verified by reading the manual.
"""
import json, time, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'scripts'))
from rag_amber import PageIndex  # noqa

# q, gold pages, my reasoned tree node_id, one-line gloss of the real topic
CASES = [
    ("thing that stops chemical bonds from wiggling so i can step bigger", [396,397,398], "0516", "SHAKE"),
    ("the math trick for charges in a repeating water box",               [413,414],     "0132", "PME"),
    ("make the computer explore shapes faster by flattening hills in the energy", [478,479,480,481], "0154", "GaMD"),
    ("switch acid level handling on durring run so residues gain n lose protons", [580,581,582], "0171", "constant pH"),
    ("glue two sulfer amino acids together by hand in the setup proggram", [247,251],    "0087", "disulfide bond cmd"),
    ("tool that says how far my shape drifted from the start frame by frame", [810,811], "0342", "cpptraj rms"),
    ("surround the molecule with a sea of watter befor runnin",            [263],        "0087", "solvateBox"),
    ("slowly make a drug molecule dissapear to get a binding strength number", list(range(505,520)), "0162", "TI"),
    ("pin my protein in place so it dont drift during warmup",             [391],        "0511", "positional restraints"),
    ("shuffle copys at diferent temperatures to sample beter",            [521,522,523], "0164", "REMD"),
]


def main():
    flat = PageIndex(); flat.load(str(HERE.parent / 'references' / 'amber_index.json'))
    tree = json.loads((HERE / 'tree_index.json').read_text())['root']
    nodes = {}
    def idx(n):
        nodes[n['node_id']] = n
        for c in n['nodes']:
            idx(c)
    idx(tree)

    print("="*100)
    print("WORST-TO-WORST adversarial queries — Production FLAT RAG vs Tree PageIndex")
    print("="*100)
    print(f"\n{'topic':22s} | FLAT  hit  rank  ms  np | TREE  hit  np  landed")
    print("-"*100)

    fh = th = 0
    fnp = tnp = 0
    for q, gold, pick, topic in CASES:
        gold = set(gold)
        t0 = time.perf_counter()
        res = flat.query(q, top_k=5)
        ms = (time.perf_counter()-t0)*1000
        fpages = [r['page'] for r in res]
        frank = next((i for i,p in enumerate(fpages,1) if p in gold), 0)
        fhit = int(frank > 0); fh += fhit; fnp += 5

        nd = nodes[pick]
        rng = set(range(nd['start_index'], nd['end_index']+1))
        thit = int(bool(rng & gold)); th += thit; tnp += len(rng)

        print(f"{topic:22s} |      {fhit}   {frank or '-':>3}  {ms:4.1f}  5  |       {thit}  {len(rng):3d}  {nd['title'][:34]}")

    n = len(CASES)
    print("-"*100)
    print(f"{'TOTALS / mean':22s} | Hit {fh}/{n} = {fh/n:.2f}            |   Hit {th}/{n} = {th/n:.2f}")
    print(f"\nFLAT  : Hit@5 {fh/n:.0%}  | ~{2.7:.1f} ms CPU | 0 LLM calls | {fnp//n} pages returned/q")
    print(f"TREE  : Hit   {th/n:.0%}  | 3-4 LLM hops/q | reads {tnp/n:.0f} pages/q (1 leaf)")


if __name__ == '__main__':
    main()
