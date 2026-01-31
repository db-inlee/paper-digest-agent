"""Pydantic schemas for Research-to-Code pipeline."""

from rtc.schemas.delta_v2 import CoreDelta, DeltaOutput, TradeoffWithEvidence
from rtc.schemas.extraction_v2 import (
    BaselineWithEvidence,
    BenchmarkInfo,
    ClaimWithEvidence,
    Evidence,
    ExtractionOutput,
    MethodComponent,
    ProblemDefinition,
)
from rtc.schemas.github_method import GitHubMethodOutput, MethodImplementation
from rtc.schemas.paper import PaperCandidate, SelectedPaper
from rtc.schemas.verification_v1 import VerificationOutput, VerificationResult
from rtc.schemas.parsed import ParsedPDF, Section, Table
from rtc.schemas.scoring_v2 import ScoringOutput
from rtc.schemas.skim import BatchSkimResult, DailySkimOutput, SkimConfig, SkimSummary

__all__ = [
    # Paper
    "PaperCandidate",
    "SelectedPaper",
    # Skim
    "SkimSummary",
    "BatchSkimResult",
    "DailySkimOutput",
    "SkimConfig",
    # Scoring
    "ScoringOutput",
    # Parsing
    "ParsedPDF",
    "Section",
    "Table",
    # Extraction
    "Evidence",
    "ProblemDefinition",
    "BaselineWithEvidence",
    "MethodComponent",
    "BenchmarkInfo",
    "ClaimWithEvidence",
    "ExtractionOutput",
    # Delta
    "CoreDelta",
    "TradeoffWithEvidence",
    "DeltaOutput",
    # GitHub Method
    "GitHubMethodOutput",
    "MethodImplementation",
    # Verification
    "VerificationOutput",
    "VerificationResult",
]
