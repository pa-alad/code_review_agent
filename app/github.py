from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import httpx

from .lenses import detect_language
from .models import FileSnapshot


@dataclass(frozen=True)
class GitHubTarget:
    owner: str
    repository: str
    path: Optional[str]
    revision: Optional[str]


class GitHubError(RuntimeError):
    pass


def parse_github_url(value: str) -> GitHubTarget:
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
        raise ValueError("Enter an https://github.com repository or file URL.")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        raise ValueError("The URL must include an owner and repository name.")
    owner, repository = parts[:2]
    repository = repository.removesuffix(".git")
    if len(parts) == 2:
        return GitHubTarget(owner, repository, None, None)
    if parts[2] not in {"blob", "raw"} or len(parts) < 5:
        raise ValueError("File URLs must use GitHub's /blob/{branch-or-commit}/{path} form.")
    return GitHubTarget(owner, repository, "/".join(parts[4:]), parts[3])


class GitHubClient:
    def __init__(self, token: Optional[str] = None, client: Optional[httpx.AsyncClient] = None):
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = client or httpx.AsyncClient(headers=headers, timeout=30)

    async def fetch_snapshot(self, target: GitHubTarget, override: Optional[str]) -> tuple[str, list[FileSnapshot], list[str]]:
        base = f"https://api.github.com/repos/{target.owner}/{target.repository}"
        metadata = await self._get(base)
        revision = override or target.revision or metadata["default_branch"]
        commit = await self._get(f"{base}/commits/{revision}")
        tree = await self._get(f"{base}/git/trees/{commit['sha']}?recursive=1")
        snapshots = []
        skipped = []
        for item in tree.get("tree", []):
            path = item.get("path", "")
            language = detect_language(path)
            if target.path and path != target.path:
                continue
            if item.get("type") != "blob" or not language:
                continue
            try:
                blob = await self._get(f"{base}/contents/{path}?ref={commit['sha']}")
                import base64
                snapshots.append(FileSnapshot(path, base64.b64decode(blob["content"]).decode("utf-8"), language))
            except (UnicodeDecodeError, KeyError, GitHubError):
                skipped.append(path)
        if target.path and not any(snapshot.path == target.path for snapshot in snapshots):
            raise GitHubError(f"File not found in revision {revision}: {target.path}")
        return commit["sha"], snapshots, skipped

    async def _get(self, url: str) -> dict:
        response = await self._client.get(url)
        if response.status_code >= 400:
            raise GitHubError(f"GitHub request failed ({response.status_code}).")
        return response.json()

    async def aclose(self) -> None:
        await self._client.aclose()
