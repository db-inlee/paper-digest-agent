"""Chunker - turn a paper's extraction + delta into embeddable chunks."""

from __future__ import annotations

from rtc.schemas.delta_v2 import DeltaOutput
from rtc.schemas.extraction_v2 import ExtractionOutput

# Each chunk is (chunk_type, text, chunk_metadata).
# NOTE: the ticket (2c) specified a 2-tuple (chunk_type, text); a third
# element carries chunk-level metadata (e.g. claim_type) per the same item's
# "claim_type는 metadata로" requirement.
Chunk = tuple[str, str, dict]


def paper_to_chunks(
    arxiv_id: str,
    extraction: ExtractionOutput,
    delta: DeltaOutput,
) -> list[Chunk]:
    """Build embeddable chunks from a paper's extraction and delta.

    - takeaway: delta.one_line_takeaway (1 chunk)
    - delta: each core_delta -> "{axis}: {old_approach} -> {new_approach}"
    - claim: each extraction.claims[].text (claim_type kept in metadata)

    Empty texts are skipped.
    """
    chunks: list[Chunk] = []

    takeaway = (delta.one_line_takeaway or "").strip()
    if takeaway:
        chunks.append(("takeaway", takeaway, {}))

    for cd in delta.core_deltas:
        text = f"{cd.axis}: {cd.old_approach} -> {cd.new_approach}".strip()
        if text and text != ": ->":
            chunks.append(("delta", text, {"axis": cd.axis}))

    for claim in extraction.claims:
        text = (claim.text or "").strip()
        if text:
            chunks.append(("claim", text, {"claim_type": claim.claim_type}))

    return chunks
