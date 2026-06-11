# Tree_RAG — reasoning-based PageIndex for the Amber manual

A hierarchical, **tree-traversal** RAG over the Amber 24 manual, re-implementing the
[VectifyAI PageIndex](https://github.com/VectifyAI/PageIndex) method:
an LLM walks a tree of document nodes (Part → Chapter → Section), reasoning over titles
to pick the relevant branch. **No embeddings, no vector DB, no TF-IDF.**

Contrast with `../scripts/rag_amber.py` = flat lexical TF-IDF that scans all 1034 pages.

## Build
```bash
python build_tree.py          # 1. parse printed TOC -> tree skeleton (no LLM)
python summarize.py           # 2. extractive `summary` on every node (no LLM)
python apply_summaries.py     # 3. agent-authored summaries on root + 5 parts (decision tier)
python build_subnodes.py      # 4. split the few FAT sections into sub-section leaves (no LLM)
```
Deterministic, no API key. Source = `../references/amber_index.json` (the printed
Contents text lives in its early pages; page numbers map 1:1 to JSON `page_num`, offset 0).

Tree after step 3: 5 parts, 44 chapters, 225 sections (275 nodes, 226 leaves).
Tree after step 4: **541 nodes, 486 leaves** — median leaf **1 page**, only 1 leaf >20p
(ndfes §44.9, an unnumbered CLI-flag list that has no sub-headings to split on).

### Step 4 — targeted depth fix (build_subnodes.py)
The printed TOC and the PDF bookmarks both stop at section level, so a few big sections were
huge single leaves (cpptraj §36.11 = 89 pages). The deeper numbered sub-headings ("36.11.68.
rms") live in the page BODY, not the TOC. `build_subnodes.py` mines those headings inside the
7 fattest leaves only (anchored to the parent's section number so citations don't false-match)
and turns them into sub-section child nodes. Result: cpptraj actions, parmed commands, REMD
sub-topics, sander mdin groups, etc. each become a precise 1-2 page leaf. The other 219 small
leaves are left untouched.

### Summaries
Vectify nodes carry a `summary` the LLM reads to pick a branch. We have no working LLM API
(Anthropic 401, OpenAI absent, Gemini 429-quota), so summaries are produced WITHOUT a
programmatic LLM:
- **Every node** gets a deterministic *extractive* summary (lead sentences of its pages) via
  `summarize.py`. Chapter intros extract well; part divider pages have no prose.
- **Decision nodes** (root + the 5 parts — read first during traversal) are overwritten with
  *agent-authored* summaries in `apply_summaries.py`, each ending in a "Choose here for …"
  routing hint that names otherwise title-less topics (SHAKE, solvateBox, disulfide, PME).
- Leaf-section summaries stay extractive (titles + extract suffice once inside a chapter).
- TODO: upgrade the 44 chapter summaries + leaves to authored/LLM quality when an API key
  is available, or have the agent author them on demand.

## Query (agent-native traversal)
The reasoning LLM is **Claude Code itself**. It navigates with read-only tools:
```bash
python tree_rag.py children 0000     # root -> the 5 Parts
python tree_rag.py children 0124     # Part IV -> chapters
python tree_rag.py children 0169     # ch.26 -> sections
python tree_rag.py pages 0171        # read a leaf section's manual pages
python tree_rag.py toc --max-depth 1 # whole tree, shallow
python tree_rag.py find "umbrella"   # jump-start: grep node titles
```

### Worked example — "How do I set up constant pH MD?"
```
children 0000 -> pick "IV. Running simulations" (0124)
children 0124 -> pick "26. Constant pH calculations" (0169)
children 0169 -> pick "26.2 Preparing a system..." (0171)
pages 0171    -> manual text: edit HIS->HIP, ASP->AS4, source leaprc.constph, cpinutil.py ...
```
4 reasoning steps, 1 leaf read — no full-corpus scan.

## Node schema (Vectify-exact)
```json
{ "title": "26.2. Preparing a system for constant pH simulation",
  "node_id": "0171", "start_index": 580, "end_index": 582,
  "summary": "", "nodes": [] }
```
`summary` is left empty in v1 (titles alone navigate well for this manual). It can be
filled later — by the agent, or programmatically if a working LLM API key appears.

## Not done yet (follow-ups)
- node summaries (improves branch filtering on ambiguous queries)
- MCP wiring (expose `tree_children` / `tree_pages` as amber MCP tools)
- benchmark vs the flat TF-IDF RAG on a query set
