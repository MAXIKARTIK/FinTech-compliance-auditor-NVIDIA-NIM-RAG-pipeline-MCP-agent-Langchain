"""PDF/HTML parsing, chunking and metadata tagging (R1)."""

import pdfplumber
from bs4 import BeautifulSoup
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.services.vectorstore import upsert_chunks

SECTION_MARKERS = {
    "item 1a": "Risk Factors",
    "item 7": "MD&A",
    "item 8": "Financial Statements",
    "item 9a": "Controls and Procedures",
}

def extract_text(path: str) -> str:
    if path.lower().endswith((".htm", ".html")):
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            soup = BeautifulSoup(fh.read(), "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        return soup.get_text(separator="\n")
    with pdfplumber.open(path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)

def build_chunks(text, *, ticker, filing_type, fiscal_year, fiscal_quarter):
    splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=150)
    chunks = splitter.split_text(text)
    ids, docs, metas, current_section = [], [], [], "general"
    for i, chunk in enumerate(chunks):
        lowered = chunk.lower()
        for marker, name in SECTION_MARKERS.items():
            if marker in lowered:
                current_section = name
        ids.append(f"{ticker}-{filing_type}-{fiscal_year}-{fiscal_quarter}-{i}")
        docs.append(chunk)
        metas.append({
            "ticker": ticker, "filing_type": filing_type,
            "fiscal_year": fiscal_year, "fiscal_quarter": fiscal_quarter,
            "section": current_section,
        })
    return ids, docs, metas

def ingest_pdf(path, *, ticker, filing_type, fiscal_year, fiscal_quarter):
    """Parse (PDF or HTML) -> chunk -> tag -> embed -> upsert. Returns chunk count."""
    text = extract_text(path)
    ids, docs, metas = build_chunks(
        text, ticker=ticker, filing_type=filing_type,
        fiscal_year=fiscal_year, fiscal_quarter=fiscal_quarter)
    if ids:
        upsert_chunks(ids, docs, metas)
    return len(ids)
