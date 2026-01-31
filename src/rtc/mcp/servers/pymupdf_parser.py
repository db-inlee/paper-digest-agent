"""PyMuPDF-based PDF text extraction as fallback for GROBID."""

import httpx
import fitz  # PyMuPDF

from rtc.schemas import ParsedPDF


class PyMuPDFParser:
    """Fallback PDF parser using PyMuPDF for text extraction."""

    async def parse_pdf(self, pdf_url: str, arxiv_id: str) -> ParsedPDF:
        """Parse a PDF using PyMuPDF for basic text extraction.

        This is a fallback when GROBID is unavailable. It extracts raw text
        but cannot provide structured sections, tables, or figures.

        Args:
            pdf_url: URL to download the PDF from
            arxiv_id: arXiv identifier for the paper

        Returns:
            ParsedPDF with raw_text populated
        """
        # Download PDF
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(pdf_url, follow_redirects=True)
            response.raise_for_status()
            pdf_bytes = response.content

        # Extract text with PyMuPDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text_parts = []

        for page in doc:
            text_parts.append(page.get_text())

        doc.close()

        raw_text = "\n".join(text_parts)

        return ParsedPDF(
            arxiv_id=arxiv_id,
            title="",  # Cannot reliably extract from raw text
            abstract="",  # Cannot reliably extract from raw text
            sections=[],
            tables=[],
            figures=[],
            references=[],
            raw_text=raw_text,
            parse_success=True,
            parse_errors=[],
        )
