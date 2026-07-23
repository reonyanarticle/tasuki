"""agents / skills / commands の frontmatter と相互参照の整合性。"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import ROOT, frontmatter

AGENT_FILES = sorted((ROOT / "agents").glob("*.md"))
COMMAND_FILES = sorted((ROOT / "commands").glob("*.md"))
SKILL_FILES = sorted((ROOT / "skills").glob("*/SKILL.md"))

VALID_MODELS = {"haiku", "sonnet", "opus", "fable", "inherit"}


@pytest.mark.parametrize("path", AGENT_FILES, ids=lambda p: p.name)
class TestAgents:
    def test_frontmatter_required(self, path: Path) -> None:
        fm = frontmatter(path)
        assert fm["name"].startswith("tasuki-"), "agent 名は tasuki- 接頭辞(衝突回避)"
        assert fm["description"]

    def test_model_valid(self, path: Path) -> None:
        fm = frontmatter(path)
        assert fm.get("model", "inherit") in VALID_MODELS

    def test_tools_is_plain_names(self, path: Path) -> None:
        """agent の tools には粒度指定(Bash(gh *) 等)を書けない(検証結果4)。"""
        fm = frontmatter(path)
        assert "(" not in fm.get("tools", "")


def test_gate_reviewers_are_read_only() -> None:
    """gate-reviewer 3変種は読み取り専用(Bash / Write / Edit を持たない)。"""
    for path in AGENT_FILES:
        if "gate-reviewer" not in path.name:
            continue
        tools = {t.strip() for t in frontmatter(path)["tools"].split(",")}
        assert not tools & {"Bash", "Write", "Edit"}, path.name


def test_worker_isolation_and_delegation() -> None:
    """worker は worktree 分離で、プロジェクト subagent 委譲用の Agent を持つ。"""
    fm = frontmatter(ROOT / "agents/worker.md")
    assert fm["isolation"] == "worktree"
    tools = {t.strip() for t in fm["tools"].split(",")}
    assert "Agent" in tools


def test_reviewer_model_ladder() -> None:
    """レイヤードレート構造: 3変種のモデル固定が設計どおりであること。"""
    expected = {
        "gate-reviewer.md": "haiku",
        "gate-reviewer-sonnet.md": "sonnet",
        "gate-reviewer-opus.md": "opus",
    }
    for filename, model in expected.items():
        assert frontmatter(ROOT / "agents" / filename)["model"] == model, filename


@pytest.mark.parametrize("path", COMMAND_FILES + SKILL_FILES, ids=lambda p: str(p.parent.name))
def test_command_and_skill_frontmatter(path: Path) -> None:
    assert frontmatter(path)["description"]


def test_loop_references_existing_agents() -> None:
    """loop.md が委譲する agent 名は、実在する agent の name と一致すること。"""
    agent_names = {frontmatter(p)["name"] for p in AGENT_FILES}
    loop_text = (ROOT / "commands/loop.md").read_text()
    for name in (
        "tasuki-gate-reviewer",
        "tasuki-gate-reviewer-sonnet",
        "tasuki-worker",
        "tasuki-verifier",
    ):
        assert name in loop_text and name in agent_names, name


def test_labels_used_are_created() -> None:
    """loop / loop-status が使うラベルは loop-init が作成する集合に含まれること。"""
    import re

    init_text = (ROOT / "commands/loop-init.md").read_text()
    # loop-init は gate:* を範囲表記で規定する。端点と loop:* の記載を確認する
    for marker in (
        "gate:g0-passed",
        "gate:g4-passed",
        "gate:g0-returned",
        "gate:g4-returned",
        "loop:in-progress",
        "loop:pr",
        "loop:triage",
    ):
        assert marker in init_text, marker

    created = {f"gate:g{i}-{s}" for i in range(5) for s in ("passed", "returned")}
    created |= {"loop:in-progress", "loop:pr", "loop:triage"}
    used = set()
    for path in (ROOT / "commands/loop.md", ROOT / "commands/loop-status.md"):
        used |= set(re.findall(r"(?:gate:g\d-(?:passed|returned)|loop:[a-z-]+)", path.read_text()))
    assert used <= created, used - created


def test_no_runtime_unresolvable_docs_references() -> None:
    """agents / skills / commands は導入先で解決不能な docs/ 参照を持たない。"""
    import re

    offenders = []
    for base in ("agents", "skills", "commands"):
        for path in (ROOT / base).rglob("*.md"):
            for lineno, line in enumerate(path.read_text().splitlines(), 1):
                if re.search(r"docs/[A-Z]", line):
                    offenders.append(f"{path.relative_to(ROOT)}:{lineno}")
    assert not offenders, offenders


def test_verifier_status_contract() -> None:
    """verifier の status 列挙と loop.md の分岐が一致すること(drifting は status ではない)。"""
    verifier_text = (ROOT / "agents/verifier.md").read_text()
    assert '"met | continue | abort | waiting"' in verifier_text.replace("status", "status")
    loop_text = (ROOT / "commands/loop.md").read_text()
    assert "drift_check" in loop_text, "loop.md は drift_check を先に判定する"
