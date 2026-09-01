# Code Review Agent

Code Review Agent is a Dockerised FastAPI application that reviews GitHub snapshots
with deterministic best-practice checks and presents a proposed unified diff.

The code in the specified repository will be reviewed according to a selected software development best practice "lens".

## Run locally with Docker

```sh
docker build -t lens-review .
docker run --rm -p 8000:8000 lens-review
```

Open http://localhost:8000.

Set `GITHUB_TOKEN` when reviewing private repositories or when higher GitHub API limits are needed:

```sh
docker run --rm -p 8000:8000 -e GITHUB_TOKEN="$GITHUB_TOKEN" lens-review
```

## Inputs

- Repository URL: scans supported files at the repository default branch.
- File URL: accepts GitHub's `/blob/{branch-or-commit}/{path}` form and uses that revision.
- Branch or commit: optional override for repository URLs and explicit control of the requested snapshot.

The current version supports Python, C, C++, Java, and Bash files and offers Clean
Code, SOLID, C++ Core Guidelines, and SEI CERT Secure Coding lenses. Each lens
declares the languages it supports; irrelevant files are skipped and shown in the
result. Proposed changes include language-appropriate comments with the rule's
source reference.

GitHub MCP is not required. The container calls GitHub's API directly so it can
run independently of VS Code. Pull-request creation is intentionally deferred.

## Local tests

```sh
python3 -m pip install -e '.[test]'
python3 -m pytest
```
