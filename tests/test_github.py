import base64

import httpx
import pytest

from app.github import GitHubClient, parse_github_url


def test_repository_url_has_no_embedded_revision():
    assert parse_github_url("https://github.com/acme/demo").revision is None


def test_file_url_extracts_revision_and_path():
    target = parse_github_url("https://github.com/acme/demo/blob/release-1/src/main.cpp")
    assert target.revision == "release-1"
    assert target.path == "src/main.cpp"


def test_non_github_url_is_rejected():
    with pytest.raises(ValueError):
        parse_github_url("https://gitlab.com/acme/demo")


def test_file_url_can_contain_nested_paths():
    target = parse_github_url("https://github.com/acme/demo/blob/abc/a/b/script.sh")
    assert target.path == "a/b/script.sh"


@pytest.mark.asyncio
async def test_snapshot_fetches_project_guidance_only_when_requested():
    requests = []
    contents = {
        "src/app.py": "print('hello')\n",
        "README.md": "Project guidance\n",
        "src/AGENTS.md": "Nested instructions\n",
    }

    def handler(request):
        requests.append(request.url)
        if request.url.path == "/repos/acme/demo":
            return httpx.Response(200, json={"default_branch": "main"})
        if request.url.path.endswith("/commits/main"):
            return httpx.Response(200, json={"sha": "pinned-sha"})
        if request.url.path.endswith("/git/trees/pinned-sha"):
            return httpx.Response(
                200,
                json={
                    "tree": [
                        {"type": "blob", "path": path}
                        for path in contents
                    ]
                },
            )
        path = request.url.path.split("/contents/", 1)[1]
        encoded = base64.b64encode(contents[path].encode()).decode()
        return httpx.Response(200, json={"content": encoded})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = GitHubClient(client=http_client)
        target = parse_github_url("https://github.com/acme/demo")
        _, snapshots, _, guidance = await client.fetch_snapshot(
            target, None, include_guidance=True
        )
        requests.clear()
        _, _, _, no_guidance = await client.fetch_snapshot(target, None)

    assert [snapshot.path for snapshot in snapshots] == ["src/app.py"]
    assert guidance["README.md"] == "Project guidance\n"
    assert guidance["src/AGENTS.md"] == "Nested instructions\n"
    content_urls = [url for url in requests if "/contents/" in url.path]
    assert [url.path.rsplit("/contents/", 1)[1] for url in content_urls] == ["src/app.py"]
    assert all(url.params.get("ref") == "pinned-sha" for url in content_urls)
    assert no_guidance == {}
