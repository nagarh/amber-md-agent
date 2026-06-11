#!/usr/bin/env python3
"""
PubMed / Europe PMC MCP Server for AmberMD Agent.

Gives the agent literature awareness for:
- Step 2 (RAG query stage): find published MD protocols for the system
- Step 4 (Plan stage): ground sim length / FF choice / observables in real practice
- Step 7 (STUDY_REPORT §9): compare measured values to published results

Uses Europe PMC REST API (free, no key required).
Docs: https://europepmc.org/RestfulWebService

Run: python pubmed_server.py
     python pubmed_server.py --test
"""

import json
import sys
import urllib.request
import urllib.parse
from typing import Optional

from fastmcp import FastMCP
from _common import http_get, error_response, get_logger

logger = get_logger(__name__)

mcp = FastMCP("pubmed-server")

EUROPMC_API = "https://www.ebi.ac.uk/europepmc/webservices/rest"


# ─── Tool Implementations ───────────────────────────────────────────────────

def _search_literature_impl(query: str, limit: int = 10, year_from: Optional[int] = None,
                             year_to: Optional[int] = None, open_access_only: bool = False) -> dict:
    """Internal implementation of search_literature."""
    q = query.strip()
    if year_from or year_to:
        yr_from = year_from or 1900
        yr_to = year_to or 9999
        q = f"({q}) AND (PUB_YEAR:[{yr_from} TO {yr_to}])"
    if open_access_only:
        q = f"({q}) AND OPEN_ACCESS:Y"

    # M-12 fix: clamp limit to valid range 1-100
    limit = max(1, min(limit, 100))
    params = {
        "query": q,
        "resultType": "core",
        "format": "json",
        "pageSize": limit,
    }
    url = f"{EUROPMC_API}/search?{urllib.parse.urlencode(params)}"
    data = http_get(url)
    if "error" in data:
        # M-13 fix: error response must include count/results keys for API consistency
        return {"error": data["error"], "query": q, "count": 0, "total_hits": 0, "results": []}

    results = []
    for hit in (data.get("resultList") or {}).get("result", []):
        author_string = hit.get("authorString", "")
        # M-14 fix: isinstance guard before .split() — authorString may not be str
        if isinstance(author_string, str) and author_string:
            first_author = author_string.split(",")[0].strip() or None
        else:
            first_author = None
            author_string = ""
        results.append({
            "pmid": hit.get("pmid"),
            "pmcid": hit.get("pmcid"),
            "doi": hit.get("doi"),
            "title": hit.get("title"),
            "abstract": hit.get("abstractText"),
            "journal": hit.get("journalTitle"),
            "year": hit.get("pubYear"),
            "first_author": first_author,
            "author_string": author_string,
            "citation_count": hit.get("citedByCount"),
            # L-02: API may return bool or string — accept both via str().upper() coercion
            "has_full_text": (str(hit.get("hasTextMinedTerms")).upper() == "Y" or
                              str(hit.get("inEPMC")).upper() == "Y"),
            "source": hit.get("source"),  # MED, PMC, etc.
        })
    return {
        "count": len(results),
        "total_hits": data.get("hitCount"),
        "query": q,
        "results": results,
    }


@mcp.tool()
def search_literature(query: str, limit: int = 10, year_from: Optional[int] = None,
                      year_to: Optional[int] = None, open_access_only: bool = False) -> dict:
    """Search Europe PMC for papers matching a free-text query.
    Use for Step 2 (find published MD protocols) and Step 7 (compare measured values).

    Args:
        query: free-text query, e.g. "HIV-1 protease flap molecular dynamics"
        limit: max number of papers to return (default 10)
        year_from: optional minimum publication year
        year_to: optional maximum publication year
        open_access_only: if True, filter to open-access papers with full text

    Returns:
        dict with:
            count: number of papers returned
            query: actual query string used
            results: list of paper records
                pmid, doi, title, abstract (if present), journal, year,
                first_author, citation_count, has_full_text
    """
    return _search_literature_impl(query, limit, year_from, year_to, open_access_only)


@mcp.tool()
def get_abstract(pmid: str) -> dict:
    """Fetch abstract + metadata for a single PMID.

    Returns dict: title, abstract, authors, journal, year, doi, pmid, pmcid.
    Returns dict with 'error' if not found.
    """
    pmid = str(pmid).strip()
    url = f"{EUROPMC_API}/article/MED/{pmid}?resultType=core&format=json"
    data = http_get(url)
    # M-15 fix: error response includes same schema keys with None values for API consistency
    _EMPTY_ABSTRACT = {"pmid": pmid, "pmcid": None, "doi": None, "title": None,
                       "abstract": None, "authors": None, "journal": None, "year": None,
                       "citation_count": None}
    if "error" in data:
        return {**_EMPTY_ABSTRACT, "error": data["error"]}
    result = data.get("result")
    if not result:
        return {**_EMPTY_ABSTRACT, "error": "not_found"}
    return {
        "pmid": result.get("pmid"),
        "pmcid": result.get("pmcid"),
        "doi": result.get("doi"),
        "title": result.get("title"),
        "abstract": result.get("abstractText"),
        "authors": result.get("authorString"),
        "journal": result.get("journalTitle"),
        "year": result.get("pubYear"),
        "citation_count": result.get("citedByCount"),
    }


@mcp.tool()
def get_full_text(pmcid: str) -> dict:
    """Fetch open-access full text XML for a PMCID (when available).

    Args:
        pmcid: e.g. "PMC1234567" or "1234567"

    Returns:
        dict with 'xml' field on success, or 'error'.
        Caller should parse XML for sections (Methods, Results, etc.).
    """
    pmcid = str(pmcid).strip()
    if not pmcid.startswith("PMC"):
        pmcid = f"PMC{pmcid}"
    url = f"{EUROPMC_API}/{pmcid}/fullTextXML"
    data = http_get(url, accept="application/xml", return_text_on_parse_fail=True)
    if isinstance(data, dict) and "error" in data:
        return data
    if isinstance(data, dict) and "raw_text" in data:
        xml_text = data["raw_text"]
        if not xml_text or len(xml_text) < 100:
            return {"error": "no_full_text", "pmcid": pmcid}
        return {"pmcid": pmcid, "xml": xml_text, "length": len(xml_text)}
    # H-18 fix: `data` is always a dict per http_get contract; len(dict) counts keys, not bytes.
    # Validate the actual text content length instead.
    raw = data if isinstance(data, str) else str(data)
    if len(raw) < 100:
        return {"error": "no_full_text", "pmcid": pmcid}
    return {"pmcid": pmcid, "xml": raw, "length": len(raw)}


@mcp.tool()
def format_citation(record: dict, style: str = "amber-report") -> str:
    """Format a paper record as a citation string.

    Args:
        record: a result entry from search_literature() or get_abstract()
        style: "amber-report" (compact), "full" (with abstract)

    Returns:
        formatted string suitable for STUDY_REPORT.md §11 References
    """
    # M-16 fix: isinstance check before "error" in record — record could be non-dict
    if not record or not isinstance(record, dict) or "error" in record:
        return "[unavailable]"
    authors = record.get("first_author") or record.get("authors") or ""
    if authors:
        authors = f"{authors} et al."
    title = (record.get("title") or "").strip().rstrip(".")
    journal = record.get("journal") or ""
    year = record.get("year") or ""
    doi = record.get("doi") or ""
    pmid = record.get("pmid") or ""
    if style == "amber-report":
        # Author et al., Journal Year. DOI:.. PMID:..
        base = f"{authors}, {title}. {journal} {year}".strip()
        ids = []
        if doi:
            ids.append(f"doi:{doi}")
        if pmid:
            ids.append(f"PMID:{pmid}")
        return base + (" " + " ".join(ids) if ids else "")
    elif style == "full":
        abs_ = (record.get("abstract") or "")[:500]
        return f"{authors}, {title}. {journal} {year}\nPMID:{pmid} DOI:{doi}\nAbstract: {abs_}"
    return f"{authors} ({year}) {title}"


@mcp.tool()
def search_protocol(system_keywords: str, simulation_type: str = "molecular dynamics",
                    n: int = 10, year_from: int = 2000) -> dict:
    """Convenience: search for published MD protocols for a specific system.

    Args:
        system_keywords: e.g. "HIV-1 protease apo" or "Abl kinase imatinib"
        simulation_type: "molecular dynamics", "free energy", "MMPBSA", "TI", etc.
        n: max results
        year_from: only papers from this year forward

    Returns same format as search_literature().
    """
    q = f"{system_keywords} {simulation_type}"
    return _search_literature_impl(q, limit=n, year_from=year_from)


@mcp.tool()
def compare_to_literature(observable_keyword: str, system_keyword: str, n: int = 5) -> dict:
    """Find papers reporting a specific observable for a specific system.
    Use at Step 7 to find published values for comparison.
    Example: compare_to_literature("flap tip distance", "HIV-1 protease")
    """
    q = f"{system_keyword} {observable_keyword}"
    return _search_literature_impl(q, limit=n, year_from=2000)


def _self_test():
    logger.debug("=== Test 1: search_literature ===")
    r = search_literature("HIV-1 protease flap molecular dynamics", limit=3)
    if "error" in r:
        logger.debug(f"ERROR: {r['error']}"); return False
    logger.debug(f"  Total hits: {r.get('total_hits')}, returned {r['count']}")
    for paper in r["results"]:
        logger.debug(f"  - {paper['year']}  {paper['title'][:80]}")
    logger.debug("=== Test 2: format_citation ===")
    if r["results"]:
        logger.debug(f"  {format_citation(r['results'][0])[:200]}")
    logger.debug("=== Test 3: compare_to_literature ===")
    r2 = compare_to_literature("flap tip distance", "HIV-1 protease", n=2)
    logger.debug(f"  Total hits: {r2.get('total_hits')}, returned {r2['count']}")
    return True


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.exit(0 if _self_test() else 1)
    mcp.run()
