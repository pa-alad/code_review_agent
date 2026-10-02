import httpx
import pytest

from app.main import app
from app.models import ReviewFinding, SourceReference


@pytest.mark.asyncio
async def test_remote_ai_review_requires_explicit_consent(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/reviews",
            json={"github_url": "https://github.com/example/repo", "lens": "clean-code", "ai_review": True},
        )

    assert response.status_code == 400
    assert "Confirm" in response.json()["detail"]


@pytest.mark.asyncio
async def test_provider_configuration_endpoint_never_exposes_api_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/config")

    assert response.status_code == 200
    assert response.json()["ai_available"] is True
    assert response.json()["remote"] is True
    assert "test-secret" not in response.text


@pytest.mark.asyncio
async def test_opted_in_ai_findings_are_included_but_not_applied_as_diff(monkeypatch):
    class FakeGitHubClient:
        def __init__(self, _token):
            pass

        async def fetch_snapshot(self, _target, _override, include_guidance=False):
            assert include_guidance is True
            from app.models import FileSnapshot

            return "revision", [FileSnapshot("src.py", "print(value)\n", "python")], [], {"README.md": "Project"}

        async def aclose(self):
            pass

    async def fake_ai_review(*_args, **_kwargs):
        return [
            ReviewFinding(
                "AI-001",
                "medium",
                "src.py",
                1,
                "Potential issue.",
                "Validate the value.",
                None,
                (),
                "ai",
                "print(value)",
            )
        ], []

    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setattr("app.main.GitHubClient", FakeGitHubClient)
    monkeypatch.setattr("app.main.run_ai_review", fake_ai_review)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/reviews",
            json={"github_url": "https://github.com/example/repo", "lens": "clean-code", "ai_review": True},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["findings"][0]["source"] == "ai"
    assert payload["findings"][0]["evidence"] == "print(value)"
    assert payload["diff"] == ""


def test_deterministic_finding_defaults_to_deterministic_source():
    finding = ReviewFinding("CC-001", "low", "src.py", 1, "message", "suggestion", None, (SourceReference("ref", "https://example.test"),))
    assert finding.source == "deterministic"
