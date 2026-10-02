from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from pydantic import BaseModel, Field


LensName = Literal["clean-code", "solid", "cpp-core-guidelines", "sei-cert"]


class ReviewRequest(BaseModel):
    github_url: str = Field(min_length=1)
    branch_or_commit: Optional[str] = None
    lens: LensName
    ai_review: bool = False
    allow_remote_ai: bool = False


@dataclass(frozen=True)
class FileSnapshot:
    path: str
    content: str
    language: str


@dataclass(frozen=True)
class SourceReference:
    title: str
    url: str


@dataclass(frozen=True)
class ReviewFinding:
    rule_id: str
    severity: str
    path: str
    line: int
    message: str
    suggestion: str
    replacement: Optional[str]
    references: tuple[SourceReference, ...]
    source: str = "deterministic"
    evidence: Optional[str] = None


class FindingResponse(BaseModel):
    rule_id: str
    severity: str
    path: str
    line: int
    message: str
    suggestion: str
    references: list[SourceReference]
    source: str = "deterministic"
    evidence: Optional[str] = None


class ReviewResponse(BaseModel):
    repository: str
    revision: str
    lens: LensName
    findings: list[FindingResponse]
    skipped_files: list[str]
    diff: str
    warnings: list[str]
