#!/usr/bin/env python3
"""
score_all.py — merge FLAT + TREE-GREEDY (from results.json) with TREE-LLM (my reasoned
picks in tree_llm_picks.json) into one comparison table across difficulty tiers.

TREE-LLM scoring: pick.node_id -> that node's page range. Hit if range overlaps gold.
pages_read = range size. hops = pick.depth. "speed" for TREE-LLM is reported as #LLM calls
(= hops) + pages_read, NOT milliseconds, because the reasoning LLM is the agent itself.
"""
import json, statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
res   = json.loads((HERE / 'results.json').read_text())['rows']
picks = json.loads((HERE / 'tree_llm_picks.json').read_text())['picks']
root  = json.loads((HERE / 'tree_index.json').read_text())['root']

nodes = {}
def walk(n):
    nodes[n['node_id']] = n
    for c in n['nodes']:
        walk(c)
walk(root)

rows = []
for r in res:
    qid, gold, tier = r['id'], set(r['gold']), r['tier']
    p = picks[qid]
    nd = nodes[p['node_id']]
    rng = set(range(nd['start_index'], nd['end_index'] + 1))
    hit = int(bool(rng & gold))
    rows.append({
        'id': qid, 'tier': tier,
        'flat_h1': r['flat']['h1'], 'flat_h5': r['flat']['h5'], 'flat_mrr': r['flat']['mrr'],
        'flat_np': r['flat']['n_pages'], 'flat_ms': r['flat']['ms'],
        'tg_hit': r['tree_greedy']['h1'], 'tg_np': r['tree_greedy']['n_pages'], 'tg_dead': r['tree_greedy']['dead'],
        'tl_hit': hit, 'tl_np': len(rng), 'tl_hops': p['depth'], 'tl_leaf': nd['title'],
    })

def mean(key, tier=None):
    v = [x[key] for x in rows if tier is None or x['tier'] == tier]
    return statistics.mean(v) if v else 0.0

print("="*108)
print("Amber manual RAG — FLAT (lexical TF-IDF) vs TREE-GREEDY (lexical titles) vs TREE-LLM (agent reasoning)")
print("="*108)
print(f"\n{'id':13s} {'tier':6s} | FLAT h@1 h@5  mrr  np  ms | TREEgreedy hit np | TREE-LLM hit np hops  section")
print("-"*108)
for x in rows:
    tgnp = x['tg_np'] if not x['tg_dead'] else 'DEAD'
    print(f"{x['id']:13s} {x['tier']:6s} |"
          f"      {x['flat_h1']}   {x['flat_h5']} {x['flat_mrr']:.2f} {x['flat_np']:3d} {x['flat_ms']:4.1f} |"
          f"          {x['tg_hit']} {str(tgnp):>4} |"
          f"        {x['tl_hit']} {x['tl_np']:3d}  {x['tl_hops']:2d}  {x['tl_leaf'][:30]}")

print("\n" + "-"*108)
print("SUMMARY — mean Hit (gold page inside result) by tier")
print("-"*108)
print(f"{'tier':6s} (n) |   FLAT Hit@1  Hit@5 |  TREE-GREEDY Hit | TREE-LLM Hit |  pages_read  FLAT / TG / TL")
for tier in ['easy', 'hard', 'vhard', 'worst', None]:
    lbl = tier or 'ALL'
    n = len([x for x in rows if tier is None or x['tier'] == tier])
    print(f"{lbl:6s} ({n:2d}) |        {mean('flat_h1',tier):.2f}   {mean('flat_h5',tier):.2f} |"
          f"             {mean('tg_hit',tier):.2f} |"
          f"         {mean('tl_hit',tier):.2f} |"
          f"      {mean('flat_np',tier):4.1f} / {mean('tg_np',tier):5.0f} / {mean('tl_np',tier):4.0f}")

# cost framing
print("\n" + "-"*108)
print("COST / SPEED (different units — that's the point)")
print("-"*108)
print(f"  FLAT      : ~{mean('flat_ms'):.1f} ms CPU/query, scans all 1034 pages, 0 LLM calls, returns {mean('flat_np'):.0f} pages")
print(f"  TREE-GREEDY: <1 ms CPU/query, 0 LLM calls, but Hit={mean('tg_hit'):.2f} (lexical titles can't navigate)")
print(f"  TREE-LLM  : {mean('tl_hops'):.0f} LLM calls/query (hops), 0 ms-scan, reads 1 section ({mean('tl_np'):.0f} pages avg)")
