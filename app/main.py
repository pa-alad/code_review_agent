import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from .github import GitHubClient, GitHubError, parse_github_url
from .llm import load_settings, merge_findings, public_provider_config, run_ai_review
from .lenses import LENS_REGISTRY
from .models import ReviewRequest, ReviewResponse
from .review import build_diff, response_findings, run_review


app = FastAPI(title="Code Review Agent", version="0.1.0")
FRONTEND = Path(__file__).parent.parent / "frontend"


@app.get("/api/config")
async def get_config() -> dict:
    return public_provider_config(load_settings())


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")


@app.post("/api/reviews", response_model=ReviewResponse)
async def create_review(request: ReviewRequest) -> ReviewResponse:
    try:
        settings = load_settings()
        if request.ai_review and settings.configured and settings.remote and not request.allow_remote_ai:
            raise ValueError("Confirm the remote AI code-sharing disclosure before requesting this review.")
        target = parse_github_url(request.github_url)
        client = GitHubClient(os.getenv("GITHUB_TOKEN"))
        try:
            revision, files, fetch_skipped, guidance = await client.fetch_snapshot(
                target,
                request.branch_or_commit,
                include_guidance=request.ai_review and settings.configured,
            )
        finally:
            await client.aclose()
        findings, lens_skipped = run_review(files, request.lens)
        warnings = []
        if request.ai_review:
            ai_files = [file for file in files if file.language in LENS_REGISTRY[request.lens].languages]
            ai_findings, warnings = await run_ai_review(
                ai_files,
                request.lens,
                settings,
                guidance=guidance,
                target_path=target.path,
            )
            findings = merge_findings(findings, ai_findings)
        return ReviewResponse(
            repository=f"{target.owner}/{target.repository}",
            revision=revision,
            lens=request.lens,
            findings=response_findings(findings),
            skipped_files=sorted(set(fetch_skipped + lens_skipped)),
            diff=build_diff(files, findings),
            warnings=warnings,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except GitHubError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
