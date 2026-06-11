# Tree_RAG — reasoning-based PageIndex for the Amber manual

Re-implements the **VectifyAI PageIndex** method (https://github.com/VectifyAI/PageIndex):
a hierarchical tree of document nodes, navigated at query time by an LLM that reasons
over node titles/summaries — **no embeddings, no vector DB**. "similarity ≠ relevance."

## Difference from the existing flat RAG
- `scripts/rag_amber.py` = flat lexical TF-IDF over 1034 page-chunks (scans ALL pages).
- `Tree_RAG/` = hierarchical tree; an LLM walks Part → Chapter → Section → pages.

## LLM backend = agent-native
Both Anthropic and OpenAI keys are dead in this environment. So:
- **Build** (`build_tree.py`) uses NO LLM — it parses the manual's *printed* Table of
  Contents (already present as text in `references/amber_index.json`, pages 5–11) into a
  clean tree. Deterministic.
- **Traversal** (query time) is done by **Claude Code itself** acting as the reasoning LLM,
  via the read-only tools in `tree_rag.py`. Same PageIndex *method*, the agent is the LLM
  instead of gpt-4o.

## Node schema (Vectify-exact)
```json
{ "title": "Proteins", "node_id": "0007",
  "start_index": 34, "end_index": 38,
  "summary": "", "nodes": [ ...children ] }
```
`start_index`/`end_index` are **printed page numbers** (== JSON `page_num`; offset 0, verified).
Page text is NOT duplicated into the tree — pulled live from `amber_index.json` by range.

## Files
- `build_tree.py`  — parse printed TOC → `tree_index.json` (Vectify schema). No LLM.
- `tree_rag.py`    — read-only navigation tools: `toc`, `children NODE_ID`, `pages NODE_ID`,
                     `find TEXT`. The agent uses these to traverse and answer.
- `tree_index.json`— the built tree.

## Query flow (agent-native traversal)
```
children(root) → Parts → pick → children → Chapters → pick → children → Sections
→ pick leaf → pages(node) → read full text → answer + reasoning chain
```

## Verify after build
- page ranges monotonic & within [1, n_pages]
- leaf count ≈ number of TOC sections
- spot-check: 3 sections' first page text contains the section title
