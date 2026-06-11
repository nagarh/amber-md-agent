#!/usr/bin/env python3
"""
build_subnodes.py — targeted depth fix. Split the handful of FAT leaf sections (the only
nodes that hurt retrieval) into sub-section children mined from body text.

The manual's printed TOC / PDF bookmarks stop at section level, but the deeper numbered
sub-headings (e.g. "36.11.68. rms") live in the page body. For each fat parent we scan its
page range for headings that start with the PARENT's number prefix (anchored -> no false
matches from citations/cross-refs) and turn them into child nodes with page sub-ranges.

Targets = the 7 leaves > 20 pages. Everything else (median 2 pages) is left untouched.

Run after build_tree.py + summarize.py + apply_summaries.py. Idempotent (skips parents that
already have children).
"""
import json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE / 'tree_index.json'
FLAT = HERE.parent / 'references' / 'amber_index.json'

# the fat parents to split (node_id -> section number prefix), from the >20-page list
TARGETS = {
    "0232": "36.11", "0274": "44.9", "0233": "36.12", "0091": "14.2",
    "0164": "25.3",  "0131": "21.6", "0139": "21.14",
}

MAXLEN = 260


def lead_summary(text, num):
    t = re.sub(r'^\s*' + re.escape(num) + r'\.\d+\.?\s+[^\n]*\n', '', text, count=1)
    lines = []
    for ln in t.splitlines():
        s = ln.strip()
        if len(s) < 25 and not s.endswith('.'):
            continue
        if re.match(r'^(\[|figure|table|•)', s, re.I):
            continue
        lines.append(s)
        if sum(len(x) for x in lines) > MAXLEN:
            break
    blob = re.sub(r'\s+', ' ', ' '.join(lines)).strip()
    if len(blob) > MAXLEN:
        cut = blob[:MAXLEN]; dot = cut.rfind('. ')
        blob = cut[:dot + 1] if dot > 80 else cut + '…'
    return blob


def find_subheadings(pages, prefix, lo, hi):
    """Return [(page, number, title)] for headings 'prefix.N[.M]. Title' within [lo,hi].
    Anchored to the parent prefix so citations/cross-refs don't match."""
    rx = re.compile(r'(?m)^\s*(' + re.escape(prefix) + r'\.\d+(?:\.\d+)?)\.\s+'
                    r'([A-Za-z][A-Za-z0-9 ,/()\-\.|+]{2,55}?)\s*$')
    found = {}
    for pno in range(lo, hi + 1):
        for m in rx.finditer(pages.get(pno, '')):
            num = m.group(1)
            title = m.group(2).strip().rstrip('.')
            if num not in found and len(title) >= 3:
                found[num] = (pno, num, title)
    # sort by numeric key
    def key(item):
        return tuple(int(x) for x in item[1].split('.'))
    return sorted(found.values(), key=key)


def main():
    tree = json.loads(TREE.read_text())
    pages = {p['page_num']: p['text'] for p in json.loads(FLAT.read_text())['pages']}

    nodes = {}
    def index(n):
        nodes[n['node_id']] = n
        for c in n['nodes']:
            index(c)
    index(tree['root'])

    next_id = max(int(nid) for nid in nodes) + 1
    report = []

    for pid, prefix in TARGETS.items():
        parent = nodes.get(pid)
        if parent is None:
            print(f"!! {pid} not found"); continue
        if parent['nodes']:
            print(f"-- {pid} ({prefix}) already split, skipping"); continue

        subs = find_subheadings(pages, prefix, parent['start_index'], parent['end_index'])
        if len(subs) < 2:
            print(f"-- {pid} ({prefix}): only {len(subs)} sub-headings — leaving as leaf")
            continue

        children = []
        for i, (pno, num, title) in enumerate(subs):
            start = pno
            end = subs[i + 1][0] - 1 if i + 1 < len(subs) else parent['end_index']
            end = max(start, end)
            txt = pages.get(start, '')
            child = {
                'title': f"{num}. {title}",
                'node_id': f"{next_id:04d}",
                'start_index': start, 'end_index': end,
                'summary': lead_summary(txt, prefix), 'nodes': [],
            }
            next_id += 1
            children.append(child)
        parent['nodes'] = children
        report.append((pid, prefix, parent['end_index'] - parent['start_index'] + 1, len(children)))
        print(f"++ {pid} ({prefix}): {report[-1][2]}p -> {len(children)} sub-nodes "
              f"(e.g. {children[0]['title'][:30]} ... {children[-1]['title'][:30]})")

    TREE.write_text(json.dumps(tree, indent=2))

    # new leaf stats
    leaves = []
    def walk(n):
        if not n['nodes']:
            leaves.append(n)
        for c in n['nodes']:
            walk(c)
    walk(tree['root'])
    import statistics
    sizes = [l['end_index'] - l['start_index'] + 1 for l in leaves]
    print(f"\n✓ tree updated. leaves: {len(leaves)} | median {statistics.median(sizes)}p | "
          f"max {max(sizes)}p | >20p: {sum(1 for s in sizes if s > 20)}")


if __name__ == '__main__':
    main()
