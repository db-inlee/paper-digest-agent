"""GROBID MCP Server implementation."""

import re
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from rtc.config import get_settings
from rtc.schemas import ParsedPDF, Section, Table


class GrobidServer:
    """MCP Server for GROBID PDF parsing."""

    # TEI XML namespace
    NS = {"tei": "http://www.tei-c.org/ns/1.0"}

    def __init__(self, grobid_url: str | None = None):
        """Initialize GROBID server.

        Args:
            grobid_url: GROBID service URL. Defaults to settings.
        """
        settings = get_settings()
        self.grobid_url = grobid_url or settings.grobid_url

    async def parse_pdf_to_tei(self, pdf_url: str) -> str:
        """Parse a PDF to TEI-XML using GROBID.

        Args:
            pdf_url: URL to the PDF file

        Returns:
            TEI-XML string
        """
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            # Download PDF
            pdf_response = await client.get(pdf_url)
            pdf_response.raise_for_status()
            pdf_content = pdf_response.content

            # Send to GROBID
            grobid_endpoint = f"{self.grobid_url}/api/processFulltextDocument"
            files = {"input": ("paper.pdf", pdf_content, "application/pdf")}
            data = {
                "consolidateHeader": "1",
                "consolidateCitations": "0",
                "includeRawCitations": "0",
                "includeRawAffiliations": "0",
                "teiCoordinates": "0",
            }

            response = await client.post(grobid_endpoint, files=files, data=data)
            response.raise_for_status()

            return response.text

    async def extract_sections(self, tei_xml: str) -> list[dict[str, Any]]:
        """Extract sections from TEI-XML.

        Args:
            tei_xml: TEI-XML string from GROBID

        Returns:
            List of section dicts with title and content
        """
        root = ET.fromstring(tei_xml)
        sections = []

        # Find body
        body = root.find(".//tei:body", self.NS)
        if body is None:
            return sections

        # Extract divs (sections)
        for div in body.findall(".//tei:div", self.NS):
            head = div.find("tei:head", self.NS)
            title = head.text if head is not None and head.text else "Untitled"

            # Get section level from @n attribute or default to 1
            level = 1
            if head is not None:
                n_attr = head.get("n", "")
                level = n_attr.count(".") + 1 if n_attr else 1

            # Collect all text in section
            content_parts = []
            for p in div.findall("tei:p", self.NS):
                text = self._get_element_text(p)
                if text:
                    content_parts.append(text)

            sections.append({
                "title": title,
                "level": level,
                "content": "\n\n".join(content_parts),
            })

        return sections

    async def extract_tables(self, tei_xml: str) -> list[dict[str, Any]]:
        """Extract tables from TEI-XML.

        Args:
            tei_xml: TEI-XML string from GROBID

        Returns:
            List of table dicts
        """
        root = ET.fromstring(tei_xml)
        tables = []

        for i, figure in enumerate(root.findall(".//tei:figure[@type='table']", self.NS)):
            table_id = figure.get("{http://www.w3.org/XML/1998/namespace}id", f"table_{i}")

            # Get caption
            head = figure.find("tei:head", self.NS)
            caption = head.text if head is not None else None

            # Get table content
            table_elem = figure.find("tei:table", self.NS)
            content = self._table_to_text(table_elem) if table_elem is not None else ""

            tables.append({
                "table_id": table_id,
                "caption": caption,
                "content": content,
            })

        return tables

    async def parse_pdf_full(self, pdf_url: str, arxiv_id: str) -> ParsedPDF:
        """Parse a PDF and return structured data.

        Args:
            pdf_url: URL to the PDF file
            arxiv_id: arXiv ID for reference

        Returns:
            ParsedPDF object
        """
        try:
            tei_xml = await self.parse_pdf_to_tei(pdf_url)
            root = ET.fromstring(tei_xml)

            # Extract title
            title_elem = root.find(".//tei:titleStmt/tei:title", self.NS)
            title = (title_elem.text or "") if title_elem is not None else ""

            # Extract abstract
            abstract_elem = root.find(".//tei:abstract", self.NS)
            abstract = self._get_element_text(abstract_elem) if abstract_elem is not None else ""

            # Extract sections
            section_dicts = await self.extract_sections(tei_xml)
            sections = [
                Section(
                    title=s["title"],
                    level=s["level"],
                    content=s["content"],
                )
                for s in section_dicts
            ]

            # Extract tables
            table_dicts = await self.extract_tables(tei_xml)
            tables = [
                Table(
                    table_id=t["table_id"],
                    caption=t["caption"],
                    content=t["content"],
                )
                for t in table_dicts
            ]

            # Get raw text
            raw_text = self._extract_raw_text(root)

            return ParsedPDF(
                arxiv_id=arxiv_id,
                title=title,
                abstract=abstract,
                sections=sections,
                tables=tables,
                raw_text=raw_text,
                parse_success=True,
            )

        except Exception as e:
            return ParsedPDF(
                arxiv_id=arxiv_id,
                title="",
                abstract="",
                parse_success=False,
                parse_errors=[str(e)],
            )

    def _get_element_text(self, elem: ET.Element | None) -> str:
        """Extract all text from an element, including nested elements."""
        if elem is None:
            return ""
        return "".join(elem.itertext()).strip()

    def _table_to_text(self, table_elem: ET.Element) -> str:
        """Convert a TEI table to text representation."""
        rows = []
        for row in table_elem.findall("tei:row", self.NS):
            cells = []
            for cell in row.findall("tei:cell", self.NS):
                cells.append(self._get_element_text(cell))
            rows.append(" | ".join(cells))
        return "\n".join(rows)

    def _extract_raw_text(self, root: ET.Element) -> str:
        """Extract raw text from the entire document."""
        body = root.find(".//tei:body", self.NS)
        if body is None:
            return ""
        return self._get_element_text(body)


async def check_grobid_health() -> bool:
    """Check if GROBID service is available.

    Returns:
        True if GROBID is healthy
    """
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.grobid_url}/api/isalive")
            return response.status_code == 200
    except Exception:
        return False
