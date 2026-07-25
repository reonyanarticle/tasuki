"""ドキュメントの参照整合性。"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from conftest import ROOT

MD_FILES = [ROOT / "README.md", ROOT / "CLAUDE.md", *sorted((ROOT / "docs").glob("*.md"))]

_LINK = re.compile(r"\]\(([^)#]+?)(?:#[^)]*)?\)")


@pytest.mark.parametrize("path", MD_FILES, ids=lambda p: p.name)
def test_relative_links_resolve(path: Path) -> None:
    """markdown の相対リンクが実在ファイルを指すこと。"""
    broken = []
    for target in _LINK.findall(path.read_text()):
        if target.startswith(("http://", "https://")):
            continue
        if not (path.parent / target).exists():
            broken.append(target)
    assert not broken, broken


def test_no_stale_references() -> None:
    """過去に除去した参照(旧 spec、旧 override 置き場)が復活していないこと。

    ROADMAP.md は E2E の発見記録として旧パス名を歴史的に言及するため除外する。
    """
    for path in MD_FILES:
        text = path.read_text()
        assert "tasuki-spec" not in text, path.name
        if path.name != "ROADMAP.md":
            assert ".claude/loop" not in text, path.name


def test_gates_catalog_has_25_perspectives() -> None:
    """レビュー観点カタログは #1〜#25 が揃っていること。"""
    text = (ROOT / "docs/GATES.md").read_text()
    rows = re.findall(r"^\| (\d+) \|", text, re.M)
    assert [int(n) for n in rows] == list(range(1, 26))


def test_g3_flow_wiring() -> None:
    """成果ゲート の配線: return_to 拡張、g3-returned の付与、ready 化順序の文書整合。"""
    gates = (ROOT / "docs/GATES.md").read_text()
    assert "decomposer | worker | implementation" in gates
    loop = (ROOT / "commands/loop.md").read_text()
    assert "`gate:outcome-returned` を付け" in loop
    assert "2f を再判定" in loop
    ops = (ROOT / "docs/OPERATIONS.md").read_text()
    assert "成果ゲートの PASS の後" in ops


def test_phase3_full_loop_wiring() -> None:
    """フェーズ3の配線: 受理ゲート、decomposer 起動と起票、循環検出、レイヤー合流、統合ゲート。"""
    loop = (ROOT / "commands/loop.md").read_text()
    assert "受理ゲート" in loop
    assert "`tasuki-decomposer` へ委譲" in loop
    assert "via tasuki-decomposer" in loop
    assert "循環を検出したらエラー" in loop
    assert "すべて人間にマージされるまで進まない" in loop
    assert "統合ゲート" in loop
    assert "親 issue の close は人間が行う" in loop
    # レビュー修正: 遡及適用禁止、分割案の永続化、マージごとの CI 再確認、不採用クローズ
    assert "遡及適用しない" in loop
    assert "分割案 YAML は `<details>` に畳む" in loop and "分割案の永続化" in loop
    assert "1件マージされるごとに残る ready PR の check-runs を再確認" in loop
    assert "不採用クローズ" in loop
    assert "integration フェーズ" in loop


def test_security_threat_model_documented() -> None:
    """信頼境界(v1 は信頼 issue 限定)が SECURITY.md と loop-init に明記されていること。"""
    sec = (ROOT / "docs/SECURITY.md").read_text()
    assert "信頼できるリポジトリでのみ使う" in sec
    assert "sandbox" in sec  # v2 ハードニングの言及
    init = (ROOT / "commands/loop-init.md").read_text()
    assert "信頼境界の確認" in init
    assert "worker/verifier に流れる" in init


def test_readme_has_flow_and_install() -> None:
    """README に処理フローの mermaid 図と、導入・前提の節があること。"""
    r = (ROOT / "README.md").read_text()
    assert "```mermaid" in r
    assert "flowchart" in r
    assert "--plugin-dir" in r  # 導入方法
    assert "## 前提" in r


def test_verdict_comment_human_readable() -> None:
    """verdict コメントは人間可読 markdown を主とし JSON を details に畳む書式を定めること。"""
    sk = (ROOT / "skills/gate-review/SKILL.md").read_text()
    assert "人間可読" in sk
    assert "<details>" in sk
    loop = (ROOT / "commands/loop.md").read_text()
    assert "<details>" in loop and "生の JSON / YAML をそのまま貼らない" in loop
    # 受理と分割と統合の verdict 記録も人間可読へ揃え、旧表現を残さないこと
    assert "verdict は親 issue にコメントで記録する(冪等)。" not in loop
    # 分割案 YAML を生で全文添付しないこと(details に畳む)
    assert "分割案 YAML を全文添付" not in loop
    # verifier の JSON をそのまま貼らない旨を定めること
    assert "そのまま issue に貼らない" in loop


def test_mermaid_skill_teaches_judgment_not_templates() -> None:
    """汎用 mermaid skill が「描くか」「どの図種か」の判断と記法を持つこと。"""
    sk = (ROOT / "skills/mermaid/SKILL.md").read_text()
    assert "図にするかを決める" in sk  # 描かない判断がある
    assert "図種を決める" in sk
    assert "stateDiagram-v2" in sk
    assert "gantt" in sk  # 選ばない判断
    # 凡例をグラフ内 subgraph にしない規則(今回の欠陥の再発防止)
    assert "凡例をグラフの中に作らない" in sk
    assert "linkStyle" in sk  # 凡例が線の番号を壊すこと
    # GitHub 固有の落とし穴(調査で確認した事実)
    assert "`theme` を指定しない" in sk  # ダーク自動追随を殺すため
    assert "elk" in sk  # 無言で dagre にフォールバックする
    assert "info" in sk  # バージョンの自己確認手順
    assert "accTitle" in sk  # 代替テキスト


def test_plan_comment_skill_makes_diagram_conditional() -> None:
    """tasuki 固有 skill が図を条件付きにし、汎用 mermaid skill を参照すること。"""
    sk = (ROOT / "skills/plan-comment/SKILL.md").read_text()
    assert "図を描く条件" in sk
    assert "合流または分岐" in sk  # 閾値
    assert "tasuki:mermaid" in sk  # skill 間の参照
    # 旧 skill と、4部構成の無条件強制が残っていないこと
    assert not (ROOT / "skills/plan-diagram").exists()
    for path in ("commands/loop.md", "commands/loop-status.md"):
        text = (ROOT / path).read_text()
        assert "tasuki:plan-comment" in text, path
        assert "plan-diagram" not in text, path
        assert "4部構成" not in text, path


def test_gm_is_hybrid() -> None:
    """形式ゲート のハイブリッド化(checks-local / checks-ci)が docs と手順の両方に現れること。"""
    assert "checks-local" in (ROOT / "docs/OPERATIONS.md").read_text()
    loop_text = (ROOT / "commands/loop.md").read_text()
    assert "checks-local" in loop_text and "checks-ci" in loop_text


_NAKAGURO_ALLOWED = (
    "中黒",  # CLAUDE.md の規約文そのもの
    "ドラム・バッファー・ロープ",  # TOC の固有名詞(カタカナ複合語であって並列ではない)
)


def _prose_lines(path: Path) -> list[tuple[int, str]]:
    """コード塊を除いた地の文の行を返す。"""
    lines: list[tuple[int, str]] = []
    in_code = False
    for i, line in enumerate(path.read_text().split("\n"), 1):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if not in_code:
            lines.append((i, line))
    return lines


_WRITING_TARGETS = [
    ROOT / "README.md",
    ROOT / "CLAUDE.md",
    *sorted((ROOT / "docs").glob("*.md")),
    *sorted((ROOT / "commands").glob("*.md")),
    *sorted((ROOT / "agents").glob("*.md")),
    *sorted((ROOT / "skills").glob("*/SKILL.md")),
]


@pytest.mark.parametrize("path", _WRITING_TARGETS, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_no_nakaguro_in_parallel_enumeration(path: Path) -> None:
    """日本語の並列に中黒を使わない(CLAUDE.md の文体規約)。

    規約は書かれていても強制されていなければ守られない。ここで機械的に固定する。
    """
    offenders = [
        (i, line.strip())
        for i, line in _prose_lines(path)
        if "・" in line and not any(tok in line for tok in _NAKAGURO_ALLOWED)
    ]
    assert not offenders, offenders


def test_baton_contract_covers_set_signals() -> None:
    """契約の書き方 skill が 分割ゲート の集合レベル基準(set_signals)も教えること。

    too_*_signals だけでは、依存の循環や孤児要件のような集合の欠陥を書けない。
    """
    sk = (ROOT / "skills/baton-contract/SKILL.md").read_text()
    assert "set_signals" in sk
    for token in ("依存の循環", "孤児", "親予算"):
        assert token in sk, token


def test_preship_review_phase_defined() -> None:
    """出荷前レビュー(5観点)と security スキャンの実施フェーズが定義されていること。"""
    loop = (ROOT / "commands/loop.md").read_text()
    assert "### 2g. 出荷前レビュー" in loop
    assert "/code-review" in loop
    assert "/claude-security:claude-security" in loop
    assert "1観点ずつ指定して5回に分ける" in loop  # 一度に回さない
    for kanten in (
        "設計と統合",
        "正しさと境界条件",
        "テストの妥当性",
        "複雑さと可読性",
        "運用影響",
    ):
        assert kanten in loop, kanten
    # 所見を鵜呑みにしない指示(古いツリー由来の所見が混ざるため)
    assert "そのまま信じない" in loop
    # このリポジトリ自身の開発フローにも同じ関門があること
    claude_md = (ROOT / "CLAUDE.md").read_text()
    assert "PR を作る前の関門" in claude_md
    assert "/code-review" in claude_md and "/claude-security:claude-security" in claude_md


def test_security_review_slash_command_removed() -> None:
    """組み込みの /security-review への参照を残さないこと(claude-security に統一)。"""
    for path in _WRITING_TARGETS:
        assert "/security-review" not in path.read_text(), path.name


def test_readme_explains_gate_symbols() -> None:
    # 記号ではなく名前で説明していること(識別子は英語で別列に置く)
    r = (ROOT / "README.md").read_text()
    assert "## ゲートの一覧" in r
    for symbol, name in (
        ("受理ゲート", "受理"),
        ("分割ゲート", "分割"),
        ("着手ゲート", "着手"),
        ("形式ゲート", "形式"),
        ("成果ゲート", "成果"),
        ("統合ゲート", "統合"),
    ):
        assert f"**{symbol}**" in r, symbol
        assert name in r, name
    # 説明が、記号を最初に使う「処理の流れ」より前にあること
    assert r.index("## ゲートの一覧") < r.index("## 処理の流れ")


def test_loop_command_keeps_least_privilege() -> None:
    """orchestrator の Bash 権限を丸ごと許可しないこと(最小権限)。

    checks-local の provider 実行に必要な権限は言語 pack が決めるため、core では
    宣言せず loop-init が導入先へ提案する。
    """
    head = (ROOT / "commands/loop.md").read_text().split("---")[1]
    allowed = next(line for line in head.split("\n") if line.startswith("allowed-tools:"))
    assert "Bash(" in allowed, allowed
    assert not any(tok.strip() == "Bash" for tok in allowed.split(":", 1)[1].split(",")), allowed
    init = (ROOT / "commands/loop-init.md").read_text()
    assert "checks-local の実行権限を提案する" in init
