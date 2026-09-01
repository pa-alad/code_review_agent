import difflib

from .lenses import LENS_REGISTRY
from .models import FileSnapshot, FindingResponse, LensName, ReviewFinding


def _comment_prefix(language: str) -> str:
    return "#" if language in {"python", "bash"} else "//"


def build_diff(files: list[FileSnapshot], findings: list[ReviewFinding]) -> str:
    by_path: dict[str, list[ReviewFinding]] = {}
    for finding in findings:
        by_path.setdefault(finding.path, []).append(finding)
    chunks = []
    for file in files:
        file_findings = by_path.get(file.path, [])
        if not file_findings:
            continue
        lines = file.content.splitlines()
        updated = lines[:]
        for finding in sorted(file_findings, key=lambda item: item.line, reverse=True):
            if finding.replacement is not None:
                replacement_lines = finding.replacement.splitlines()
                index = finding.line - 1
                if index < 0:
                    index = 0
                if index <= len(updated):
                    updated[index : index + 1] = replacement_lines
                else:
                    updated.extend(replacement_lines)
                continue
            if finding.line <= len(updated):
                prefix = _comment_prefix(file.language)
                reference = finding.references[0].url
                updated.insert(
                    finding.line - 1,
                    f"{prefix} Review {finding.rule_id}: {reference}",
                )
        chunks.extend(
            difflib.unified_diff(
                lines,
                updated,
                fromfile=f"a/{file.path}",
                tofile=f"b/{file.path}",
                lineterm="",
            )
        )
    return "\n".join(chunks)


def run_review(files: list[FileSnapshot], lens_name: LensName) -> tuple[list[ReviewFinding], list[str]]:
    lens = LENS_REGISTRY[lens_name]
    findings = []
    skipped = []
    for file in files:
        if file.language not in lens.languages:
            skipped.append(file.path)
            continue
        findings.extend(lens.run(file))
    return findings, skipped


def response_findings(findings: list[ReviewFinding]) -> list[FindingResponse]:
    return [
        FindingResponse(
            rule_id=f.rule_id,
            severity=f.severity,
            path=f.path,
            line=f.line,
            message=f.message,
            suggestion=f.suggestion,
            references=list(f.references),
        )
        for f in findings
    ]
