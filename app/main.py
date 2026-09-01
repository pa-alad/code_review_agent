import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from .github import GitHubClient, GitHubError, parse_github_url
from .models import ReviewRequest, ReviewResponse
from .review import build_diff, response_findings, run_review


app = FastAPI(title="Code Review Agent", version="0.1.0")
FRONTEND = Path(__file__).parent.parent / "frontend"


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")


@app.post("/api/reviews", response_model=ReviewResponse)
async def create_review(request: ReviewRequest) -> ReviewResponse:
    try:
        target = parse_github_url(request.github_url)
        client = GitHubClient(os.getenv("GITHUB_TOKEN"))
        try:
            revision, files, fetch_skipped = await client.fetch_snapshot(target, request.branch_or_commit)
        finally:
            await client.aclose()
        findings, lens_skipped = run_review(files, request.lens)
        return ReviewResponse(
            repository=f"{target.owner}/{target.repository}",
            revision=revision,
            lens=request.lens,
            findings=response_findings(findings),
            skipped_files=sorted(set(fetch_skipped + lens_skipped)),
            diff=build_diff(files, findings),
            warnings=[],
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except GitHubError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
