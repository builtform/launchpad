"""Static contracts for the evidence-oriented review agents."""

from __future__ import annotations

from pathlib import Path

import yaml

_AGENTS_ROOT = Path(__file__).resolve().parents[2] / "agents" / "review"


def _text(name: str) -> str:
    return (_AGENTS_ROOT / name).read_text(encoding="utf-8")


def _frontmatter(name: str) -> dict:
    text = _text(name)
    end = text.find("\n---\n", 4)
    assert text.startswith("---\n") and end > 4
    parsed = yaml.safe_load(text[4:end])
    assert isinstance(parsed, dict)
    return parsed


def test_go_reviewer_probes_only_in_isolated_copies() -> None:
    text = _text("lp-foad-go-reviewer.md")
    metadata = _frontmatter("lp-foad-go-reviewer.md")["x-launchpad"]["capabilities"]

    assert "temporary `_test.go` file inside the repository" not in text
    assert "Don't create a temporary test anywhere under the reviewed repository" in text
    assert "isolated scratch copy under a temporary directory" in text
    assert "Require byte-identical status output" in text
    assert "DO NOT execute reviewed Go code through a bare" in text
    assert "require `bwrap` with a new network namespace" in text
    assert "require `sandbox-exec` with default deny" in text
    assert "Scrub the process environment with `env -i`" in text
    assert "report a coverage limitation with no finding priority" in text
    assert "Prefix every focused `go test`, `go run`" in text
    assert metadata["mutation"] == "none"
    assert metadata["tool-profile"] == "read_only"
    assert "repository_write" not in metadata["required"]


def test_claims_reviewer_separates_coverage_limits_from_findings() -> None:
    text = _text("lp-claims-auditor.md")
    metadata = _frontmatter("lp-claims-auditor.md")["x-launchpad"]["capabilities"]

    assert "coverage limitations rather than actionable findings" in text
    assert "coverage-limitations section" in text
    assert "does not enter the prioritized findings list" in text
    assert "unavailable local tool, credential, or external service" in text
    assert "DO NOT execute reviewed tests" in text
    assert "require `bwrap` with a new network namespace" in text
    assert "require `sandbox-exec` with default deny" in text
    assert "Scrub executable-check environments with `env -i`" in text
    assert "record a coverage limitation with no finding priority" in text
    assert metadata["mutation"] == "none"
    assert metadata["tool-profile"] == "read_only"


def test_go_sandbox_example_scrubs_environment_and_uses_scratch_paths() -> None:
    text = _text("lp-foad-go-reviewer.md")

    assert "Run: `env -i" in text
    assert "HOME=/work/home" in text
    assert "TMPDIR=/work/tmp" in text
    assert "GOCACHE=/work/cache" in text
    assert "GOMODCACHE=/work/modcache" in text
    assert "GOPROXY=off" in text
    assert "--unshare-all" in text


def test_document_reviewer_sandboxes_binary_extraction() -> None:
    text = _text("lp-document-truth.md")
    frontmatter = _frontmatter("lp-document-truth.md")
    external_tools = frontmatter["x-launchpad"]["direct"]["external-tools"]

    assert "DO NOT run repository-controlled renderers" in text
    assert "require `bwrap` with a new network namespace" in text
    assert "require `sandbox-exec` with default deny" in text
    assert "Scrub extractor environments with `env -i`" in text
    assert "coverage limitation with no finding priority" in text
    assert "Don't process a binary artifact with an unsandboxed parser" in text
    assert {"bwrap", "sandbox-exec"}.issubset(external_tools)
