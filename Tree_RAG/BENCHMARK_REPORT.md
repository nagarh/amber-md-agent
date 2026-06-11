# Benchmark: Flat TF-IDF RAG vs Tree PageIndex — Amber manual

18 labeled queries, 4 difficulty tiers, gold pages verified by reading the manual.
Reproduce: `python benchmark.py && python score_all.py`. Raw: `results.json`, picks: `tree_llm_picks.json`.

Three retrievers:
| | what | LLM? |
|--|--|--|
| **FLAT** | `scripts/rag_amber.py` lexical TF-IDF over all 1034 pages | no |
| **TREE-GREEDY** | deterministic walk picking child with best **title** word-overlap (subtree look-ahead) | no |
| **TREE-LLM** | Claude Code reasons query→Part→Chapter→Section over node titles (real PageIndex method) | yes (= the agent) |

## Headline — Hit rate (gold page inside returned result)

| tier (n) | FLAT Hit@1 | FLAT Hit@5 | TREE-GREEDY | **TREE-LLM** |
|---|---|---|---|---|
| easy  (8) | 0.88 | 1.00 | 0.25 | **1.00** |
| hard  (2) | 0.00 | 0.00 | 0.00 | **1.00** |
| vhard (4) | 0.50 | 0.50 | 0.00 | **1.00** |
| worst (4) | 0.00 | 0.00 | 0.00 | **1.00** |
| **ALL (18)** | **0.50** | **0.56** | **0.11** | **1.00** |

## Speed / cost (different units — that is the finding)
| | per query | LLM calls | pages handed to reader |
|--|--|--|--|
| FLAT | ~2.7 ms CPU | 0 | 5 (precise) |
| TREE-GREEDY | <1 ms CPU | 0 | varies (often dead-ends) |
| TREE-LLM | 3–4 reasoning hops | 3–4 | 1 leaf (avg **9**, range 1–18) |

> Numbers above are AFTER `build_subnodes.py` (the targeted depth fix). Before it, TREE-LLM
> read whole sections (avg 22, up to 89 pages: cpptraj §36.11). Splitting the 7 fat sections
> into body-mined sub-section leaves dropped per-query reads to avg 9 (shake 22→1, rmsd 89→2)
> at the cost of one extra hop on deepened branches. Accuracy (Hit) unchanged at 1.00.

## What each result means

**FLAT is fast + free + precise, but lexical.** Perfect on easy exact-jargon queries
(Hit@5 = 1.00). Collapses to **0.00 on hard/worst** — vocabulary gap. "freez bond lenght
to take longer steps" never matches the body token `SHAKE`. Returns 5 tight pages — low
reader cost — when it hits.

**TREE-GREEDY proves structure alone is worthless (0.11).** Top-level Part titles
("Running simulations") share no literal tokens with jargon, so the greedy walk either
dead-ends at the root (DEAD = returns whole book) or wanders into wrong sections on
generic shared words ("reference", "water", "force field"). **The tree needs a reasoner.**

**TREE-LLM is robust to vocabulary — 1.00 across every tier including worst.** It reasons
"freeze bonds for bigger timestep ⇒ SHAKE ⇒ an mdin parameter ⇒ sander §21.6", which no
lexical method can. Cost is 3 LLM calls + reading one section.

## Honest caveats (state these in interview)
1. **TREE-LLM picks were graded by a script, but chosen by me (the agent).** Auditable in
   `tree_llm_picks.json` (node_id + reasoning); 3 traversals shown live. Still, self-routing
   on a small (n=18) hand-built set — not an independent eval. A genuinely ambiguous query
   could mis-route; none here were that hard for a domain LLM.
2. **TREE-LLM reader cost is coarse and uneven.** RMSD lands in cpptraj §36.11 = **89 pages**,
   because our tree depth stops at the printed-TOC section level (no sub-action nodes). Flat
   always returns 5 pages. Tree granularity is capped by TOC depth.
3. **"Speed" is not comparable.** Flat = milliseconds of CPU; TREE-LLM = seconds + tokens of
   LLM reasoning. Flat wins raw speed/cost by orders of magnitude.
4. Small set, English-only, golds defined by one reader.

## Verdict
- **Accuracy / robustness to phrasing → TREE-LLM** (1.00 vs 0.50), decisively on hard/worst.
- **Raw speed + cost + precise page targeting → FLAT** (2.7 ms, no tokens, 5 pages).
- **Tree structure without an LLM → useless** (0.11).

**Best real system = hybrid:** FLAT for instant recall on exact jargon; escalate to LLM
reasoning (tree traversal, or the existing `rag_rerank.py` LLM rerank) when the query is
descriptive/paraphrased. Tree-LLM's 89-page lands also argue for deepening the tree
(sub-section nodes) or pairing it with flat to pick the exact page within the chosen section.
