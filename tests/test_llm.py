import json

import httpx
import pytest

from app.llm import (
    LLMSettings,
    build_context,
    load_settings,
    merge_findings,
    public_provider_config,
    run_ai_review,
    validate_findings,
)
from app.models import FileSnapshot, ReviewFinding


SOURCE = FileSnapshot("src/app.py", "def run():\n    dangerous_call(user_input)\n", "python")


def _finding(path="src/app.py", line=2, evidence="dangerous_call"):
    return {
        "path": path,
        "line": line,
        "severity": "medium",
        "message": "The value is not validated before use.",
        "suggestion": "Validate the value before calling this function.",
        "evidence": evidence,
    }


def test_load_settings_defaults_to_disabled_and_public_config_hides_credentials():
    settings = load_settings({})
    assert settings.provider == "none"
    assert settings.configured is False

    gemini = load_settings({"LLM_PROVIDER": "gemini", "GEMINI_API_KEY": "secret-key"})
    assert public_provider_config(gemini) == {
        "ai_available": True,
        "provider": "gemini",
        "remote": True,
        "model": "gemini-2.5-flash",
    }
    assert "secret-key" not in str(public_provider_config(gemini))


def test_validate_findings_requires_valid_snapshot_location_and_exact_evidence():
    result = validate_findings(
        {"findings": [_finding(), _finding(path="missing.py"), _finding(line=99), _finding(evidence="not present")]},
        [SOURCE],
    )
    assert len(result) == 1
    assert result[0].source == "ai"
    assert result[0].evidence == "dangerous_call"
    assert result[0].references == ()


def test_build_context_has_hard_character_limit_and_reports_truncation():
    files = [FileSnapshot(f"src/{index}.py", "x" * 8_000, "python") for index in range(12)]
    context, warnings = build_context(files)
    assert len(context) <= 64_000
    assert warnings


def test_merge_findings_deduplicates_ai_at_deterministic_locations():
    deterministic = ReviewFinding("CC-001", "low", SOURCE.path, 2, "message", "suggestion", None, ())
    ai = validate_findings({"findings": [_finding()]}, [SOURCE])
    assert merge_findings([deterministic], ai) == [deterministic]


@pytest.mark.asyncio
async def test_ollama_provider_returns_only_snapshot_validated_findings():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"message": {"content": json.dumps({"findings": [_finding()]})}},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        findings, warnings = await run_ai_review(
            [SOURCE],
            "sei-cert",
            LLMSettings("ollama", "test-model", "http://ollama:11434"),
            client=client,
        )

    assert seen["url"] == "http://ollama:11434/api/chat"
    assert seen["payload"]["model"] == "test-model"
    assert "untrusted data" in seen["payload"]["messages"][1]["content"]
    assert findings[0].rule_id == "AI-001"
    assert warnings == []


@pytest.mark.asyncio
async def test_gemini_provider_sends_key_only_to_provider_and_parses_json():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": json.dumps({"findings": [_finding()]})}]}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        findings, warnings = await run_ai_review(
            [SOURCE],
            "sei-cert",
            LLMSettings("gemini", "gemini-test", "https://example.test/v1beta", "test-secret"),
            client=client,
        )

    assert "key=test-secret" in seen["url"]
    assert findings[0].path == SOURCE.path
    assert warnings == []


@pytest.mark.asyncio
async def test_provider_failure_returns_warning_without_raising():
    def handler(_request):
        return httpx.Response(503)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        findings, warnings = await run_ai_review(
            [SOURCE],
            "sei-cert",
            LLMSettings("ollama", "test-model", "http://ollama:11434"),
            client=client,
        )

    assert findings == []
    assert warnings == ["AI review failed or returned an invalid response; deterministic findings are shown."]
