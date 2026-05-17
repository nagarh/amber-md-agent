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

EUROPMC_API = "https://www.ebi.ac.uk/europepmc/webservices/rest"


def _http_get(url, accept="application/json"):
    req = urllib.request.Request(
        url,
        headers={"Accept": accept, "User-Agent": "AmberMD-Agent/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read().decode()
            if accept == "application/json":
                try:
                    return json.loads(data)
                except json.JSONDecodeError:
                    return {"raw_text": data}
            return data
    except Exception as e:
        return {"error": str(e)}


# ─── Tool Implementations ───────────────────────────────────────────────────

def search_literature(query, limit=10, year_from=None, year_to=None,
                       open_access_only=False):
    """Search Europe PMC for papers matching a free-text query.

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
    q = query.strip()
    if year_from or year_to:
        yr_from = year_from or 1900
        yr_to = year_to or 9999
        q = f"({q}) AND (PUB_YEAR:[{yr_from} TO {yr_to}])"
    if open_access_only:
        q = f"({q}) AND OPEN_ACCESS:Y"

    params = {
        "query": q,
        "resultType": "core",
        "format": "json",
        "pageSize": min(limit, 100),
    }
    url = f"{EUROPMC_API}/search?{urllib.parse.urlencode(params)}"
    data = _http_get(url)
    if "error" in data:
        return {"error": data["error"], "query": q}

    results = []
    for hit in (data.get("resultList") or {}).get("result", []):
        results.append({
            "pmid": hit.get("pmid"),
            "pmcid": hit.get("pmcid"),
            "doi": hit.get("doi"),
            "title": hit.get("title"),
            "abstract": hit.get("abstractText"),
            "journal": hit.get("journalTitle"),
            "year": hit.get("pubYear"),
            "first_author": hit.get("authorString", "").split(",")[0].strip() or None,
            "author_string": hit.get("authorString"),
            "citation_count": hit.get("citedByCount"),
            "has_full_text": hit.get("hasTextMinedTerms") == "Y" or hit.get("inEPMC") == "Y",
            "source": hit.get("source"),  # MED, PMC, etc.
        })
    return {
        "count": len(results),
        "total_hits": data.get("hitCount"),
        "query": q,
        "results": results,
    }


def get_abstract(pmid):
    """Fetch abstract + metadata for a single PMID.

    Returns dict: title, abstract, authors, journal, year, doi, pmid, pmcid.
    Returns dict with 'error' if not found.
    """
    pmid = str(pmid).strip()
    url = f"{EUROPMC_API}/article/MED/{pmid}?resultType=core&format=json"
    data = _http_get(url)
    if "error" in data:
        return data
    result = data.get("result")
    if not result:
        return {"error": "not_found", "pmid": pmid}
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


def get_full_text(pmcid):
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
    data = _http_get(url, accept="application/xml")
    if isinstance(data, dict) and "error" in data:
        return data
    if not data or len(data) < 100:
        return {"error": "no_full_text", "pmcid": pmcid}
    return {"pmcid": pmcid, "xml": data, "length": len(data)}


def format_citation(record, style="amber-report"):
    """Format a paper record as a citation string.

    Args:
        record: a result entry from search_literature() or get_abstract()
        style: "amber-report" (compact), "full" (with abstract)

    Returns:
        formatted string suitable for STUDY_REPORT.md §11 References
    """
    if not record or "error" in record:
        return "[unavailable]"
    authors = record.get("first_author") or record.get("authors") or ""
    if "," in (record.get("author_string") or ""):
        authors = f"{record['author_string'].split(',')[0].strip()} et al."
    elif record.get("first_author"):
        authors = f"{record['first_author']} et al."
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


def search_protocol(system_keywords, simulation_type="molecular dynamics",
                    n=10, year_from=2000):
    """Convenience: search for published MD protocols for a specific system.

    Args:
        system_keywords: e.g. "HIV-1 protease apo" or "Abl kinase imatinib"
        simulation_type: "molecular dynamics", "free energy", "MMPBSA", "TI", etc.
        n: max results
        year_from: only papers from this year forward

    Returns same format as search_literature().
    """
    q = f"{system_keywords} {simulation_type}"
    return search_literature(q, limit=n, year_from=year_from)


def compare_to_literature(observable_keyword, system_keyword, n=5):
    """Find papers reporting a specific observable for a specific system.

    Used at Step 7 to find published values for comparison.
    Example: compare_to_literature("flap tip distance", "HIV-1 protease")
    """
    q = f"{system_keyword} {observable_keyword}"
    return search_literature(q, limit=n, year_from=2000)


# ─── CLI ────────────────────────────────────────────────────────────────────

TOOLS = {
    "search_literature": search_literature,
    "get_abstract": get_abstract,
    "get_full_text": get_full_text,
    "format_citation": format_citation,
    "search_protocol": search_protocol,
    "compare_to_literature": compare_to_literature,
}


def _self_test():
    """Quick test against live API. Run with --test flag."""
    print("=== Test 1: search_literature for HIV-1 protease flap MD ===")
    r = search_literature("HIV-1 protease flap molecular dynamics", limit=3)
    if "error" in r:
        print("ERROR:", r["error"])
        return False
    print(f"  Total hits: {r.get('total_hits')}, returned {r['count']}")
    for paper in r["results"]:
        print(f"  - {paper['year']}  {paper['title'][:80]}")
        print(f"    PMID:{paper['pmid']}  DOI:{paper['doi']}")
    print()

    print("=== Test 2: format_citation ===")
    if r["results"]:
        c = format_citation(r["results"][0])
        print(f"  {c[:200]}")
    print()

    print("=== Test 3: compare_to_literature for flap_tip distance ===")
    r2 = compare_to_literature("flap tip distance", "HIV-1 protease", n=2)
    print(f"  Total hits: {r2.get('total_hits')}, returned {r2['count']}")
    for paper in r2["results"][:2]:
        print(f"  - {paper['year']}  {paper['title'][:80]}")
    return True


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        ok = _self_test()
        sys.exit(0 if ok else 1)

    # Tool dispatch via JSON on stdin (matches other MCP servers' pattern)
    if len(sys.argv) > 1:
        tool = sys.argv[1]
        if tool not in TOOLS:
            print(json.dumps({"error": f"unknown tool: {tool}", "available": list(TOOLS)}))
            sys.exit(1)
        kwargs = {}
        if len(sys.argv) > 2:
            try:
                kwargs = json.loads(sys.argv[2])
            except json.JSONDecodeError:
                kwargs = {"query": sys.argv[2]}
        result = TOOLS[tool](**kwargs)
        print(json.dumps(result, indent=2, default=str))
        return

    print(json.dumps({
        "server": "pubmed_server",
        "api": "Europe PMC REST",
        "tools": list(TOOLS),
        "usage": "python pubmed_server.py <tool> '{\"key\":\"value\"}' | --test",
    }, indent=2))


if __name__ == "__main__":
    main()
