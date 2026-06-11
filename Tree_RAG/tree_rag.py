#!/usr/bin/env python3
"""
tree_rag.py — read-only navigation tools for the Amber-manual PageIndex tree.

This is the QUERY side of the VectifyAI-PageIndex method. There is no scoring and no
embedding here: the tool only exposes the tree so that an LLM (here, Claude Code itself)
can do REASONING-BASED tree search — read child titles, decide which branch is relevant,
descend, and finally read the leaf pages.

Commands:
    python tree_rag.py toc                  # print the whole tree, indented
    python tree_rag.py children 0000        # list a node's direct children (start at root 0000)
    python tree_rag.py node 0094            # show one node's metadata + its children
    python tree_rag.py pages 0094           # full manual text for that node's page range
    python tree_rag.py find "umbrella"      # grep node TITLES (a jump-start, not the search)

The intended loop (agent as the LLM):
    children 0000  ->  pick a Part  ->  children <part>  ->  pick a Chapter
    ->  children <chapter>  ->  pick a Section  ->  pages <section>  ->  read & answer
"""
import json
import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE / 'tree_index.json'
FLAT = HERE.parent / 'references' / 'amber_index.json'


def load_tree():
    return json.loads(TREE.read_text())


def _index_nodes(root):
    """node_id -> node dict."""
    out = {}
    def walk(n):
        out[n['node_id']] = n
        for c in n['nodes']:
            walk(c)
    walk(root)
    return out


def load_pages():
    data = json.loads(FLAT.read_text())
    return {p['page_num']: p['text'] for p in data['pages']}


# ── commands ────────────────────────────────────────────────────────────────────

def cmd_toc(root, max_depth=99):
    def walk(n, d=0):
        if d > max_depth:
            return
        pad = '  ' * d
        rng = f"p{n['start_index']}-{n['end_index']}"
        print(f"{pad}[{n['node_id']}] {n['title']}  ({rng})")
        for c in n['nodes']:
            walk(c, d + 1)
    walk(root)


def cmd_children(nodes, node_id):
    n = nodes.get(node_id)
    if not n:
        print(f"node {node_id} not found"); return
    print(f"[{n['node_id']}] {n['title']}  (p{n['start_index']}-{n['end_index']})")
    if not n['nodes']:
        print("  (leaf — no children; use `pages` to read it)"); return
    for c in n['nodes']:
        s = f"  [{c['node_id']}] {c['title']}  (p{c['start_index']}-{c['end_index']})"
        if c['summary']:
            s += f"\n      {c['summary']}"
        print(s)


def cmd_node(nodes, node_id):
    n = nodes.get(node_id)
    if not n:
        print(f"node {node_id} not found"); return
    meta = {k: n[k] for k in ('node_id', 'title', 'start_index', 'end_index', 'summary')}
    meta['n_children'] = len(n['nodes'])
    print(json.dumps(meta, indent=2))


def cmd_pages(nodes, node_id, pages):
    n = nodes.get(node_id)
    if not n:
        print(f"node {node_id} not found"); return
    print(f"═══ [{n['node_id']}] {n['title']}  (pages {n['start_index']}-{n['end_index']}) ═══\n")
    for pno in range(n['start_index'], n['end_index'] + 1):
        txt = pages.get(pno)
        if not txt:
            continue
        print(f"───────────── page {pno} ─────────────")
        print(txt.rstrip())
        print()


def cmd_find(nodes, needle):
    needle = needle.lower()
    hits = [n for n in nodes.values() if needle in n['title'].lower()]
    if not hits:
        print(f"no node title contains {needle!r}"); return
    print(f"{len(hits)} node titles match {needle!r}:")
    for n in sorted(hits, key=lambda x: x['start_index']):
        print(f"  [{n['node_id']}] {n['title']}  (p{n['start_index']}-{n['end_index']})")


def main():
    ap = argparse.ArgumentParser(description="Navigate the Amber PageIndex tree")
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('toc');      p.add_argument('--max-depth', type=int, default=99)
    p = sub.add_parser('children'); p.add_argument('node_id')
    p = sub.add_parser('node');     p.add_argument('node_id')
    p = sub.add_parser('pages');    p.add_argument('node_id')
    p = sub.add_parser('find');     p.add_argument('needle')
    args = ap.parse_args()

    tree = load_tree()
    root = tree['root']
    nodes = _index_nodes(root)

    if args.cmd == 'toc':
        cmd_toc(root, args.max_depth)
    elif args.cmd == 'children':
        cmd_children(nodes, args.node_id)
    elif args.cmd == 'node':
        cmd_node(nodes, args.node_id)
    elif args.cmd == 'pages':
        cmd_pages(nodes, args.node_id, load_pages())
    elif args.cmd == 'find':
        cmd_find(nodes, args.needle)


if __name__ == '__main__':
    main()
