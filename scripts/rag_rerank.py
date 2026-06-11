#!/usr/bin/env python
"""
Enhanced Amber-manual retrieval: passage-scoring (precision) + LLM rerank (semantic).

Additive layer over rag_amber.PageIndex — does NOT modify the existing lexical path.

Pipeline:
  1. Recall  : score sliding-word-window PASSAGES across every page (TF-IDF, idf reused
               from the page index). page_score = best passage score. A page that only
               *mentions* a term in passing scores low; a page with a passage *about* it
               scores high. -> fixes dense-token false positives. (option 3)
  2. Rerank  : send the top-N candidate snippets to an LLM, which ranks by true semantic
               relevance and returns the top_k. No hardcoded synonyms — the model bridges
               vocabulary gaps. (option 2)

The recall stage is deliberately HIGH-RECALL (large pool) so the rerank has the gold
candidate to promote; the rerank stage supplies precision.
"""
import json, re, math, sys, os, urllib.request, urllib.error
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rag_amber import PageIndex, tokenize, AMBER_TERMS

DEFAULT_INDEX = str(Path(__file__).resolve().parent.parent / "references" / "amber_index.json")
RERANK_MODEL = "claude-haiku-4-5-20251001"   # cheap/fast for relevance judgement


# ── option 3: passage-level scoring ────────────────────────────────────────────
def _windows(text, size=120, stride=80):
    """Sliding word-windows — robust to PDF paragraph mangling."""
    words = text.split()
    if len(words) <= size:
        return [text]
    return [" ".join(words[i:i + size]) for i in range(0, len(words) - size + stride, stride)]


def _passage_score(q_tokens, passage_text, idf):
    toks = tokenize(passage_text)
    if not toks:
        return 0.0
    tf = Counter(toks)
    score = 0.0
    for t in q_tokens:
        c = tf.get(t, 0)
        if c:
            s = (1 + math.log(c)) * idf.get(t, 0)
            if t in AMBER_TERMS:
                s *= 2.0
            score += s
    return score


def passage_recall(index, question, pool=20):
    """Return up to `pool` candidate pages, each with its best-matching passage."""
    q_tokens = tokenize(question)
    if not q_tokens:
        return []
    cands = []
    for p in index.pages:
        best_s, best_w = 0.0, ""
        for w in _windows(p["text"]):
            s = _passage_score(q_tokens, w, index.idf)
            if s > best_s:
                best_s, best_w = s, w
        if best_s > 0:
            cands.append({
                "page": p["page_num"], "source": p["source"],
                "section_path": p.get("section_path", ""),
                "best_passage": best_w, "text": p["text"],
                "passage_score": round(best_s, 2),
            })
    cands.sort(key=lambda c: -c["passage_score"])
    return cands[:pool]


# ── option 2: LLM rerank ────────────────────────────────────────────────────────
def _anthropic(messages, model=RERANK_MODEL, max_tokens=400):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    body = json.dumps({"model": model, "max_tokens": max_tokens, "messages": messages}).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["content"][0]["text"]


def llm_rerank(question, candidates, top_k=3):
    """Rank candidate passages by relevance to the question; return reordered top_k."""
    if not candidates:
        return []
    lines = []
    for i, c in enumerate(candidates):
        snip = c["best_passage"][:600].replace("\n", " ")
        lines.append(f"[{i}] (p.{c['page']}, {c['section_path'][:60]}) {snip}")
    prompt = (
        "You rank Amber MD manual passages by how well they ANSWER the question. "
        "Judge meaning, not keyword overlap. A passage that merely mentions a term in a "
        "different context is NOT relevant.\n\n"
        f"QUESTION: {question}\n\nCANDIDATES:\n" + "\n".join(lines) +
        f"\n\nReturn ONLY a JSON array of the {top_k} most relevant candidate indices, "
        "best first, e.g. [3,0,7]. No prose.")
    txt = _anthropic([{"role": "user", "content": prompt}])
    m = re.search(r"\[[\d,\s]*\]", txt)
    order = json.loads(m.group(0)) if m else list(range(min(top_k, len(candidates))))
    out = []
    for idx in order:
        if 0 <= idx < len(candidates) and candidates[idx] not in out:
            out.append(candidates[idx])
        if len(out) >= top_k:
            break
    return out


# ── full pipeline ────────────────────────────────────────────────────────────────
_INDEX = None
def get_index(index_path=None):
    global _INDEX
    if _INDEX is None:
        _INDEX = PageIndex()
        _INDEX.load(index_path or DEFAULT_INDEX)
    return _INDEX


def enhanced_query(question, top_k=3, pool=20, rerank=True, index_path=None):
    idx = get_index(index_path)
    cands = passage_recall(idx, question, pool=pool)
    if rerank and cands:
        ranked = llm_rerank(question, cands, top_k=top_k)
    else:
        ranked = cands[:top_k]
    return [{"page": c["page"], "source": c["source"], "section_path": c["section_path"],
             "passage_score": c["passage_score"], "snippet": c["best_passage"][:300],
             "text": c["text"]} for c in ranked]


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "what cutoff for PME"
    for r in enhanced_query(q):
        print(f"\n[p.{r['page']} score {r['passage_score']}] {r['section_path'][:70]}")
        print("  " + r["snippet"][:200].replace("\n", " "))
