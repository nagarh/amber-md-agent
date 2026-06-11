#!/usr/bin/env python3
"""
summarize.py — fill node `summary` fields in tree_index.json.

No working LLM API in this environment (Anthropic 401, OpenAI absent, Gemini 429). So this
script produces a DETERMINISTIC EXTRACTIVE summary for every node from its lead text — the
first 1-2 clean sentences of the node's page range, taken from references/amber_index.json.

It is a baseline. The agent (Claude Code) then overwrites the high-value DECISION nodes
(parts + chapters) with proper reasoned summaries via `apply_summaries.py`.

Usage:
    python summarize.py                 # writes summaries into tree_index.json in place
    python summarize.py --dry-run       # print what it would set, don't write
"""
import json, re, argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE / 'tree_index.json'
FLAT = HERE.parent / 'references' / 'amber_index.json'

MAXLEN = 280


def lead_summary(text, title):
    """Extract the first 1-2 sentences of `text` that look like prose, skipping the title
    line and obvious headers/citations."""
    # drop the leading chapter/section number echo (e.g. "26. Constant pH calculations")
    t = re.sub(r'^\s*\d+(\.\d+)*\.\s+.*?\n', '', text, count=1)
    # also drop a bare repeat of the title
    short = re.sub(r'[^a-z]', '', title.lower())[:20]
    lines = []
    for ln in t.splitlines():
        s = ln.strip()
        if not s:
            continue
        if len(s) < 25 and not s.endswith('.'):     # heading-ish
            continue
        if re.match(r'^(\[|figure|table|•|\d+\.\d+\.)', s, re.I):
            continue
        if re.sub(r'[^a-z]', '', s.lower())[:20] == short:
            continue
        lines.append(s)
        if sum(len(x) for x in lines) > MAXLEN:
            break
    blob = ' '.join(lines)
    blob = re.sub(r'\s+', ' ', blob).strip()
    # cut at sentence boundary near MAXLEN
    if len(blob) > MAXLEN:
        cut = blob[:MAXLEN]
        dot = cut.rfind('. ')
        blob = cut[:dot + 1] if dot > 80 else cut + '…'
    return blob


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    tree = json.loads(TREE.read_text())
    pages = {p['page_num']: p['text'] for p in json.loads(FLAT.read_text())['pages']}

    n = [0]
    def fill(node):
        txt = ''.join(pages.get(p, '') for p in range(node['start_index'],
                                                       min(node['end_index'], node['start_index'] + 1) + 1))
        node['summary'] = lead_summary(txt, node['title'])
        n[0] += 1
        for c in node['nodes']:
            fill(c)
    fill(tree['root'])

    if args.dry_run:
        def show(node, d=0):
            print('  ' * d + f"[{node['node_id']}] {node['title'][:40]}")
            print('  ' * d + f"    → {node['summary'][:120]}")
            for c in node['nodes'][:3]:
                show(c, d + 1)
        for part in tree['root']['nodes']:
            show(part, 0)
        print(f"\n(dry-run) would set {n[0]} summaries")
        return

    TREE.write_text(json.dumps(tree, indent=2))
    print(f"✓ set extractive summary on {n[0]} nodes → {TREE.name}")


if __name__ == '__main__':
    main()
