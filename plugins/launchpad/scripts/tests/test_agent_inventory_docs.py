"""Current-state documentation must match the plugin agent inventory."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]


def test_current_docs_report_39_agents() -> None:
    readme = (_REPO_ROOT / "README.md").read_text(encoding="utf-8")
    how_it_works = (_REPO_ROOT / "docs/guides/HOW_IT_WORKS.md").read_text(
        encoding="utf-8"
    )

    assert "| Sub-agents      | 39" in readme
    assert "# 39 sub-agents across 6 namespaces" in readme
    assert "42 slash commands, 39 sub-agents, and 16 skills" in how_it_works


def test_methodology_uses_canonical_agent_ids() -> None:
    methodology = (_REPO_ROOT / "docs/guides/METHODOLOGY.md").read_text(
        encoding="utf-8"
    )

    for agent_id in (
        "lp-claims-auditor",
        "lp-foad-go-reviewer",
        "lp-document-truth",
    ):
        assert f"`{agent_id}`" in methodology
