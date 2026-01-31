"""MCP server implementations."""

from rtc.mcp.servers.arxiv_server import ArxivServer
from rtc.mcp.servers.arxiv_server import paper_dict_to_candidate as arxiv_paper_to_candidate
from rtc.mcp.servers.grobid_server import GrobidServer
from rtc.mcp.servers.hf_papers_server import HFPapersServer
from rtc.mcp.servers.hf_papers_server import paper_dict_to_candidate as hf_paper_to_candidate
from rtc.mcp.servers.pymupdf_parser import PyMuPDFParser

__all__ = [
    "ArxivServer",
    "GrobidServer",
    "HFPapersServer",
    "PyMuPDFParser",
    "arxiv_paper_to_candidate",
    "hf_paper_to_candidate",
]
