#!/usr/bin/env python3
"""
benchmark.py — Flat TF-IDF RAG vs Tree PageIndex on a labeled Amber-manual query set.

Evaluates two FULLY PROGRAMMATIC retrievers (fair, reproducible):
  FLAT        : scripts/rag_amber.PageIndex.query  (lexical TF-IDF over all 1034 pages)
  TREE-GREEDY : deterministic title-only tree walk (pick child whose TITLE best overlaps
                the query; descend to a leaf). This is the tree structure WITHOUT an LLM.

The third retriever, TREE-LLM (Claude Code reasoning over node titles), is run by the agent
by hand and merged into the report — it is the real PageIndex method and is NOT in this
script (no working LLM API key in this environment).

Metrics per retriever:
  Hit@1 / Hit@3 / Hit@5 : a returned/landed page is within the query's gold page set
  MRR                   : 1/rank of first gold page (0 if none in top-k)
  latency_ms            : median wall-clock per query
  pages_returned        : how many full pages handed to the reader (context cost proxy)

Usage:
  python benchmark.py                 # run, print table, write results.json
"""
import json, time, re, sys, statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'scripts'))
from rag_amber import PageIndex, tokenize  # noqa: E402

FLAT_INDEX = HERE.parent / 'references' / 'amber_index.json'
TREE_INDEX = HERE / 'tree_index.json'
QUERIES    = HERE / 'queries.json'
TOPK = 5


# ── FLAT ────────────────────────────────────────────────────────────────────────
def run_flat(index, q):
    t0 = time.perf_counter()
    res = index.query(q, top_k=TOPK)
    dt = (time.perf_counter() - t0) * 1000
    pages = [r['page'] for r in res]
    return pages, dt


# ── TREE-GREEDY (deterministic, no LLM) ──────────────────────────────────────────
def _title_overlap(q_tokens, title):
    """Lexical overlap between query tokens and a node title (tokenized same way)."""
    tt = set(tokenize(title))
    if not tt:
        return 0
    return len(set(q_tokens) & tt)


def _subtree_titles(node):
    out = [node['title']]
    for c in node['nodes']:
        out.extend(_subtree_titles(c))
    return out


def _subtree_best_overlap(q_tokens, node):
    """Best title-overlap found ANYWHERE in node's subtree (look-ahead) — lets an abstract
    parent ('Running simulations') win when a descendant title matches the query."""
    return max(_title_overlap(q_tokens, t) for t in _subtree_titles(node))


def run_tree_greedy(root, q):
    """Walk from root: at each level pick the child whose SUBTREE best matches the query
    title-wise; descend until a leaf or a dead-end (no lexical signal anywhere ahead).

    A dead-end at the root (hops==0) means lexical title-nav found nothing -> non-answer:
    we report it as a miss with the full remaining range (huge pages_read exposes it)."""
    t0 = time.perf_counter()
    q_tokens = tokenize(q)
    node = root
    hops = 0
    dead = False
    while node['nodes']:
        scored = [(_subtree_best_overlap(q_tokens, c), -(c['end_index'] - c['start_index']), i, c)
                  for i, c in enumerate(node['nodes'])]
        scored.sort(reverse=True)
        if scored[0][0] == 0:
            dead = True
            break  # no lexical signal anywhere ahead — greedy nav cannot proceed
        node = scored[0][3]
        hops += 1
    dt = (time.perf_counter() - t0) * 1000
    pages = list(range(node['start_index'], node['end_index'] + 1))
    return pages, dt, hops, node, dead


# ── metrics ───────────────────────────────────────────────────────────────────
def hits(pages, gold, topk=TOPK):
    """For FLAT: pages is ranked list -> Hit@k uses first k. For TREE: pages is a leaf
    range (unranked) -> treat as Hit if any overlaps gold (and rank=1 if so)."""
    gold = set(gold)
    h1 = int(bool(set(pages[:1]) & gold))
    h3 = int(bool(set(pages[:3]) & gold))
    h5 = int(bool(set(pages[:topk]) & gold))
    rank = 0
    for i, p in enumerate(pages[:topk], 1):
        if p in gold:
            rank = i
            break
    mrr = 1.0 / rank if rank else 0.0
    return h1, h3, h5, mrr


def tree_hit(pages, gold, dead, hops):
    """Tree leaf: a range. Hit only if it actually localized (descended at least once and
    did not dead-end) AND the landed range overlaps gold."""
    if dead or hops == 0:
        return 0, 0, 0, 0.0
    ov = bool(set(pages) & set(gold))
    return int(ov), int(ov), int(ov), (1.0 if ov else 0.0)


def main():
    flat = PageIndex(); flat.load(str(FLAT_INDEX))
    tree = json.loads(TREE_INDEX.read_text())['root']
    qset = json.loads(QUERIES.read_text())['queries']

    rows = []
    for item in qset:
        q, gold, tier = item['q'], item['gold'], item['tier']

        fp, fdt = run_flat(flat, q)
        fh1, fh3, fh5, fmrr = hits(fp, gold)

        tp, tdt, thops, leaf, dead = run_tree_greedy(tree, q)
        th1, th3, th5, tmrr = tree_hit(tp, gold, dead, thops)

        rows.append({
            'id': item['id'], 'tier': tier, 'q': q, 'gold': gold,
            'flat': {'pages': fp, 'ms': round(fdt, 2), 'h1': fh1, 'h3': fh3, 'h5': fh5, 'mrr': round(fmrr, 3),
                     'n_pages': len(fp)},
            'tree_greedy': {'leaf': leaf['title'], 'range': [leaf['start_index'], leaf['end_index']],
                            'ms': round(tdt, 3), 'hops': thops, 'dead': dead, 'h1': th1, 'mrr': round(tmrr, 3),
                            'n_pages': len(tp)},
        })

    # ── aggregate ──
    def agg(key, metric, tier=None):
        vals = [r[key][metric] for r in rows if (tier is None or r['tier'] == tier)]
        return statistics.mean(vals) if vals else 0.0

    tiers = ['easy', 'hard', 'vhard', 'worst', None]
    print(f"\n{'='*92}\nAmber manual RAG benchmark — {len(rows)} queries, top_k={TOPK}\n{'='*92}\n")

    # per-query detail
    print(f"{'id':14s} {'tier':6s} | FLAT h@1 h@3 h@5  mrr   ms   np | TREEg hit hops  ms   np  leaf")
    print('-'*92)
    for r in rows:
        f, t = r['flat'], r['tree_greedy']
        print(f"{r['id']:14s} {r['tier']:6s} |     {f['h1']}   {f['h3']}   {f['h5']}  {f['mrr']:.2f} {f['ms']:5.1f} {f['n_pages']:3d} |"
              f"      {t['h1']}   {t['hops']:2d} {t['ms']:5.2f} {t['n_pages']:4d}  {t['leaf'][:26]}")

    # summary
    print(f"\n{'-'*92}\nSUMMARY (mean)\n{'-'*92}")
    print(f"{'tier':8s} | FLAT  Hit@1 Hit@3 Hit@5  MRR  ms   | TREE-greedy Hit  MRR  ms     pages_read(F/T)")
    for tier in tiers:
        label = tier or 'ALL'
        n = len([r for r in rows if tier is None or r['tier'] == tier])
        print(f"{label:8s} | "
              f"      {agg('flat','h1',tier):.2f}  {agg('flat','h3',tier):.2f}  {agg('flat','h5',tier):.2f} "
              f"{agg('flat','mrr',tier):.2f} {agg('flat','ms',tier):5.1f} | "
              f"          {agg('tree_greedy','h1',tier):.2f} {agg('tree_greedy','mrr',tier):.2f} "
              f"{agg('tree_greedy','ms',tier):.3f}   "
              f"{agg('flat','n_pages',tier):.1f}/{agg('tree_greedy','n_pages',tier):.0f}  (n={n})")

    out = {'topk': TOPK, 'n_queries': len(rows), 'rows': rows}
    (HERE / 'results.json').write_text(json.dumps(out, indent=2))
    print(f"\n✓ results.json written")


if __name__ == '__main__':
    main()
