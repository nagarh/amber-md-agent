#!/usr/bin/env python3
"""
Page-Indexed RAG for the Amber Manual.

Design philosophy:
  - Pages are the fundamental unit, NOT arbitrary chunks
  - Authors wrote pages as coherent semantic units — respect that
  - Keep all context: examples, parameter tables, warnings, caveats
  - The LLM (Claude Code) does the semantic understanding
  - This RAG just needs to be a good librarian: find the right pages

Retrieval uses multi-signal scoring:
  1. Keyword matching (with Amber term boosting)
  2. Section/chapter header association (page inherits its section topic)
  3. Page proximity bonus (if page N matches, pages N-1 and N+1 are likely relevant too)
  4. Table of contents mapping (chapter → page range)

Usage:
    # Ingest a PDF manual (page-by-page)
    python rag_amber.py ingest --input Amber24.pdf

    # Append another document
    python rag_amber.py ingest --input Tutorial.pdf --append

    # Query — returns full pages
    python rag_amber.py query "how to set up umbrella sampling"

    # Interactive
    python rag_amber.py interactive

    # Show table of contents
    python rag_amber.py toc
"""

import json
import re
import math
import logging
import argparse
from pathlib import Path
from collections import Counter, defaultdict

logger = logging.getLogger("amber_md_agent.rag")


# ═══════════════════════════════════════════════════════════════════════════════
#  PDF Page Extraction — one text block per page
# ═══════════════════════════════════════════════════════════════════════════════

def extract_pages_from_pdf(pdf_path):
    """Extract text page-by-page from a PDF. Returns list of {page, text}."""
    import subprocess

    pages = []

    # Method 1: PyPDF2 (best page-level control)
    try:
        import PyPDF2
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                if text.strip():
                    pages.append({"page": i + 1, "text": text})
        if pages:
            logger.info(f"Extracted {len(pages)} pages via PyPDF2")
            return pages
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"PyPDF2 failed: {e}")

    # Method 2: pdftotext per page (poppler-utils)
    try:
        # First get page count
        result = subprocess.run(
            ["pdfinfo", str(pdf_path)],
            capture_output=True, text=True, check=True
        )
        n_pages = 0
        for line in result.stdout.split('\n'):
            if line.startswith("Pages:"):
                n_pages = int(line.split(":")[1].strip())
                break

        if n_pages > 0:
            for i in range(1, n_pages + 1):
                result = subprocess.run(
                    ["pdftotext", "-f", str(i), "-l", str(i),
                     "-layout", str(pdf_path), "-"],
                    capture_output=True, text=True, check=True
                )
                text = result.stdout
                if text.strip():
                    pages.append({"page": i, "text": text})

            if pages:
                logger.info(f"Extracted {len(pages)} pages via pdftotext")
                return pages
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Method 3: pdfminer
    try:
        from pdfminer.high_level import extract_text
        from pdfminer.pdfpage import PDFPage
        from pdfminer.pdfparser import PDFParser
        from pdfminer.pdfdocument import PDFDocument

        with open(pdf_path, 'rb') as f:
            parser = PDFParser(f)
            doc = PDFDocument(parser)
            n_pages = sum(1 for _ in PDFPage.create_pages(doc))

        for i in range(n_pages):
            text = extract_text(str(pdf_path), page_numbers=[i])
            if text.strip():
                pages.append({"page": i + 1, "text": text})

        if pages:
            logger.info(f"Extracted {len(pages)} pages via pdfminer")
            return pages
    except ImportError:
        pass

    # Method 4: Fallback — bulk extract and split by form feeds
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            capture_output=True, text=True, check=True
        )
        raw_pages = result.stdout.split('\f')  # Form feed = page break
        for i, text in enumerate(raw_pages):
            if text.strip():
                pages.append({"page": i + 1, "text": text})
        if pages:
            logger.info(f"Extracted {len(pages)} pages via bulk pdftotext")
            return pages
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    raise RuntimeError(
        "No PDF extraction tool available. Install one of:\n"
        "  pip install PyPDF2\n"
        "  apt install poppler-utils\n"
        "  pip install pdfminer.six"
    )


def extract_pages_from_text(text_path):
    """Extract 'pages' from a plain text file.
    Uses form feeds if present, otherwise splits every ~3000 chars at paragraph breaks."""
    text = Path(text_path).read_text(errors='ignore')

    # If the text has form feeds, use those as page breaks
    if '\f' in text:
        raw_pages = text.split('\f')
        return [{"page": i + 1, "text": p} for i, p in enumerate(raw_pages) if p.strip()]

    # Otherwise, split into ~3000 char pages at paragraph boundaries
    pages = []
    paragraphs = text.split('\n\n')
    current_page = ""
    page_num = 1

    for para in paragraphs:
        if len(current_page) + len(para) > 3000 and current_page.strip():
            pages.append({"page": page_num, "text": current_page.strip()})
            page_num += 1
            current_page = para
        else:
            current_page += "\n\n" + para

    if current_page.strip():
        pages.append({"page": page_num, "text": current_page.strip()})

    return pages


def extract_pages(file_path):
    """Auto-detect format and extract pages."""
    path = Path(file_path)
    if path.suffix.lower() == '.pdf':
        return extract_pages_from_pdf(path)
    else:
        return extract_pages_from_text(path)


# ═══════════════════════════════════════════════════════════════════════════════
#  Section / Chapter Detection
# ═══════════════════════════════════════════════════════════════════════════════

def detect_sections(pages):
    """Scan pages and detect chapter/section headers.
    Each page inherits the section context it belongs to.
    This is key: when searching for "umbrella sampling", we match not just
    the page text but also the section it belongs to."""

    section_patterns = [
        # "Chapter 5: Free Energy Methods"
        re.compile(r'^(?:Chapter|CHAPTER)\s+(\d+)[.:]\s*(.+)', re.MULTILINE),
        # "5.1 Umbrella Sampling"
        re.compile(r'^(\d+\.\d+(?:\.\d+)?)\s+([A-Z][^\n]{5,80})', re.MULTILINE),
        # "5. Thermodynamic Integration"
        re.compile(r'^(\d+)\.\s+([A-Z][^\n]{5,80})', re.MULTILINE),
        # "=== Section Title ==="  or "--- Section Title ---"
        re.compile(r'^[=\-]{3,}\s*(.+?)\s*[=\-]{3,}', re.MULTILINE),
    ]

    current_chapter = ""
    current_section = ""
    current_subsection = ""

    for page in pages:
        text = page["text"]

        for pattern in section_patterns:
            for match in pattern.finditer(text):
                groups = match.groups()
                header_text = groups[-1].strip() if len(groups) > 1 else groups[0].strip()
                number = groups[0] if len(groups) > 1 else ""

                if number:
                    if re.match(r'^\d+$', number):  # Chapter level
                        current_chapter = header_text
                        current_section = ""
                        current_subsection = ""
                    elif '.' in number:
                        parts = number.split('.')
                        if len(parts) == 2:
                            current_section = header_text
                            current_subsection = ""
                        else:
                            current_subsection = header_text
                else:
                    current_section = header_text

        # Assign section context to this page
        page["chapter"] = current_chapter
        page["section"] = current_section
        page["subsection"] = current_subsection
        page["section_path"] = " > ".join(
            s for s in [current_chapter, current_section, current_subsection] if s
        )

    return pages


# ═══════════════════════════════════════════════════════════════════════════════
#  Page Index
# ═══════════════════════════════════════════════════════════════════════════════

# Amber-specific terms that get boosted in retrieval
AMBER_TERMS = {
    # Programs
    "amber", "ambertools", "tleap", "leap", "xleap", "sander", "pmemd", "cpptraj",
    "pytraj", "parmed", "antechamber", "parmchk", "parmchk2", "pdb4amber",
    "mmpbsa", "nmode", "mdgx", "resp",
    # File types
    "prmtop", "parm7", "inpcrd", "rst7", "restrt", "netcdf", "mdcrd",
    "mdout", "mdin", "mden", "mdinfo", "mol2", "frcmod", "lib", "off",
    "cpin", "cpout", "cprestrt", "groupfile", "remdlog", "remlog",
    # Simulation types
    "minimization", "minimize", "heating", "equilibration", "equilibrate",
    "production", "solvation", "solvate", "neutralize",
    # Water models & force fields
    "tip3p", "tip4p", "tip4pew", "opc", "opc3", "spc", "spce",
    "ff14sb", "ff19sb", "ff99sb", "ff99sbildn", "ff03",
    "gaff", "gaff2", "lipid14", "lipid17", "lipid21",
    "ol15", "ol3", "bsc1",
    # Key parameters
    "ntp", "nvt", "nve", "ntb", "ntt", "ntp",
    "langevin", "berendsen", "barostat", "thermostat", "montecarlo",
    "shake", "pme", "cutoff", "ewald",
    "imin", "irest", "ntx", "nstlim", "ntc", "ntf",
    "ntr", "restraint_wt", "restraintmask", "bellymask",
    "igb", "saltcon", "rgbmax", "gbsa",
    "cut", "dt", "gamma_ln", "taup", "pres0", "temp0", "tempi",
    "ig", "ioutfm", "ntpr", "ntwx", "ntwr", "ntwe",
    # Enhanced sampling & free energy
    "umbrella", "sampling", "wham", "histogram",
    "thermodynamic", "integration", "lambda", "clambda",
    "softcore", "dvdl", "timask1", "timask2", "scmask1", "scmask2",
    "icfe", "ifsc", "klambda",
    "remd", "replica", "exchange", "numexchg", "rem", "reservoir",
    "steered", "pulling", "smd", "jarzynski",
    "gamd", "igamd", "accelerated", "boost",
    "metadynamics", "colvar", "collective", "variable",
    "cphmd", "constantph", "solvph",
    "alchemical", "fep", "perturbation", "bar", "mbar",
    "qmmm", "qmcut", "qmmask", "qm_theory", "qmcharge",
    # Analysis
    "rmsd", "rmsf", "radgyr", "hbond", "dssp", "cluster", "pca",
    "nativecontacts", "surf", "volmap", "density", "diffusion",
    "crosscorr", "atomiccorr",
    "decomp", "idecomp", "mmpbsa", "mmgbsa", "nmode", "entropy",
    # System setup
    "solvatebox", "solvateoct", "solvateShell",
    "addions", "addions2", "addionsrand",
    "bond", "disulfide", "cyx", "cys",
    "membrane", "lipid", "bilayer", "packmol",
    "histidine", "hid", "hie", "hip", "protonation",
    # Misc
    "periodic", "boundary", "implicit", "explicit",
    "restraint", "constraint", "nmropt",
    "barostat", "montecarlo",
}

STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "under", "again",
    "further", "then", "once", "here", "there", "when", "where", "why",
    "how", "all", "each", "every", "both", "few", "more", "most", "other",
    "some", "such", "no", "nor", "not", "only", "own", "same", "so",
    "than", "too", "very", "just", "but", "and", "or", "if", "this",
    "that", "these", "those", "it", "its", "he", "she", "they", "them",
    "we", "you", "i", "me", "my", "your", "his", "her", "our", "their",
    "what", "which", "who", "whom", "up", "out", "about", "also",
    "page", "figure", "table", "see", "note", "example",
}


def tokenize(text):
    """Tokenize for indexing. Keep Amber terms, drop stopwords."""
    text = text.lower()
    tokens = re.findall(r'[a-z0-9_]+(?:\.[a-z0-9]+)?', text)
    return [t for t in tokens if t in AMBER_TERMS or
            (t not in STOPWORDS and len(t) > 2)]


class PageIndex:
    """Page-level index for the Amber manual.

    Design:
    - Each page is stored as a complete unit (full text preserved)
    - Pages inherit section/chapter context from headers
    - Retrieval returns FULL PAGES — the LLM does semantic understanding
    - Scoring: keyword TF-IDF + section header match + Amber term boost + proximity
    """

    def __init__(self):
        self.pages = []         # List of page dicts
        self.df = Counter()     # Document frequency across pages
        self.n_pages = 0
        self.idf = {}
        self.toc = []           # Table of contents entries

    def ingest(self, file_path):
        """Ingest a document (PDF or text) into the page index."""
        source = Path(file_path).name
        raw_pages = extract_pages(file_path)
        raw_pages = detect_sections(raw_pages)

        start_id = len(self.pages)

        for raw in raw_pages:
            # Build searchable text: page content + section context
            search_text = raw["text"]
            if raw.get("section_path"):
                search_text = raw["section_path"] + "\n" + search_text

            tokens = tokenize(search_text)
            tf = Counter(tokens)

            page_entry = {
                "id": start_id + len(self.pages) - start_id,  # sequential
                "page_num": raw["page"],
                "source": source,
                "text": raw["text"],                   # FULL original text
                "chapter": raw.get("chapter", ""),
                "section": raw.get("section", ""),
                "subsection": raw.get("subsection", ""),
                "section_path": raw.get("section_path", ""),
                "tokens": tokens,
                "tf": tf,
                "amber_term_count": sum(1 for t in tokens if t in AMBER_TERMS),
            }
            self.pages.append(page_entry)

            # Update document frequency
            for token in set(tokens):
                self.df[token] += 1

            # Track TOC entries
            if raw.get("section") and raw["section"] not in [t.get("section") for t in self.toc[-3:]]:
                self.toc.append({
                    "chapter": raw.get("chapter", ""),
                    "section": raw["section"],
                    "page": raw["page"],
                    "source": source,
                })

        self.n_pages = len(self.pages)
        self._recompute_idf()

        logger.info(f"Ingested {source}: {len(raw_pages)} pages "
                     f"(total: {self.n_pages} pages, {len(self.df)} terms)")

    def _recompute_idf(self):
        """Recompute IDF scores after ingestion."""
        for token, freq in self.df.items():
            self.idf[token] = math.log(self.n_pages / (1 + freq))

    def query(self, question, top_k=5, include_neighbors=True):
        """Find the most relevant pages for a question.

        Scoring signals:
        1. TF-IDF keyword match on page content
        2. Section header match (page's chapter/section context)
        3. Amber-specific term boost
        4. Neighbor proximity (if page N scores high, N±1 get a bonus)

        Returns full page texts for the LLM to reason over.
        """
        q_tokens = tokenize(question)
        if not q_tokens:
            return []

        # Also extract raw words for header matching
        q_words = set(re.findall(r'[a-z0-9]+', question.lower()))

        # ── Score each page ──────────────────────────────────────────
        scores = {}

        for page in self.pages:
            score = 0.0

            # Signal 1: TF-IDF on page content
            for token in q_tokens:
                tf = page["tf"].get(token, 0)
                if tf > 0:
                    tf_score = 1 + math.log(tf)
                    idf_score = self.idf.get(token, 0)
                    term_score = tf_score * idf_score

                    # Amber term boost: 2x for domain terms
                    if token in AMBER_TERMS:
                        term_score *= 2.0

                    score += term_score

            # Signal 2: Section header match
            # If the query words appear in the section path, big bonus
            section_text = page.get("section_path", "").lower()
            section_words = set(re.findall(r'[a-z0-9]+', section_text))
            header_overlap = len(q_words & section_words)
            if header_overlap > 0:
                score += header_overlap * 3.0  # strong signal

            if score > 0:
                scores[page["id"]] = score

        # Signal 3: Neighbor proximity bonus
        # If page N is highly relevant, pages N-1 and N+1 likely are too
        if include_neighbors and scores:
            neighbor_bonus = {}
            for page_id, score in scores.items():
                for neighbor in [page_id - 1, page_id + 1]:
                    if 0 <= neighbor < self.n_pages:
                        # Only boost within same source document
                        if self.pages[neighbor]["source"] == self.pages[page_id]["source"]:
                            current = neighbor_bonus.get(neighbor, 0)
                            neighbor_bonus[neighbor] = max(current, score * 0.3)

            for page_id, bonus in neighbor_bonus.items():
                if page_id in scores:
                    scores[page_id] += bonus
                else:
                    scores[page_id] = bonus

        # ── Rank and return ──────────────────────────────────────────
        ranked = sorted(scores.items(), key=lambda x: -x[1])

        # Deduplicate: if two consecutive pages from same source, merge them
        results = []
        seen_pages = set()

        for page_id, score in ranked:
            if page_id in seen_pages:
                continue
            if len(results) >= top_k:
                break

            page = self.pages[page_id]
            seen_pages.add(page_id)

            result = {
                "page": page["page_num"],
                "source": page["source"],
                "score": round(score, 2),
                "section_path": page["section_path"],
                "text": page["text"],  # FULL page — semantic meaning preserved
            }
            results.append(result)

        return results

    def query_by_section(self, section_name):
        """Get ALL pages belonging to a named section.
        Useful when the agent knows which chapter it needs."""
        section_lower = section_name.lower()
        results = []
        for page in self.pages:
            sp = page.get("section_path", "").lower()
            if section_lower in sp:
                results.append({
                    "page": page["page_num"],
                    "source": page["source"],
                    "section_path": page["section_path"],
                    "text": page["text"],
                })
        return results

    def get_toc(self):
        """Return the detected table of contents."""
        return self.toc

    def get_page(self, page_num, source=None):
        """Get a specific page by number."""
        for page in self.pages:
            if page["page_num"] == page_num:
                if source is None or page["source"] == source:
                    return {"page": page["page_num"], "source": page["source"],
                            "section_path": page["section_path"], "text": page["text"]}
        return None

    def get_page_range(self, start, end, source=None):
        """Get a range of pages. Useful when the agent wants to read a whole chapter."""
        results = []
        for page in self.pages:
            if start <= page["page_num"] <= end:
                if source is None or page["source"] == source:
                    results.append({
                        "page": page["page_num"], "source": page["source"],
                        "section_path": page["section_path"], "text": page["text"],
                    })
        return results

    # ── Persistence ──────────────────────────────────────────────────

    def save(self, path):
        """Save index to JSON."""
        data = {
            "n_pages": self.n_pages,
            "pages": [
                {
                    "id": p["id"], "page_num": p["page_num"], "source": p["source"],
                    "text": p["text"], "chapter": p["chapter"],
                    "section": p["section"], "subsection": p["subsection"],
                    "section_path": p["section_path"],
                }
                for p in self.pages
            ],
            "toc": self.toc,
            "df": dict(self.df),
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(data))  # No indent — save space for large manuals
        size_mb = Path(path).stat().st_size / (1024 * 1024)
        logger.info(f"Index saved: {path} ({size_mb:.1f} MB, {self.n_pages} pages)")

    def load(self, path):
        """Load index from JSON."""
        data = json.loads(Path(path).read_text())
        self.n_pages = data["n_pages"]
        self.df = Counter(data["df"])
        self.toc = data.get("toc", [])

        for pd in data["pages"]:
            search_text = pd["text"]
            if pd.get("section_path"):
                search_text = pd["section_path"] + "\n" + search_text
            tokens = tokenize(search_text)

            page = {
                **pd,
                "tokens": tokens,
                "tf": Counter(tokens),
                "amber_term_count": sum(1 for t in tokens if t in AMBER_TERMS),
            }
            self.pages.append(page)

        self._recompute_idf()
        logger.info(f"Index loaded: {self.n_pages} pages from {path}")

    def stats(self):
        """Return index statistics."""
        sources = set(p["source"] for p in self.pages)
        return {
            "n_pages": self.n_pages,
            "n_terms": len(self.df),
            "n_toc_entries": len(self.toc),
            "sources": sorted(sources),
            "pages_per_source": {s: sum(1 for p in self.pages if p["source"] == s)
                                  for s in sources},
        }


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Page-Indexed RAG for the Amber Manual",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Pages are the fundamental unit — preserving semantic coherence as the
author wrote it. The LLM does the semantic understanding; this RAG
just finds the right pages.

Examples:
    python rag_amber.py ingest --input Amber24.pdf
    python rag_amber.py ingest --input Tutorial.pdf --append
    python rag_amber.py query "umbrella sampling setup"
    python rag_amber.py query "TI lambda windows" --top-k 10
    python rag_amber.py toc
    python rag_amber.py page 142
    python rag_amber.py pages 140-150
    python rag_amber.py section "Free Energy"
    python rag_amber.py stats
    python rag_amber.py interactive
        """
    )
    sub = parser.add_subparsers(dest="cmd")

    # Ingest
    ip = sub.add_parser("ingest", help="Ingest a manual (PDF or text)")
    ip.add_argument("--input", required=True, help="Path to document")
    ip.add_argument("--output", default="references/amber_index.json", help="Index output path")
    ip.add_argument("--append", action="store_true", help="Append to existing index")

    # Query
    qp = sub.add_parser("query", help="Search for relevant pages")
    qp.add_argument("question", help="Your question")
    qp.add_argument("--index", default="references/amber_index.json")
    qp.add_argument("--top-k", type=int, default=5, help="Number of pages to return")
    qp.add_argument("--no-neighbors", action="store_true", help="Disable neighbor proximity bonus")

    # Section query
    sp = sub.add_parser("section", help="Get all pages in a section")
    sp.add_argument("name", help="Section name (partial match)")
    sp.add_argument("--index", default="references/amber_index.json")

    # Page
    pp = sub.add_parser("page", help="Get a specific page")
    pp.add_argument("number", type=int)
    pp.add_argument("--index", default="references/amber_index.json")

    # Page range
    pr = sub.add_parser("pages", help="Get a range of pages (e.g., 140-150)")
    pr.add_argument("range", help="Page range like 140-150")
    pr.add_argument("--index", default="references/amber_index.json")

    # TOC
    tp = sub.add_parser("toc", help="Show table of contents")
    tp.add_argument("--index", default="references/amber_index.json")

    # Stats
    stp = sub.add_parser("stats", help="Show index statistics")
    stp.add_argument("--index", default="references/amber_index.json")

    # Interactive
    sub.add_parser("interactive", help="Interactive query mode")

    args = parser.parse_args()

    if args.cmd == "ingest":
        index = PageIndex()
        if args.append and Path(args.output).exists():
            index.load(args.output)
            print(f"Loaded existing index ({index.n_pages} pages)")
        index.ingest(args.input)
        index.save(args.output)
        print(f"✓ Indexed {index.n_pages} total pages → {args.output}")
        print(f"  Detected {len(index.toc)} TOC entries")

    elif args.cmd == "query":
        index = PageIndex()
        index.load(args.index)
        results = index.query(args.question, top_k=args.top_k,
                              include_neighbors=not args.no_neighbors)
        print(f"\n📚 Query: '{args.question}' — {len(results)} pages found\n")
        for r in results:
            header = f"[Page {r['page']} | Score: {r['score']} | {r['source']}]"
            if r['section_path']:
                header += f" § {r['section_path']}"
            print(f"{'═' * 70}")
            print(header)
            print(f"{'─' * 70}")
            # Show full page text (truncate for terminal display)
            text = r["text"]
            if len(text) > 2000:
                print(text[:2000])
                print(f"\n  ... ({len(text) - 2000} more chars)")
            else:
                print(text)
            print()

    elif args.cmd == "section":
        index = PageIndex()
        index.load(args.index)
        results = index.query_by_section(args.name)
        print(f"\nSection '{args.name}': {len(results)} pages\n")
        for r in results:
            print(f"  Page {r['page']:4d} | {r['section_path']} ({r['source']})")

    elif args.cmd == "page":
        index = PageIndex()
        index.load(args.index)
        result = index.get_page(args.number)
        if result:
            print(f"\n[Page {result['page']} | {result['source']}] § {result['section_path']}\n")
            print(result["text"])
        else:
            print(f"Page {args.number} not found")

    elif args.cmd == "pages":
        index = PageIndex()
        index.load(args.index)
        start, end = map(int, args.range.split("-"))
        results = index.get_page_range(start, end)
        for r in results:
            print(f"\n{'═' * 70}")
            print(f"[Page {r['page']} | {r['source']}] § {r['section_path']}")
            print(f"{'─' * 70}")
            print(r["text"])

    elif args.cmd == "toc":
        index = PageIndex()
        index.load(args.index)
        toc = index.get_toc()
        print(f"\nTable of Contents ({len(toc)} entries):\n")
        current_chapter = ""
        for entry in toc:
            if entry["chapter"] != current_chapter:
                current_chapter = entry["chapter"]
                if current_chapter:
                    print(f"\n  {current_chapter}")
            print(f"    p.{entry['page']:4d}  {entry['section']}  [{entry['source']}]")

    elif args.cmd == "stats":
        index = PageIndex()
        index.load(args.index)
        print(json.dumps(index.stats(), indent=2))

    elif args.cmd == "interactive":
        index_path = "references/amber_index.json"
        if not Path(index_path).exists():
            print("No index found. Run: python rag_amber.py ingest --input <manual.pdf>")
            return
        index = PageIndex()
        index.load(index_path)
        print(f"Amber Manual RAG — {index.n_pages} pages indexed")
        print("Commands: query text | toc | page N | section NAME | quit\n")
        while True:
            q = input("❯ ").strip()
            if q.lower() in ('quit', 'exit', 'q'):
                break
            elif q.lower() == 'toc':
                for entry in index.get_toc():
                    print(f"  p.{entry['page']:4d}  {entry['section']}")
            elif q.lower().startswith('page '):
                num = int(q.split()[1])
                r = index.get_page(num)
                if r:
                    print(f"\n[Page {r['page']}] § {r['section_path']}\n{r['text']}\n")
            elif q.lower().startswith('section '):
                name = q[8:].strip()
                for r in index.query_by_section(name):
                    print(f"  Page {r['page']:4d} | {r['section_path']}")
            else:
                results = index.query(q, top_k=3)
                for r in results:
                    print(f"\n{'═' * 60}")
                    print(f"[Page {r['page']} | Score {r['score']}] § {r['section_path']}")
                    print(r["text"][:1500])
                print()


if __name__ == "__main__":
    main()
