# Worst-to-worst test: Production FLAT RAG vs Tree PageIndex

10 adversarial queries: lay metaphors + typos, deliberately stripped of every Amber term
("thing that stops chemical bonds from wiggling" = SHAKE; "slowly make a drug dissapear to
get a binding strength number" = TI). Gold pages verified by reading the manual.
Reproduce: `python worst_test.py`.

## Result
| | FLAT (production `rag_amber.py`) | TREE-LLM (our PageIndex) |
|--|--|--|
| **Hit** | **0 / 10 (0%)** | **10 / 10 (100%)** |
| speed | ~2.7 ms CPU, 0 LLM calls | 3–4 LLM hops/query |
| pages handed to reader | 5 (exact) | ~10 (1 leaf) |

FLAT misses every one. The queries share no tokens with the body jargon, so lexical TF-IDF
matches noise: the SHAKE query returns paramfit + QM/MM pages (score ~13); the solvate and
disulfide queries land nowhere near. TREE-LLM reasons each paraphrase to the right section
(SHAKE→§21.6.9, TI→§25.1, REMD→§25.3) — vocabulary is irrelevant to a reasoning navigator.

## Honest caveats (do not overclaim)
1. **Metrics are asymmetric.** FLAT is graded on the exact gold page landing in its top-5.
   TREE-LLM is graded on its chosen *section range* overlapping gold — an easier bar, paid
   for in `pages_read` (REMD = a 27-page section the reader must still scan).
2. **REMD was a near-miss for FLAT, not a total loss.** FLAT returned p527/528, which sit
   *inside* the REMD section (25.3 = 521-547) but outside the narrow gold (521-523). With a
   section-level gold, FLAT would partially credit here. The other 9 are genuine whiffs.
3. **TREE-LLM = the agent itself**, routing its own hand-built n=10 set. Auditable (node_id +
   topic in `worst_test.py`), but not an independent eval. A domain LLM finds these trivial;
   a weaker model could mis-route.
4. Small set, English, one author's golds.

## Takeaway
On pure-paraphrase / typo queries — the realistic "user who doesn't know the jargon" case —
**lexical RAG collapses (0%) and reasoning-based tree traversal holds (100%)**. This is the
single strongest argument for the tree approach. The cost is LLM calls + reading a whole
section instead of 5 exact pages. Hybrid (tree picks the section, flat picks the page inside
it) would keep the 100% routing while cutting pages_read back toward 5.
