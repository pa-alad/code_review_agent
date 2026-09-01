from collections.abc import Callable
from dataclasses import dataclass
import re
from typing import Optional

from .models import FileSnapshot, LensName, ReviewFinding, SourceReference


@dataclass(frozen=True)
class ReviewLens:
    name: LensName
    label: str
    languages: frozenset[str]
    run: Callable[[FileSnapshot], list[ReviewFinding]]


CLEAN_CODE_REF = SourceReference(
    "Clean Code handbook",
    (
        "https://github.com/jnguyen095/clean-code/blob/master/"
        "Clean.Code.A.Handbook.of.Agile.Software.Craftsmanship.pdf"
    ),
)
SOLID_REF = SourceReference("SOLID principles", "https://en.wikipedia.org/wiki/SOLID")
CPP_REF = SourceReference(
    "C++ Core Guidelines",
    "https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines.html",
)
CERT_REF = SourceReference(
    "SEI CERT Secure Coding",
    "https://cmu-sei.github.io/secure-coding-standards/",
)


def _language_for(path: str) -> Optional[str]:
    suffix = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return {
        "py": "python",
        "c": "c",
        "h": "c",
        "cc": "cpp",
        "cpp": "cpp",
        "cxx": "cpp",
        "hpp": "cpp",
        "java": "java",
        "sh": "bash",
        "bash": "bash",
    }.get(suffix)


def _clean_code(file: FileSnapshot) -> list[ReviewFinding]:
    findings = []
    for number, line in enumerate(file.content.splitlines(), 1):
        if len(line) > 120:
            findings.append(
                ReviewFinding(
                    "CC-001",
                    "low",
                    file.path,
                    number,
                    "This line is difficult to scan because it exceeds 120 characters.",
                    "Break the expression into named intermediate steps.",
                    None,
                    (CLEAN_CODE_REF,),
                )
            )
    return findings


def _solid(file: FileSnapshot) -> list[ReviewFinding]:
    findings = []
    for number, line in enumerate(file.content.splitlines(), 1):
        if (
            re.search(r"\b(class|def|function)\s+\w+", line)
            and "(" not in line
            and file.language in {"python", "java"}
        ):
            findings.append(
                ReviewFinding(
                    "SOLID-001",
                    "medium",
                    file.path,
                    number,
                    "This declaration may hide a type or function with unclear responsibility.",
                    "Review the abstraction boundary and keep the responsibility focused.",
                    None,
                    (SOLID_REF,),
                )
            )
    return findings


def _cpp_core(file: FileSnapshot) -> list[ReviewFinding]:
    findings = []
    for number, line in enumerate(file.content.splitlines(), 1):
        if re.search(r"\b(char\s*\*|strcpy\s*\(|sprintf\s*\()", line):
            findings.append(
                ReviewFinding(
                    "CPP-001",
                    "high",
                    file.path,
                    number,
                    "This pattern can create unsafe memory or buffer handling.",
                    "Use a bounds-aware abstraction and make ownership explicit.",
                    None,
                    (CPP_REF, CERT_REF),
                )
            )
    return findings


def _sei_cert(file: FileSnapshot) -> list[ReviewFinding]:
    findings = []
    for number, line in enumerate(file.content.splitlines(), 1):
        if re.search(r"(input\s*\(|eval\s*\(|system\s*\(|os\.system\s*)", line):
            findings.append(
                ReviewFinding(
                    "CERT-001",
                    "high",
                    file.path,
                    number,
                    "This operation may use untrusted input without visible validation.",
                    "Validate, constrain, and safely encode input before using this operation.",
                    None,
                    (CERT_REF,),
                )
            )
    return findings


LENS_REGISTRY: dict[LensName, ReviewLens] = {
    "clean-code": ReviewLens(
        "clean-code",
        "Clean Code",
        frozenset({"python", "c", "cpp", "java", "bash"}),
        _clean_code,
    ),
    "solid": ReviewLens(
        "solid",
        "SOLID principles",
        frozenset({"python", "c", "cpp", "java", "bash"}),
        _solid,
    ),
    "cpp-core-guidelines": ReviewLens(
        "cpp-core-guidelines",
        "C++ Core Guidelines",
        frozenset({"c", "cpp"}),
        _cpp_core,
    ),
    "sei-cert": ReviewLens(
        "sei-cert",
        "SEI CERT Secure Coding",
        frozenset({"python", "c", "cpp", "java", "bash"}),
        _sei_cert,
    ),
}


def detect_language(path: str) -> Optional[str]:
    return _language_for(path)
