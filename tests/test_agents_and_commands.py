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
    """gate-reviewer は読み取り専用(Bash / Write / Edit を持たない)。"""
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


def test_reviewer_is_single_agent_with_per_call_model() -> None:
    """gate-reviewer は1つの agent で、モデルは呼び出しごとに指定すること。

    以前はモデル固定の3変種に分けていたが、Agent の起動引数で model を渡せる
    (agent 定義の model より優先される)ため統合した。変種の復活を防ぐ。
    """
    reviewers = [p for p in AGENT_FILES if "gate-reviewer" in p.name]
    assert [p.name for p in reviewers] == ["gate-reviewer.md"], reviewers
    loop = (ROOT / "commands/loop.md").read_text()
    assert "判定モデルは呼び出しごとに指定する" in loop
    # ゲート別の標準モデルとエスカレーション先が手順に書かれていること
    for token in ("opus", "haiku", "sonnet"):
        assert token in loop, token
    # ゲート別の判定基準は skill が単一の正であること
    skill = (ROOT / "skills/gate-review/SKILL.md").read_text()
    assert "## ゲート別の特記事項" in skill
    for gate in ("受理ゲート", "分割ゲート", "着手ゲート", "成果ゲート", "統合ゲート"):
        assert gate in skill, gate


@pytest.mark.parametrize("path", COMMAND_FILES + SKILL_FILES, ids=lambda p: str(p.parent.name))
def test_command_and_skill_frontmatter(path: Path) -> None:
    assert frontmatter(path)["description"]


def test_loop_references_existing_agents() -> None:
    """loop.md が委譲する agent 名は、実在する agent の name と一致すること。"""
    agent_names = {frontmatter(p)["name"] for p in AGENT_FILES}
    loop_text = (ROOT / "commands/loop.md").read_text()
    for name in (
        "tasuki-gate-reviewer",
        "tasuki-worker",
        "tasuki-verifier",
    ):
        assert name in loop_text and name in agent_names, name


def test_labels_used_are_created() -> None:
    """loop と loop-status が使うラベルを、loop-init が1つ残らず作成すること。

    範囲表記(gate:intake-passed 〜 gate:integration-passed)では、識別子を
    名前にした後は途中のラベルが列挙されず作られない。実際に使う集合と
    作る集合を突き合わせる。
    """
    import re

    init_text = (ROOT / "commands/loop-init.md").read_text()
    used: set[str] = set()
    for path in (ROOT / "commands/loop.md", ROOT / "commands/loop-status.md"):
        used |= set(re.findall(r"`(gate:[a-z-]+|loop:[a-z-]+)`", path.read_text()))
    # ワイルドカード表記は集合ではないので除く
    used = {label for label in used if "*" not in label}
    missing = sorted(label for label in used if label not in init_text)
    assert not missing, missing


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


def test_trust_boundary_has_single_source() -> None:
    """信頼境界の規範は data-boundary skill を単一の正とし、各 agent は参照だけすること。

    同じ文面を各 agent に複製すると、次の改訂で一部だけ更新されて食い違う。
    """
    assert (ROOT / "skills/data-boundary/SKILL.md").exists()
    for path in AGENT_FILES:
        text = path.read_text()
        assert "tasuki:data-boundary" in text, path.name
        # 複製されていた本文が戻っていないこと
        assert "誰でもコメント" not in text, path.name


def test_worker_records_plan_before_implementing() -> None:
    """worker が実装前に方針を issue コメントへ残すこと(本文には書かない)。

    子 issue の待ち位置は「実装方式は未指定」なので、方針を本文に書くと
    着手ゲートが TOO_CONCRETE で差し戻す。要件と方針を別の場所に置く。
    """
    text = (ROOT / "agents/worker.md").read_text()
    assert "実装方針の記録" in text
    assert "issue 本文には書かない" in text
    for item in ("作るもの", "既存への接続", "選択と理由", "確かめ方"):
        assert item in text, item
    # 方針の記録が実装より前の手順であること
    assert text.index("実装方針の記録") < text.index("2. **実装 / 実験**")
    # 設計上の位置づけが docs に残っていること
    gates = (ROOT / "docs/GATES.md").read_text()
    assert "### 実装方針をどこに置くか" in gates


def test_loop_pr_label_goes_on_the_pr() -> None:
    """loop:pr を PR に付けること(issue に付けると WIP 集計が機能しない)。"""
    text = (ROOT / "agents/worker.md").read_text()
    assert "ラベルは PR に付ける。issue には付けない" in text
