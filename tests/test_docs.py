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
    assert "全子が統合ブランチへ取り込まれたら進む" in loop
    assert "統合ゲート" in loop
    assert "親 issue の close も人間が行う" in loop
    # レビュー修正: 遡及適用禁止、分割案の永続化、マージごとの CI 再確認、不採用クローズ
    assert "遡及適用しない" in loop
    assert "分割案 YAML は `<details>` に畳む" in loop and "分割案の永続化" in loop
    assert "1件取り込むごとに、統合ブランチ上で checks-local を再実行" in loop
    assert "不採用クローズ" in loop
    assert "`gates.integration.phase`" in loop  # フェーズ名はハードコードせず契約から引く


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
    assert "### 3c. 出荷前レビュー(親 PR、最終コード評価)" in loop
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


def test_readme_documents_model_assignment() -> None:
    """README が役割ごとのモデル配分と、その根拠(非対称性)を示すこと。"""
    r = (ROOT / "README.md").read_text()
    assert "## 誰がどのモデルで動くか" in r
    for role in ("orchestrator", "worker", "verifier", "decomposer"):
        assert role in r, role
    for model in ("Opus", "Sonnet", "Haiku"):
        assert model in r, model
    assert "誤 PASS" in r and "誤 REJECT" in r  # 配分の根拠
    # agent 定義の model と README の記述が食い違わないこと
    expected = {"worker": "sonnet", "verifier": "sonnet", "decomposer": "sonnet"}
    for name, model in expected.items():
        text = (ROOT / f"agents/{name}.md").read_text()
        assert f"model: {model}" in text, (name, model)
    # 配分を選んだ理由が書かれていること(根拠なく変えられないようにする)
    assert "コストの支配項を worker レートに留める" in r


def test_readme_explains_mechanism() -> None:
    """README が「動く仕組み」(状態、停止装置、二段検査、自己検査の禁止)を説明すること。"""
    r = (ROOT / "README.md").read_text()
    assert "## 動く仕組み" in r
    for heading in ("状態はすべて GitHub にある", "暴走しない仕組み", "検査が二段になっている"):
        assert heading in r, heading
    # 再開できること、fail-closed、マージは人間、という核が落ちていないこと
    assert "続きから再開する" in r
    assert "fail-closed" in r
    assert "マージは常に人間" in r


def test_operations_documents_preship_review_and_output_rules() -> None:
    """運用文書に出荷前レビューと、issue 出力の原則があること。"""
    ops = (ROOT / "docs/OPERATIONS.md").read_text()
    assert "## 出荷前レビュー" in ops
    assert "/code-review" in ops and "/claude-security:claude-security" in ops
    assert "## issue に残す出力の原則" in ops
    assert "<details>" in ops


def test_diagrams_are_conditional_and_renderable() -> None:
    """図は構造がある箇所にだけ置き、識別子は ASCII、代替テキストを持つこと。"""
    import re

    for path in (ROOT / "README.md", ROOT / "docs/DESIGN.md"):
        for block in re.findall(r"```mermaid\n(.*?)```", path.read_text(), re.S):
            assert "accTitle:" in block and "accDescr:" in block, path.name
            # ノード ID に日本語を使わない(ID は ASCII、表示ラベルのみ日本語)
            ids = re.findall(r"^\s*([^\s\[{(]+)[\[{(]", block, re.M)
            bad = [i for i in ids if not re.fullmatch(r"[A-Za-z0-9_-]+", i)]
            assert not bad, (path.name, bad)


def test_common_gate_rules_are_single_source() -> None:
    """ラベル整理と冪等の規則を、ゲートごとに散らさず共通規則として1箇所に置くこと。

    受理ゲートにしかラベル整理が書かれておらず、他のゲートでは triage が
    滞留し続けていた。共通規則にすることで書き漏れを構造的に防ぐ。
    """
    loop = (ROOT / "commands/loop.md").read_text()
    assert "## ゲート共通の規則" in loop
    assert "### ラベルの整理" in loop and "### コメントは冪等に投稿する" in loop
    # 共通規則が個々のゲートより前にあること
    assert loop.index("## ゲート共通の規則") < loop.index("### 2b.")
    # 各ゲートの PASS 付与が片付けに言及していること(判定条件の出現ではなく付与の箇所)
    import re

    for gate in ("intake", "split", "start", "outcome", "integration"):
        assigns = list(re.finditer(rf"`gate:{gate}-passed` を付け", loop))
        assert assigns, gate
        assert any("片付け" in loop[m.start() : m.start() + 120] for m in assigns), gate


def test_degenerate_cases_documented() -> None:
    """縮退した形(子1件、依存なし、全マージ済み、子0件)の扱いが書かれていること。"""
    loop = (ROOT / "commands/loop.md").read_text()
    assert "縮退した形の扱い" in loop
    for case in ("子が1件", "依存がまったく無い", "全子 issue がマージ済み", "子が0件"):
        assert case in loop, case


def test_artifact_placement_is_documented() -> None:
    """親 issue と子 issue と draft PR の役割分担が根拠つきで書かれていること。

    実装方針を親に置くと俯瞰できなくなり、issue 本文に置くと着手ゲートに反する。
    細部は動くコードの diff で見るほうが早い、という判断も残す。
    """
    gates = (ROOT / "docs/GATES.md").read_text()
    assert "### 実装方針をどこに置くか" in gates
    for place in ("親 issue", "子 issue", "draft PR"):
        assert place in gates, place
    assert "仕様書にしない" in gates
    assert "動くコードの diff" in gates
    worker = (ROOT / "agents/worker.md").read_text()
    assert "仕様書にしない" in worker


def test_operational_gaps_are_specified() -> None:
    """運用の観点(手動停止、単一親、契約の読み取り時点、gh 失敗)が定義されていること。

    Fable レビューで見つけた欠落。いずれも実運用で最初に踏む類のもの。
    """
    loop = (ROOT / "commands/loop.md").read_text()
    # 人間が理由を問わず引けるブレーキ
    assert "loop:pause" in loop
    assert "実行中の worker は完了まで走り切ってよい" in loop  # 強制中断はしない
    # 同時に回す親のスコープ
    assert "同時に自走させる親 issue は1つとする" in loop
    # 契約は run 開始時に固定
    assert "run は開始時に読んだ契約で最後まで走る" in loop
    # gh 失敗は fail-stop(握りつぶして進まない)
    assert "run を止めて失敗箇所を報告する" in loop
    # ラベルが作成対象に含まれ、status が表示すること
    assert "loop:pause" in (ROOT / "commands/loop-init.md").read_text()
    assert "loop:pause" in (ROOT / "commands/loop-status.md").read_text()
    assert "loop:pause" in (ROOT / "README.md").read_text()


def test_integration_branch_model() -> None:
    """人間の最終判断が親 PR の1回に集約されていること(統合ブランチ方式)。

    子 PR を人間が個別にマージする設計は「人間はループの外」という思想に反する。
    default branch への反映点は親 PR のマージだけとする。
    """
    loop = (ROOT / "commands/loop.md").read_text()
    assert "loop/parent-<親番号>" in loop  # 統合ブランチ
    assert "人間が最終的に見るのはこの親 PR だけ" in loop
    assert "人間は子 PR をマージしない" in loop
    assert "orchestrator が子 PR を統合ブランチへマージする" in loop
    # 子 PR は Closes を使わない(統合ブランチ向けでは機能しない)
    worker = (ROOT / "agents/worker.md").read_text()
    assert "`Closes` は使わない" in worker
    assert "Refs #" in worker
    # 親 PR に Closes を集約
    assert "`Closes #<番号>` を列挙する" in loop
