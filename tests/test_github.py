import pytest

from app.github import parse_github_url


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
