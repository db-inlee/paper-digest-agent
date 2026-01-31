"""Parsed PDF schemas."""

from typing import Optional

from pydantic import BaseModel, Field


class Table(BaseModel):
    """A table extracted from the paper."""

    table_id: str = Field(..., description="Table identifier")
    caption: Optional[str] = Field(default=None, description="Table caption")
    content: str = Field(..., description="Table content as text or markdown")
    section: Optional[str] = Field(default=None, description="Section where table appears")


class Figure(BaseModel):
    """A figure reference from the paper."""

    figure_id: str = Field(..., description="Figure identifier")
    caption: Optional[str] = Field(default=None, description="Figure caption")
    section: Optional[str] = Field(default=None, description="Section where figure appears")


class Section(BaseModel):
    """A section from the parsed paper."""

    title: str = Field(..., description="Section title")
    level: int = Field(default=1, description="Section level (1=top)")
    content: str = Field(..., description="Section text content")
    subsections: list["Section"] = Field(default_factory=list, description="Nested subsections")


class Reference(BaseModel):
    """A bibliographic reference."""

    ref_id: str = Field(..., description="Reference identifier")
    title: Optional[str] = Field(default=None, description="Reference title")
    authors: list[str] = Field(default_factory=list, description="Reference authors")
    year: Optional[int] = Field(default=None, description="Publication year")
    venue: Optional[str] = Field(default=None, description="Publication venue")


class ParsedPDF(BaseModel):
    """Fully parsed PDF structure."""

    arxiv_id: str = Field(..., description="arXiv identifier")
    title: str = Field(..., description="Paper title")
    abstract: str = Field(..., description="Paper abstract")
    sections: list[Section] = Field(default_factory=list, description="Paper sections")
    tables: list[Table] = Field(default_factory=list, description="Extracted tables")
    figures: list[Figure] = Field(default_factory=list, description="Figure references")
    references: list[Reference] = Field(default_factory=list, description="Bibliography")
    raw_text: Optional[str] = Field(default=None, description="Full raw text if available")
    parse_success: bool = Field(default=True, description="Whether parsing succeeded")
    parse_errors: list[str] = Field(default_factory=list, description="Any parsing errors")

    def get_section_by_title(self, title: str) -> Optional[Section]:
        """Find a section by its title (case-insensitive)."""
        title_lower = title.lower()
        for section in self.sections:
            if title_lower in section.title.lower():
                return section
            for subsec in section.subsections:
                if title_lower in subsec.title.lower():
                    return subsec
        return None

    def get_full_text(self) -> str:
        """Get concatenated text from all sections."""
        if self.raw_text:
            return self.raw_text
        parts = [self.abstract]
        for section in self.sections:
            parts.append(f"\n## {section.title}\n{section.content}")
            for subsec in section.subsections:
                parts.append(f"\n### {subsec.title}\n{subsec.content}")
        return "\n".join(parts)
