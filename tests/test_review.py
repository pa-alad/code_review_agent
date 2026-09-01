from app.lenses import LENS_REGISTRY
from app.models import FileSnapshot
from app.review import build_diff, run_review


def test_cpp_lens_skips_python_files():
    files = [FileSnapshot("app.py", "print('hello')", "python")]
    findings, skipped = run_review(files, "cpp-core-guidelines")
    assert findings == []
    assert skipped == ["app.py"]


def test_clean_code_finding_has_reference_in_generated_diff():
    content = "value = " + "x" * 130
    files = [FileSnapshot("main.py", content, "python")]
    findings, skipped = run_review(files, "clean-code")
    diff = build_diff(files, findings)
    assert skipped == []
    assert findings[0].rule_id == "CC-001"
    assert findings[0].references[0].url in diff


def test_registry_is_extendable_by_lens_name():
    assert set(LENS_REGISTRY) == {"clean-code", "solid", "cpp-core-guidelines", "sei-cert"}
