#!/usr/bin/env python3
"""
build_tree.py — Build a VectifyAI-PageIndex-style hierarchical tree for the Amber
manual from the manual's PRINTED table of contents.

No LLM. No embeddings. Deterministic.

Source of truth: references/amber_index.json (the existing flat page index). Its early
pages contain the manual's printed Contents (page numbers == JSON page_num, offset 0).
We parse that into a tree of nodes:

    Part (I, II, ...)  →  Chapter (1, 2, ...)  →  Section (3.1, ...)  →  Subsection (3.1.1)

Node schema (Vectify-exact):
    { "title", "node_id", "start_index", "end_index", "summary", "nodes": [...] }

start_index / end_index = printed page numbers (inclusive).

Usage:
    python build_tree.py
    python build_tree.py --json ../references/amber_index.json --out tree_index.json
"""
import json
import re
import argparse
from pathlib import Path

# ── TOC line patterns ───────────────────────────────────────────────────────────
# Trailing integer = the printed page number. Dot-leaders (". . .") may precede it.
RE_PART = re.compile(r'^([IVXLCDM]+)\.\s+(.+?)[\s.]*\s(\d+)\s*$')
RE_CHAP = re.compile(r'^(\d+)\.\s+(.+?)[\s.]*\s(\d+)\s*$')
RE_SEC  = re.compile(r'^(\d+\.\d+)\.\s+(.+?)[\s.]*\s(\d+)\s*$')
RE_SUB  = re.compile(r'^(\d+\.\d+\.\d+)\.\s+(.+?)[\s.]*\s(\d+)\s*$')


def _clean_title(t):
    """Strip trailing dot-leaders and whitespace from a TOC title."""
    return re.sub(r'[\s.]+$', '', t).strip()


def find_toc_pages(pages):
    """Return the contiguous run of pages that make up the printed Contents.

    Heuristic: a TOC page has many lines ending in a page number, and the first one
    literally begins with 'Contents'. We start at that page and extend while pages
    stay TOC-dense.
    """
    def trailing_num_lines(text):
        return len(re.findall(r'(?m)\S.*\s\d+\s*$', text))

    start = None
    for i, p in enumerate(pages):
        if p['text'].lstrip().lower().startswith('contents'):
            start = i
            break
    if start is None:
        raise RuntimeError("Could not locate the printed 'Contents' page.")

    end = start
    for i in range(start, len(pages)):
        if trailing_num_lines(pages[i]['text']) >= 8:
            end = i
        else:
            break
    return start, end


def parse_toc(pages, toc_start, toc_end):
    """Parse TOC page text into a flat ordered list of entries.

    Each entry: {level, number, title, page}. level in {part, chapter, section, sub}.
    """
    entries = []
    for i in range(toc_start, toc_end + 1):
        for raw in pages[i]['text'].splitlines():
            line = raw.strip()
            if not line or line.lower() in ('contents', 'contents 5'):
                continue
            # Order matters: most specific number pattern first.
            m = RE_SUB.match(line)
            if m:
                entries.append({'level': 'sub', 'number': m.group(1),
                                'title': _clean_title(m.group(2)), 'page': int(m.group(3))})
                continue
            m = RE_SEC.match(line)
            if m:
                entries.append({'level': 'section', 'number': m.group(1),
                                'title': _clean_title(m.group(2)), 'page': int(m.group(3))})
                continue
            m = RE_CHAP.match(line)
            if m:
                entries.append({'level': 'chapter', 'number': m.group(1),
                                'title': _clean_title(m.group(2)), 'page': int(m.group(3))})
                continue
            m = RE_PART.match(line)
            if m:
                entries.append({'level': 'part', 'number': m.group(1),
                                'title': _clean_title(m.group(2)), 'page': int(m.group(3))})
                continue
            # non-matching line (wrapped title, figure caption) — skip
    return entries


def dedupe_and_sort(entries):
    """The same TOC line can be parsed twice across overlapping page dumps; keep the
    first occurrence of each (level, number) and sort by printed page then number."""
    seen = set()
    uniq = []
    for e in entries:
        key = (e['level'], e['number'])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(e)
    uniq.sort(key=lambda e: (e['page'], _num_key(e['number'])))
    return uniq


def _num_key(number):
    """Sort key for a TOC number. Roman parts sort by value; numeric by tuple."""
    if re.fullmatch(r'[IVXLCDM]+', number):
        return (_roman(number),)
    return tuple(int(x) for x in number.split('.'))


def _roman(s):
    vals = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    total, prev = 0, 0
    for ch in reversed(s):
        v = vals[ch]
        total += -v if v < prev else v
        prev = max(prev, v)
    return total


def build_tree(entries, n_pages):
    """Turn the flat ordered TOC entries into a nested tree.

    end_index for each node = (start of the next entry in flat order) - 1, then each
    parent's end_index is extended to cover its last descendant.
    """
    # First assign a provisional end_index from the next entry's start page.
    for i, e in enumerate(entries):
        nxt = entries[i + 1]['page'] if i + 1 < len(entries) else n_pages + 1
        e['end'] = max(e['page'], nxt - 1)

    root = {'title': 'Amber Reference Manual', 'node_id': '0000',
            'start_index': 1, 'end_index': n_pages, 'summary': '', 'nodes': []}

    counter = [0]

    def new_node(e):
        counter[0] += 1
        return {'title': f"{e['number']}. {e['title']}",
                'node_id': f"{counter[0]:04d}",
                'start_index': e['page'], 'end_index': e['end'],
                'summary': '', 'nodes': []}

    cur_part = cur_chap = cur_sec = None
    for e in entries:
        node = new_node(e)
        if e['level'] == 'part':
            root['nodes'].append(node); cur_part = node; cur_chap = cur_sec = None
        elif e['level'] == 'chapter':
            parent = cur_part or root
            parent['nodes'].append(node); cur_chap = node; cur_sec = None
        elif e['level'] == 'section':
            parent = cur_chap or cur_part or root
            parent['nodes'].append(node); cur_sec = node
        else:  # sub
            parent = cur_sec or cur_chap or cur_part or root
            parent['nodes'].append(node)

    _fix_parent_ends(root)
    return root


def _fix_parent_ends(node):
    """Extend each parent's end_index to cover its children (depth-first)."""
    if node['nodes']:
        for c in node['nodes']:
            _fix_parent_ends(c)
        node['end_index'] = max(node['end_index'], max(c['end_index'] for c in node['nodes']))
    return node['end_index']


def main():
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description="Build PageIndex tree from the Amber manual TOC")
    ap.add_argument('--json', default=str(here.parent / 'references' / 'amber_index.json'),
                    help='Path to the flat amber_index.json')
    ap.add_argument('--out', default=str(here / 'tree_index.json'))
    args = ap.parse_args()

    data = json.loads(Path(args.json).read_text())
    pages = data['pages']
    n_pages = max(p['page_num'] for p in pages)

    toc_start, toc_end = find_toc_pages(pages)
    print(f"TOC pages: index {toc_start}..{toc_end} "
          f"(printed {pages[toc_start]['page_num']}..{pages[toc_end]['page_num']})")

    entries = dedupe_and_sort(parse_toc(pages, toc_start, toc_end))
    levels = {}
    for e in entries:
        levels[e['level']] = levels.get(e['level'], 0) + 1
    print(f"Parsed {len(entries)} TOC entries: {levels}")

    tree = build_tree(entries, n_pages)

    out = {'source': pages[0]['source'], 'n_pages': n_pages, 'method': 'VectifyAI-PageIndex (agent-native)',
           'root': tree}
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(f"✓ Tree written: {args.out}")

    # quick shape report
    def count(n):
        return 1 + sum(count(c) for c in n['nodes'])
    def leaves(n):
        return 1 if not n['nodes'] else sum(leaves(c) for c in n['nodes'])
    print(f"  total nodes: {count(tree)}  |  leaves: {leaves(tree)}  |  top-level parts/chapters: {len(tree['nodes'])}")


if __name__ == '__main__':
    main()
