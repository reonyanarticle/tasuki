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
    # 撤回した拡張(調査と実験)の実体への参照が復活していないこと。
    # ROADMAP は撤回の記録としてこれらの名前を歴史的に言及するため除外する。
    removed = ("tasuki-spec", ".claude/loop", "profiles/experiment.yaml", "profiles/research.yaml")
    for path in MD_FILES:
        text = path.read_text()
        assert "tasuki-spec" not in text, path.name
        if path.name == "ROADMAP.md":
            continue
        for token in removed:
            assert token not in text, (path.name, token)
    # plugin 側の実体も消えたままであること
    gone_paths = (
        "profiles/experiment.yaml",
        "profiles/research.yaml",
        "agents/researcher.md",
        "packs/docs",
    )
    for gone in gone_paths:
        assert not (ROOT / gone).exists(), gone


def test_design_tree_lists_existing_profiles() -> None:
    """DESIGN.md のディレクトリツリーが実在するプロファイルだけを挙げること。

    ツリーは手書きなので、ファイルを消してもツリーだけ古い状態が残る。
    """
    import re as _re

    body = (ROOT / "docs/DESIGN.md").read_text().split("## plugin ディレクトリ構成")[1]
    tree = body.split("```")[1]  # 見出し直後のコードフェンス1つだけを見る
    listed = set(_re.findall(r"([a-z]+)\.yaml", tree))
    actual = {p.stem for p in (ROOT / "profiles").glob("*.yaml")}
    assert listed >= actual, (listed, actual)
    assert listed - actual <= {"providers"}, (listed, actual)


def test_gates_catalog_has_25_perspectives() -> None:
    """レビュー観点カタログは25観点が名前で揃っていること(番号は持たない)。"""
    text = (ROOT / "docs/GATES.md").read_text()
    section = text.split("## レビュー観点カタログ")[1].split("\n## ")[0]
    rows = [
        line
        for line in section.splitlines()
        if line.startswith("| ") and not line.startswith("| 観点 |") and "---" not in line
    ]
    assert len(rows) == 25, len(rows)
    for name in ("要件充足性", "並行整合性", "ゲートの発振検知"):
        assert any(name in r for r in rows), name


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
    *sorted((ROOT / ".claude" / "rules").glob("*.md")),
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


_DATE_PATTERN = re.compile(r"20\d{2}-\d{2}|20\d{2}年")


@pytest.mark.parametrize("path", _WRITING_TARGETS, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_no_dates_in_docs(path: Path) -> None:
    """ドキュメントに日付を書かない(CLAUDE.md のドキュメント規約)。

    いつ対応したかはコミットとリリースが記録する。本文の日付は書いた瞬間から古くなる。
    """
    offenders = [(i, line.strip()) for i, line in _prose_lines(path) if _DATE_PATTERN.search(line)]
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
    assert "下表の5観点を1観点ずつ回す" in loop  # 一度に回さない(subagent で自動実行)
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
    # DESIGN のモデル表も同じ配分を指すこと(README と DESIGN の二重管理 drift の検出。
    # worker のモデルを変えた実績があり、そのとき両方の編集が必要だった)
    d = (ROOT / "docs/DESIGN.md").read_text()
    assert "worker を Sonnet に置き" in d
    assert "| 物量 | worker / verifier / decomposer | Sonnet |" in d


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
    assert "`preship_review`" in ops  # 自動実行の規模制御(人間起動は manual のみ)
    assert "/claude-security:claude-security" in ops
    assert "## issue に残す出力の原則" in ops
    assert "<details>" in ops


def test_diagrams_are_conditional_and_renderable() -> None:
    """図は構造がある箇所にだけ置き、識別子は ASCII、代替テキストを持つこと。

    ノード ID は行頭にだけ現れるとは限らない(`A --> B["..."]` の B のように
    矢印やラベルの後ろにも書ける)。行頭起点で拾うと flowchart の1行目しか
    検査されないため、行内も走査する。
    """
    import re

    # 図の指示行はノード宣言ではない(accDescr の日本語が ID と誤検出される)
    directive = re.compile(
        r"^\s*(accTitle|accDescr|%%|style|classDef|class\s|click|linkStyle|direction)"
    )
    # 行頭 / 空白 / 矢印の先 / ラベル区切り(`|`)/ 連結(`&`)の直後に来る、
    # 形状の開き括弧(`[` `(` `{`)を伴うトークンをノード ID とみなす
    node = re.compile(r"(?:^|[\s|&>])([^\s\[\](){}|>]+)[\[({]")
    for path in (ROOT / "README.md", ROOT / "docs/DESIGN.md"):
        for block in re.findall(r"```mermaid\n(.*?)```", path.read_text(), re.S):
            assert "accTitle:" in block and "accDescr:" in block, path.name
            # ノード ID に日本語を使わない(ID は ASCII、表示ラベルのみ日本語)
            ids: list[str] = []
            for line in block.splitlines():
                if directive.match(line):
                    continue
                ids += node.findall(re.sub(r'"[^"]*"', '""', line))  # 引用ラベルは除く
            bad = [i for i in ids if not re.fullmatch(r"[A-Za-z0-9_-]+", i)]
            assert not bad, (path.name, bad)
            if block.lstrip().startswith("flowchart"):
                assert len(set(ids)) >= 2, (path.name, "flowchart のノードを拾えていない")


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
    assert "orchestrator が子 PR を ready 化してから統合ブランチへマージする" in loop
    # 子 PR は Closes を使わない(統合ブランチ向けでは機能しない)
    worker = (ROOT / "agents/worker.md").read_text()
    assert "`Closes` は使わない" in worker
    assert "Refs #" in worker
    # 親 PR に Closes を集約
    assert "`Closes #<番号>` を列挙する" in loop


def test_replan_path_is_designed() -> None:
    """走行中の親要件変更に正式経路(loop:replan)があること。

    経路が無いと、本文編集のズレは統合ゲートの孤児要件まで潜伏する。
    黙った自動追従(編集のたびに再分割)も、意図しない opus 消費になるため退ける。
    """
    loop = (ROOT / "commands/loop.md").read_text()
    assert "loop:replan" in loop
    assert "要件変更の検知" in loop  # §0 の機械検知(通知のみ)
    assert "再計画は行っていない" in loop  # ラベル無し編集は通知に留める
    assert "差分分割モード" in loop
    assert "維持 / 改訂 / 追加 / 撤回" in loop
    assert "追い子" in loop  # 取り込み済みへの波及は巻き戻さず前進で適応
    assert "強制中断しない" in loop  # 発効は合流点
    # decomposer 側にモードがあること
    dec = (ROOT / "agents/decomposer.md").read_text()
    assert "差分分割モード" in dec
    assert "改訂と撤回を宣言できるのは統合ブランチへ未取り込みの子だけ" in dec
    # ラベルの作成と可視化
    assert "loop:replan" in (ROOT / "commands/loop-init.md").read_text()
    assert "loop:replan" in (ROOT / "commands/loop-status.md").read_text()
    assert "loop:replan" in (ROOT / "README.md").read_text()


def test_base_sync_checkpoints_are_designed() -> None:
    """ループ外開発(hotfix 等)と共存する default branch の定点取り込みがあること。

    定点が無いと親 PR の base が古いまま承認され、承認した差分とマージ結果がずれる。
    """
    loop = (ROOT / "commands/loop.md").read_text()
    assert "定点0" in loop and "定点1" in loop and "定点2" in loop
    assert "rebase はしない" in loop  # 子 PR の参照 SHA を書き換えない
    assert "merge-base が default branch の先端と一致していること" in loop  # 3c 入場条件
    assert "hotfix 側に特別な経路は要らない" in loop
    # worker 実行中は base を動かさない
    assert "worker が実行中の間は取り込まない" in loop


def test_base_sync_does_not_flag_upstream_changes() -> None:
    """定点取り込みの検知が hotfix 由来の変更を worker の改変と誤認しないこと。"""
    loop = (ROOT / "commands/loop.md").read_text()
    assert "default branch 側から来た変更" in loop
    assert "worker の改変と誤認しない" in loop


def test_replan_refiling_matches_open_children_only() -> None:
    """replan の再起票の冪等判定が撤回済み(closed)の子に誤マッチしないこと。"""
    loop = (ROOT / "commands/loop.md").read_text()
    assert "open の子だけと突き合わせる" in loop


def test_section0_numbering_consistent() -> None:
    """§0 の項番が連番であり、本文中の §0.N 参照が実在する項番を指すこと。

    項目挿入で番号が重複すると、§0.N の参照が別の項目を指したまま読める(実害を踏んだ)。
    """
    loop = (ROOT / "commands/loop.md").read_text()
    sec0 = loop.split("## 0. ")[1].split("\n## ")[0]
    nums = [int(m) for m in re.findall(r"^(\d+)\. ", sec0, re.M)]
    assert nums == list(range(1, len(nums) + 1)), nums
    refs = {int(m) for m in re.findall(r"§0\.(\d+)", loop)}
    assert refs <= set(nums), refs


def test_draft_command_is_designed() -> None:
    """起票支援(/tasuki:draft)が、独自基準を持たず契約の目盛りをシフトレフトすること。

    基準が2つあると「draft を通ったのに受理ゲートで落ちる」が起きる。
    また実装方式が本文に入ると、待ち位置(解き方は未指定)に反して TOO_CONCRETE になる。
    """
    d = (ROOT / "commands/draft.md").read_text()
    assert "`gates.intake.phase`" in d  # 契約から引く(フェーズ名を書かない)
    assert "このコマンド独自の基準を持たない" in d
    assert "実装方式は本文に書かない" in d
    assert "`too_concrete_signals`" in d  # 何が「解き方」かも契約から引く
    # 実走で生成本文に絶対日付が入った(issue は完走まで参照され続ける文書である)
    assert "issue 本文に絶対日付を書かない" in d
    # 自己照合は独立判定より弱いので、その旨を起票者に伝える
    assert "割れなかったこと自体を起票者に伝える" in d
    assert "参考メモ" in d
    assert "ラベルは付けず、verdict も issue に残さない" in d  # 事前審査は正式判定でない
    assert "確認を得てから" in d  # 勝手に起票しない
    assert "裏取り" in d
    assert "/tasuki:draft" in (ROOT / "README.md").read_text()


def test_field_review_fixes_are_designed() -> None:
    """実運用レビューで確定した修正が手順と agent 定義に反映されていること。"""
    loop = (ROOT / "commands/loop.md").read_text()
    assert "インラインで渡す" in loop  # 被判定物の直前取得(揮発ファイル禁止)
    assert "ready 化してから統合ブランチへマージする" in loop  # 2g の draft 対応
    assert "空コミットを1つ置いてから" in loop  # 親 PR 作成の前提
    assert "長時間ジョブの公式プロトコル" in loop
    assert "shell のワンライナーで行わない" in loop  # 起票の1ズレ事故
    assert "defaultBranchRef" in loop  # main を仮定しない
    assert "assignee を手で外すと" in loop  # 停止時の即時再入
    worker = (ROOT / "agents/worker.md").read_text()
    assert "PID、ログパス、完了の判定条件" in worker
    assert "成果物の置き場" in worker
    init = (ROOT / "commands/loop-init.md").read_text()
    assert "既存ゲートと外部レビューツールの棚卸し" in init
    assert "判定例(fixture)の下書きを自動生成してよい" in init
    # 契約の但し書き(統制条件は要件側)
    for prof in ("profiles/development.yaml",):
        assert "要件でありここに含めない" in (ROOT / prof).read_text(), prof
    # 併用の制約(状態機械が重ならないこと)
    assert "対象 issue 集合が重ならない場合に限る" in (ROOT / "docs/INTEGRATION.md").read_text()
    # 直列親の依存(先行親の未マージ成果を worker が複製した実地事故の再発防止)
    assert "先行親の親 PR がマージされてから起動する" in loop
    # 長時間ジョブと stale 回収の干渉(ログ更新時刻を生存確認に含める。二重起動の防止)
    assert "ログの最終更新時刻と PID の生存も基準時刻の候補に含める" in loop
    # 長時間ジョブの打ち切りは wall-clock 上限を必須とする(ハングと低速の区別)
    dec2 = (ROOT / "agents/decomposer.md").read_text()
    assert "wall-clock の上限" in dec2


def test_trace_review_findings_are_fixed() -> None:
    """第6観点「手順のトレース」の試走が検出した8欠陥の修正が残っていること。"""
    loop = (ROOT / "commands/loop.md").read_text()
    assert "子 issue 本文と issue 番号、統合ブランチ名" in loop  # worker への受け渡し
    assert "`loop:triage` が付いた子には着手しない" in loop  # 裁定前の再実行防止
    assert "レビュー結果は親 PR のコメントに残す" in loop  # 3c の run またぎ
    assert "マージが conflict で拒否された場合" in loop  # 子 PR の conflict 分岐
    assert "着手も回収もしない" in loop  # 人間の手動 assign との判別
    assert "後着に譲って run を終了する" in loop  # 二重起動の競合緩和
    assert "orchestrator(メインセッション)が裁定する" in loop  # opus の low PASS を降格させない
    assert "解消専用の worker セッション(新規)に統合ブランチ向けの修正 PR" in loop  # 取り込み後の赤
    worker = (ROOT / "agents/worker.md").read_text()
    assert "--base <統合ブランチ>" in worker
    assert "統合ブランチとは限らない" in worker  # worktree base の明示
    # 観点自体が関門に定義されていること
    claude_md = (ROOT / "CLAUDE.md").read_text()
    assert "手順のトレース" in claude_md


def test_conventions_live_in_rules() -> None:
    """コード規約とドキュメント規約は .claude/rules/ が正であること(CLAUDE.md に写しを残さない)。"""
    assert (ROOT / ".claude/rules/code.md").exists()
    docs_rule = (ROOT / ".claude/rules/docs.md").read_text()
    assert "paths:" in docs_rule  # markdown 編集時に読み込まれる条件付きルール
    assert "日付を書かない" in docs_rule
    claude_md = (ROOT / "CLAUDE.md").read_text()
    assert ".claude/rules/" in claude_md  # 置き場所の案内はある
    assert "日付を書かない" not in claude_md  # 中身の写しは無い
    assert "tasuki-` 接頭辞" not in claude_md


def test_preship_review_runs_in_subagents() -> None:
    """3c の5観点レビューは orchestrator が subagent で自動実行すること(人間の起動を待たない)。"""
    loop = (ROOT / "commands/loop.md").read_text()
    assert "レビューは orchestrator が subagent で自動実行する" in loop
    assert "これは人間が起動するコマンドである" not in loop
    # セキュリティスキャンだけは人間案内のまま(別建て課金)
    assert "実行を人間に案内する" in loop
    # コスト制御: 固定5体ではなく契約の preship_review で規模を選ぶ
    assert "`preship_review` で制御する" in loop
    for mode in ("mode: full", "mode: scaled", "mode: manual"):
        assert mode in loop, mode
    import yaml

    for prof in ("profiles/development.yaml",):
        c = yaml.safe_load((ROOT / prof).read_text())
        assert c["preship_review"]["mode"] == "scaled", prof
        assert c["preship_review"]["fanout_threshold_lines"] > 0, prof


def test_worker_reports_used_skills_and_subagents() -> None:
    """レポートに参照 skill と委譲 subagent の欄があること(成果の前提を辿れるようにする)。"""
    import yaml

    fields = yaml.safe_load((ROOT / "profiles/development.yaml").read_text())["templates"][
        "report_required_fields"
    ]
    assert "参照した skill と委譲した subagent" in fields  # 欄の正は契約
    report_skill = (ROOT / "skills/loop-report/SKILL.md").read_text()
    assert "成果の前提を辿る欄がある契約では" in report_skill  # skill は欄名を写さず条件で書く
    worker = (ROOT / "agents/worker.md").read_text()
    assert "参照した skill と委譲した subagent の欄を必ず埋める" in worker


_KANTEN_BARE = re.compile(r"(?<![/\w])#\d+")
_ISSUE_NUM_REF = re.compile(r"(?:PR|親|子|issue) #\d+")


@pytest.mark.parametrize("path", _WRITING_TARGETS, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_references_are_readable(path: Path) -> None:
    """番号だけの参照を書かない(ドキュメント規約)。

    レビュー観点は番号でなく名前で参照する(「観点 #N」を書かない。カタログにも番号を置かない)。
    PR / issue 番号は本文の根拠にしない(読者がその番号を解決できる保証が無い)。
    ブランチ名 loop/parent-N は対象外。
    """
    offenders = []
    for i, line in _prose_lines(path):
        if "番号だけの参照" in line or "#123 で修正" in line:  # 規約文そのものが悪い例を引用する
            continue
        if _KANTEN_BARE.search(line):
            offenders.append((i, "観点番号に名前が無い", line.strip()[:60]))
        if _ISSUE_NUM_REF.search(line) and "loop/parent" not in line:
            offenders.append((i, "PR / issue 番号の参照", line.strip()[:60]))
    assert not offenders, offenders


def test_commands_declare_data_boundary_and_least_privilege() -> None:
    """未検証データを読むコマンドが、境界の宣言と最小権限を持つこと。

    セキュリティスキャンの指摘: 読み取り専用は文章の宣言では担保されない(権限で表現する)。
    引数が gh の呼び出しに入るコマンドは、値の検証を手順に持つ。
    """
    for name in ("loop-status", "draft"):
        text = (ROOT / f"commands/{name}.md").read_text()
        assert "data-boundary" in text, name  # 入力を未検証データとして扱う
        assert "Bash(gh *)" not in text, name  # 書き込み系まで前承認する粗い許可を持たない
    # 引数が gh の呼び出しに入る(番号を取る)コマンドは値を検証する。
    # draft の引数は自由文で、本文ファイル経由でしか使われないため対象外。
    assert "正の整数であることを確認" in (ROOT / "commands/loop-status.md").read_text()
    # 手順が使う操作は許可に含まれていること(絞り込みで機能を壊さない)
    loop = (ROOT / "commands/loop.md").read_text()
    for grant in (
        "Bash(gh issue:*)",
        "Bash(gh pr:*)",
        "Bash(gh label:*)",
        "Bash(git worktree:*)",
        "Bash(git merge:*)",
        "Bash(git push:*)",
        "Write",
    ):
        assert grant in loop.split("---")[1], grant  # frontmatter に存在する
    assert "許可されていない操作が必要になったら、実行せずに中断して報告する" in loop
    for grant in ("Bash(gh issue create:*)", "Write"):
        assert grant in (ROOT / "commands/draft.md").read_text().split("---")[1], grant

    draft = (ROOT / "commands/draft.md").read_text()
    assert "Bash(git *)" not in draft  # 事実上の任意実行を持たない
    assert "default branch(信頼された版)から** 読む" in draft  # 物差しは検めた版から
    assert "author_association" in draft  # 代理起票が opt-in を素通りする件の明示


def test_security_reflects_implemented_hardening() -> None:
    """SECURITY.md が v1 で実装済みの対策を v2 予約に残していないこと。

    allowlist のサブコマンド絞り込みは v1 で実装した。予約側に残すと、
    読者は未対応と誤読し、実装済みの対策を二重に作る。
    """
    sec = (ROOT / "docs/SECURITY.md").read_text()
    # 守る範囲(実装済み)に移っていること
    assert "手順が実際に使う操作だけを列挙する" in sec
    assert "注入への完全な防御ではない" in sec  # 効果の限界も併記
    # 予約側には「残余の遮断」だけが残る
    reserved = sec.split("## v2 のハードニング")[1]
    assert "allowlist の残余の遮断" in reserved
    assert "サブコマンド単位に絞るか hook" not in reserved  # 旧文(未実装扱い)が消えている
    # 実装の現物と一致していること
    loop_front = (ROOT / "commands/loop.md").read_text().split("---")[1]
    assert "Bash(git *)" not in loop_front and "Bash(gh *)" not in loop_front


def test_contracts_sample_matches_profiles() -> None:
    """CONTRACTS.md の契約サンプルが実プロファイルの判定シグナルからずれないこと。

    サンプルは正典を名乗るため、profiles/ の変更(承認サイズ、但し書き)を写し損ねると
    導入先が古いスキーマを正として上書きしてしまう。
    """
    sample = (ROOT / "docs/CONTRACTS.md").read_text()
    assert "完了の定義が1回のレビューで判断できる範囲を超えている" in sample
    assert "要件でありここに含めない" in sample


def test_loop_init_ships_via_bootstrap_pr() -> None:
    """loop-init の生成物は PR で入る(機械は PR 作成まで、default branch への反映は人間のマージ)。

    手動コミットを人間に求める形は、関与を承認1回に純化する思想に反する(実際に一度誤設計した)。
    """
    init = (ROOT / "commands/loop-init.md").read_text()
    assert "ブートストラップ用ブランチ(`tasuki/init`)にコミットして push し" in init
    assert "default branch へ直接 push しない" in init
    assert "反映は人間のマージだけ" in init
    frontmatter = init.split("---")[1]
    for grant in ("Bash(git commit:*)", "Bash(git push:*)", "Bash(gh pr create:*)"):
        assert grant in frontmatter, grant


def test_code_review_round2_fixes() -> None:
    """2周目のレビュー所見(クラッシュ孤児、生存確認の権限、フォールバック等)の修正が残っていること。"""
    loop = (ROOT / "commands/loop.md").read_text()
    assert "先に「⏳ 着手(run 識別つき)」コメントを1件残し、その直後に assign する" in loop
    for grant in ("Bash(ps:*)", "Bash(tail:*)"):
        assert grant in loop.split("---")[1], grant  # 長時間ジョブの生存確認に必要
    assert "head ブランチが `loop/parent-` で始まる" in loop  # 親 PR の判定基準
    assert "Bash(gh --version)" in (ROOT / "commands/loop-init.md").read_text().split("---")[1]
    draft = (ROOT / "commands/draft.md").read_text()
    assert "Bash(git fetch:*)" in draft.split("---")[1]
    assert "origin/<default branch>" in draft  # 追跡ブランチの古さを踏まない
    status_md = (ROOT / "commands/loop-status.md").read_text()
    assert "head ブランチが `loop/parent-` で始まる" in status_md


def test_undone_items_have_issue_drafts() -> None:
    """3c の承認コメントが「やらなかったこと」の issue 下書きを添え、起票はしないこと。"""
    loop = (ROOT / "commands/loop.md").read_text()
    assert "起票できる下書き" in loop
    assert "**起票はしない**" in loop


def test_external_author_optin_is_designed() -> None:
    """外部起票の親は tasuki:accepted の opt-in が無ければループ対象外であること。"""
    loop = (ROOT / "commands/loop.md").read_text()
    assert "起票者の信頼チェック" in loop
    assert "author_association" in loop
    assert "tasuki:accepted" in loop
    # ラベル作成と文書への反映
    assert "tasuki:accepted" in (ROOT / "commands/loop-init.md").read_text()
    sec = (ROOT / "docs/SECURITY.md").read_text()
    assert "tasuki:accepted" in sec
    # opt-in は本文にのみ効く、という限界の明示(過大主張しない)
    assert "コメントまでは守れない" in sec


def test_child_visibility_hygiene() -> None:
    """子 issue は機械の作業単位として、取り込み時に閉じ、一覧から絞れること(案C)。"""
    loop = (ROOT / "commands/loop.md").read_text()
    assert "tasuki:child" in loop
    assert "子 issue を close する" in loop
    assert "保険として残す" in loop  # Closes 列挙の位置づけ
    init = (ROOT / "commands/loop-init.md").read_text()
    assert "tasuki:child" in init
    assert "no:parent-issue" in init
    assert "no:parent-issue" in (ROOT / "README.md").read_text()


def test_parent_pr_is_designed_for_approval() -> None:
    """親 PR が「コードを読まずに何を承認するか分かる」道具として設計されていること。"""
    import yaml

    fields = yaml.safe_load((ROOT / "profiles/development.yaml").read_text())["templates"][
        "parent_pr_required_fields"
    ]
    for f in ("何が変わるか", "承認してほしい判断", "やらなかったこと", "リスクと戻し方"):
        assert f in fields, f
    loop = (ROOT / "commands/loop.md").read_text()
    # 裁量の決定を実装方針から親 PR へ集約する規則
    assert "承認してほしい判断" in loop
    assert "「選択と理由」から" in loop
    # ready 化は 3c 入場時(人間に draft を渡さない)
    assert "親 PR を ready 化する" in loop
    # 順序: 機械のレビュー → 承認材料の投稿 → ready 化(先に承認を出すと差し戻しで撤回になる)
    auto_review = "レビューは orchestrator が subagent で自動実行する"
    assert loop.index(auto_review) < loop.index("親 PR を ready 化する")
    rev_sec = "### 3c-1. レビューの実行"
    assert loop.index(rev_sec) < loop.index("### 3c-2. 承認材料の投稿と ready 化")


def test_parent_pr_body_is_staged_and_traceable() -> None:
    """親 PR 本文が「大観が先、承認材料は CI 全緑の後」の2段構成であること。

    検証が通る前に承認の文言を書くと、赤のまま「承認してほしい」と読める
    本文が世に出る。判断には出どころ(どの子)と検証点を必ず添える。
    """
    loop = (ROOT / "commands/loop.md").read_text()
    assert "前半(作成時から置く): 大観" in loop
    # 承認材料は本文の編集ではなく新規コメント(タイムラインの最後に現れる)
    assert "「新規コメント」として投稿する" in loop
    assert "レビューが所見なし、または所見の修正を取り込み終えてから" in loop
    assert "どの子(#N)で決めたか" in loop
    assert "どこで検められたか" in loop
    assert "どの子の作業で見つかったかを添える" in loop


def test_toc_adaptation_is_reflected() -> None:
    """TOC の記述が新構造(制約通過の最小化+親予算のバッチ)に更新されていること。"""
    phil = (ROOT / "docs/PHILOSOPHY.md").read_text()
    assert "親 PR の1回に最小化" in phil
    gates = (ROOT / "docs/GATES.md").read_text()
    assert "親の粒度" in gates
    # A: 受理ゲートが承認サイズを見る
    skill = (ROOT / "skills/gate-review/SKILL.md").read_text()
    assert "承認のサイズを検める" in skill  # 契約シグナルの照合として言い直した
    # C: レイヤー報告は覗いてよい任意のチェックポイント
    loop = (ROOT / "commands/loop.md").read_text()
    assert "覗いてよい任意のチェックポイント" in loop


def test_loop_report_skill_pulls_fields_from_contract() -> None:
    """レポート skill が欄名を契約から引くこと(プロファイル固有の欄を skill に写さない)。

    3つ目のプロファイルを試作したとき、skill に development の欄が literal に
    書かれていたため「読み替え節」を足す羽目になった(その成果物には受け入れ条件も
    テストも無く、共通の必須構成に忠実な報告は成果ゲートの門前払いを必ず落ちた)。
    欄の正を契約に一本化し、skill には共通規則だけを残す。
    """
    sk = (ROOT / "skills/loop-report/SKILL.md").read_text()
    assert "`report_required_fields`" in sk
    assert "欄の意味は契約の欄コメントが定める" in sk
    assert "プロファイルの読み替え" not in sk  # 読み替え節を復活させない


def test_preship_review_recovers_from_crashed_review() -> None:
    """レビュー結果コメントが無い状態からの再入が、モードで分岐すること。

    自動実行の設定で「待ちを維持」を選ぶと、ラベルだけが残って親 PR が
    draft のまま無期限に止まり、triage inbox にも上がらない。
    """
    loop = (ROOT / "commands/loop.md").read_text()
    assert "コメントが無い場合の扱いは契約の `preship_review.mode` で分かれる" in loop
    assert "レビューを起動し直す" in loop


def test_providers_definition_has_a_home_in_the_target_repo() -> None:
    """checks-local が読む providers 定義を loop-init が導入先に書き出すこと。

    plugin の packs/ は導入先リポジトリに存在しないため、書き出しが無いと
    「default branch から providers を読む」の参照先が無い。
    """
    init = (ROOT / "commands/loop-init.md").read_text()
    assert "`.tasuki/providers.yaml` へ書き出す" in init
    loop = (ROOT / "commands/loop.md").read_text()
    assert "`.tasuki/providers.yaml`" in loop
    # 導入先に存在しないパスを改変検知の対象にしない
    assert "packs/**/providers.yaml" not in loop


def test_gate_review_skill_judges_only_by_contract() -> None:
    """判定側の skill が契約だけを物差しにすること(存在しない欄で差し戻さない)。

    かつては development の欄名を具体列挙し、別プロファイル用の読み替え節で打ち消していた。
    具体列挙が原則に勝つ構造を廃し、分割基準と欄の意味を契約から引く。
    """
    sk = (ROOT / "skills/gate-review/SKILL.md").read_text()
    assert "契約に存在しない欄を根拠に差し戻さない" in sk
    assert "`split_criteria`" in sk  # 分割基準は契約から引く
    assert "`report_required_fields`" in sk  # レポート欄も契約から引く
    assert "プロファイルでの読み替え" not in sk  # 読み替え節を復活させない


def test_section_references_carry_names() -> None:
    """手順書内部の節参照(§)に節名を併記すること(ドキュメント規約)。

    番号だけの参照は、読み手が該当節を探すまで意味が取れない。
    規約は .claude/rules/docs.md にあり、書かれているだけでは守られないためここで固定する。
    """
    pattern = re.compile(r"§[0-9]+(?:\.[0-9]+)?(?:[a-z](?:-[0-9])?)?")
    offenders = []
    for path in sorted((ROOT / "commands").glob("*.md")):
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            if line.startswith("#") or "§番号" in line:  # 見出しと規約文そのものは除く
                continue
            for m in pattern.finditer(line):
                if not line[m.end() :].startswith("("):
                    offenders.append(f"{path.name}:{lineno}: {m.group()}")
    assert not offenders, offenders


def test_scan_artifacts_are_ignored() -> None:
    """セキュリティスキャンの作業ディレクトリが誤ってコミットされないこと。

    撤回前の全文書の写しを含むため、追跡すると検索が二重ヒットし、
    古い記述が生き返ったように見える。
    """
    ignored = (ROOT / ".gitignore").read_text()
    assert "CLAUDE-SECURITY-*/" in ignored


_PLUGIN_PATH = re.compile(r"(docs|profiles|packs|commands|agents|skills)/[A-Za-z]")


def test_distributed_files_have_no_unresolvable_references() -> None:
    """導入先へコピーされるファイルが、plugin 内のパスを参照しないこと。

    profiles/*.yaml は .tasuki/profile.yaml へ、packs/*/providers.yaml は
    .tasuki/providers.yaml へ丸ごとコピーされる。導入先に docs/ も profiles/ も
    存在しないため、そこへの参照は読み手が辿れない
    (agents / skills / commands に対する同種の検査は別テストが持つ)。
    """
    offenders = []
    targets = [
        *sorted((ROOT / "profiles").glob("*.yaml")),
        *sorted((ROOT / "packs").rglob("providers.yaml")),
        *sorted((ROOT / "packs").rglob("normalizers/*.py")),  # これも .tasuki/ へコピーされる
    ]
    assert targets, "配布対象のファイルが見つからない"
    for path in targets:
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            if re.search(_PLUGIN_PATH, line):
                offenders.append(f"{path.relative_to(ROOT)}:{lineno}: {line.strip()[:60]}")
    assert not offenders, offenders


def test_final_trace_audit_findings_are_fixed() -> None:
    """最終状態の手順トレース監査の所見が反映されていること。

    いずれも新規セッションが文字どおり歩くと詰まる箇所である。
    """
    loop = (ROOT / "commands/loop.md").read_text()
    # ブートストラップ PR 未マージのとき、作業ツリーを見て通過させない
    assert "作業ツリーを見てはならない" in loop
    # mechanical でも command を持たない provider はローカル実行しない
    assert "その provider が `command` を持つもの" in loop
    # 予算欄の読み取りは門前払いの有無に依らず走らせる(有効上限の出どころ)
    assert "予算欄の読み取りは、上の空チェックを行うかどうかに関わらず必ず行う" in loop
    # 門前払いの差し戻しも verdict 同型(再入の基準時刻と委譲の入力になる)
    assert "`tasuki:gate-review` skill の verdict スキーマで残す" in loop
    # 人間起票の親に replan が付いた場合の代替入力
    assert "現在の子 issue 群の本文一覧を旧分割案の代わりに渡す" in loop
    init = (ROOT / "commands/loop-init.md").read_text()
    # plugin 側のファイルは plugin ルートからの絶対パスで読む(カレントは導入先)
    assert "${CLAUDE_PLUGIN_ROOT}/profiles/development.yaml" in init
    assert "カレントは導入先リポジトリであり" in init
    # 契約ファイルのコメントは導入先へコピーされるため、plugin の docs パスを指さない
    contract = (ROOT / "profiles/development.yaml").read_text()
    assert "docs/CONTRACTS.md" not in contract


def test_gate_inputs_and_label_cleanup_are_complete() -> None:
    """委譲の渡し物とラベルの後始末に穴が無いこと。

    受け手が使うと宣言しているものを渡し手が渡していない、付けたラベルを外す手順が
    ゲート無効時に走らない、といった穴は run を止めるか triage を汚す。
    """
    loop = (ROOT / "commands/loop.md").read_text()
    # 統合ゲートにも契約を渡す(gate-reviewer は契約ファイルを自力で読めない)
    assert "契約の `gates.integration.phase` が指すフェーズの `receives` 定義" in loop
    # 出荷前レビューは AC / SC を照合するので子 issue の欄が要る
    assert "各子 issue の受け入れ条件と成功基準の欄" in loop
    # 回収モードの worker に PID とログパスを渡す
    assert "worker が報告した PID とログパスと完了の判定条件" in loop
    # decomposer への差し戻しでも契約の抜粋を渡す
    assert "verdict + §1a(分割の入手)と同じ契約の抜粋" in loop  # §1b 固有(§1d にも同名の句がある)
    # ゲートを無効にした契約でもラベルを外す
    assert "`intake` の有効無効に関わらず" in loop
    assert "`start` の有効無効に関わらず" in loop
    # 成果ゲートの門前払いは outcome 無効でも通る経路を持つ
    assert "含まれない場合も **2f の門前払い(機械チェック)だけを行ってから**" in loop
    # 再判定のガード(同じ状態で opus を呼び直さない)
    assert "`gate:split-returned` が付いている場合は" in loop
    assert "`gate:integration-passed` が無ければ" in loop
    # run を壊した種類の修正(実走で詰まった経路)
    assert "gh repo view --json defaultBranchRef` で解決する" in loop  # default branch 名
    # 契約を run 中に再読み出ししない
    assert "§0.1(前提と状態復元)で default branch から読んだものを使う" in loop
    assert "ブートストラップ PR が未マージである" in loop  # loop-init の再実行を案内しない
    # ゲートを無効にした契約でも門前払いのラベルは片付く
    assert "`outcome` の有効無効に関わらず" in loop
    # 無効にしたゲートの LLM 判定は走らせない(2b と対称)
    assert "`outcome` が無ければ、ここから先の LLM 判定は行わない" in loop
    # replan は統合ゲートの通過も解除する
    assert "`gate:integration-passed` を外し" in loop
    # 漂流で戻すときは着手ゲートの通過を解除する
    assert "**`gate:start-passed` を外してから**着手ゲート相当の再照合" in loop


def test_subagent_nesting_claims_match_current_spec() -> None:
    """subagent のネストについて、現行仕様と逆の記述を持たないこと。

    「subagent は別の subagent を起動できない」を前提に orchestrator の置き場所を
    説明していたが、現行仕様では既定でメインセッションの3階層下まで起動でき、
    CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH は上限を下げる設定である
    (https://code.claude.com/docs/en/sub-agents)。
    Claude Code の仕様に依存する記述は、こう固定しないと古いまま生き残る。
    """
    wrong = (
        "subagent は別の subagent を起動できない",
        "subagent は子 subagent を起動できない",
        "SPAWN_DEPTH` の設定が必要",  # 設定しないとネストできない、という趣旨の別表現
        "SPAWN_DEPTH=2` を設定すると",
    )
    for base in ("docs", "commands", "agents", "skills"):
        for path in sorted((ROOT / base).rglob("*.md")):
            text = path.read_text()
            for phrase in wrong:
                # ROADMAP は訂正の記録としてこの語を引用するため、訂正の文脈だけ許す
                if phrase in text and "**訂正**" not in text:
                    raise AssertionError(f"{path.relative_to(ROOT)}: 現行仕様と逆の記述: {phrase}")
    design = (ROOT / "docs/DESIGN.md").read_text()
    assert "3階層下まで" in design
    assert "上限を下げる設定" in design


def test_contract_consolidation_review_fixes() -> None:
    """契約一本化の変更に対する5観点レビュー所見の修正が残っていること。"""
    loop = (ROOT / "commands/loop.md").read_text()
    # 差し戻し委譲の入力(前提入力を毎回渡す。既存 PR の継続は maker 側の確認に依る)
    assert "差し戻しの委譲でも毎回渡す" in loop
    assert "既存 PR」を確認して行う" in loop
    # decomposer への契約抜粋(split_criteria 等)は全モードの委譲で毎回渡す
    assert "のたびに毎回渡す" in loop
    assert "`split_criteria`" in loop
    assert "split_criteria" in (ROOT / "agents/decomposer.md").read_text()
    # 統合の子の照合には親 issue 本文を渡す
    assert "親 issue 本文も渡す" in loop
    # outcome-returned 再入はレポートの編集更新も検知する
    assert "verdict より新しい編集" in loop
    # 門前払いは完全一致で、フェンス内の見出しを数えない
    assert "コードブロック(フェンス)内の見出しは数えない" in loop
    # 初期化コマンドは既存の調整を黙って捨てない
    init = (ROOT / "commands/loop-init.md").read_text()
    assert "上書きの前に次の4つを行う" in init


def test_report_fields_carry_meaning_comments() -> None:
    """report_required_fields の各欄行に欄コメントが付いていること。

    欄の意味は skill の本文から契約の欄コメントへ移した。コメントは yaml.safe_load に
    見えないため、raw テキストで固定しないと全部消しても緑のまま意味の実体が失われる。
    """
    import yaml

    text = (ROOT / "profiles/development.yaml").read_text()
    fields = yaml.safe_load(text)["templates"]["report_required_fields"]
    for field in fields:
        lines = [ln for ln in text.splitlines() if ln.strip().startswith(f"- {field}")]
        assert lines, field
        assert any("#" in ln for ln in lines), (field, "欄コメントが無い")


def test_mechanical_preflight_survives_gate_removal() -> None:
    """LLM 判定を外した契約でも、必須欄の空チェックは走ること。"""
    loop = (ROOT / "commands/loop.md").read_text()
    assert "`enabled_gates` に `start` が無くても走らせる" in loop
    assert "`preflight: template-fields` を持つ契約で走る" in loop  # 有無は契約から引く
    assert "人間が起票した子" in loop  # 分割ゲートを通っていない子は LLM 判定へ


def test_name_resolution_order_agrees_across_documents() -> None:
    """名前解決の順序を書く2箇所(skill と INTEGRATION)が一致すること。

    skill は agent が実行時に読み、INTEGRATION は設計の正である。
    導入先から docs/ を辿れないため skill 側に写しを置いているので、
    ズレないことを機械で固定する(規約「同じ事実を2つの文書に書かない」の例外扱い)。
    """
    order = "project"
    for path, text in (
        ("skills/baton-contract/SKILL.md", (ROOT / "skills/baton-contract/SKILL.md").read_text()),
        ("docs/INTEGRATION.md", (ROOT / "docs/INTEGRATION.md").read_text()),
    ):
        line = next(ln for ln in text.splitlines() if ln.startswith("名前解決は"))
        assert order in line, path
        assert (
            line.index("repo override")
            < line.index("language pack")
            < line.index("plugin デフォルト")
        ), path
    # project 層の実体が INTEGRATION に定義されていること(「project とは何か」が読める)
    integration = (ROOT / "docs/INTEGRATION.md").read_text()
    assert "ここでの project は導入先リポジトリ自身の Claude Code 定義" in integration


def test_gh_version_thresholds_are_single_and_correct() -> None:
    """gh の必要バージョンを 2.94.0 に統一すること(2.95.0 は誤りだった)。

    sub-issues の作成も `--json subIssues` での読み取りも cli/cli v2.94.0 で入っている。
    2.95.0 と書いていた間、gh 2.94.x の利用者は不要な GraphQL フォールバックへ分岐し、
    /tasuki:loop-status はフォールバックが無いため進行状況の節ごと落ちていた。
    """
    targets = [
        ROOT / "README.md",
        ROOT / "docs/OPERATIONS.md",
        ROOT / "commands/loop.md",
        ROOT / "commands/loop-init.md",
        ROOT / "commands/loop-status.md",
    ]
    for path in targets:
        assert "2.95.0" not in path.read_text(), path.name
    # 訂正の経緯と出典が ROADMAP に残っていること(仕様断定の登録規則)
    roadmap = (ROOT / "docs/ROADMAP.md").read_text()
    assert "https://github.com/cli/cli/releases/tag/v2.94.0" in roadmap


def test_checks_gates_have_no_labels() -> None:
    """形式ゲートはラベルを持たないこと(合否は CI の check-run が正)。

    README が識別子 `checks` を載せ「ラベルは識別子から作られる」と書いていたため、
    存在しない `gate:checks-passed` を読者が探すことになっていた。
    """
    readme = (ROOT / "README.md").read_text()
    assert "| `checks-*` |" in readme
    assert "形式ゲート(`checks-*`)はラベルを持たない" in readme
    # 実際にどこにも gate:checks* を作らない / 使わないこと
    for base in ("commands", "agents", "skills", "docs", "profiles"):
        for path in (ROOT / base).rglob("*"):
            if path.is_file() and path.suffix in (".md", ".yaml"):
                assert "gate:checks" not in path.read_text(), path.name


def test_marketplace_manifest_ships_with_the_repo() -> None:
    """常用導入の手順が、読者に自作を求めないこと。

    README が `.claude-plugin/marketplace.json` を「用意する」と書いていたが
    リポジトリに無く、クローンした読者は marketplace 登録に進めなかった。
    """
    import json

    manifest = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
    assert manifest["name"] == "tasuki"
    assert manifest["description"]
    assert [p["name"] for p in manifest["plugins"]] == ["tasuki"]
    readme = (ROOT / "README.md").read_text()
    assert "claude plugin marketplace add" in readme


def test_ci_validates_both_manifests_strictly() -> None:
    """自分の CI が、生成物に課しているのと同じ規律を自分にも課すこと。

    警告を素通りさせない(--strict)、供給網を固定する(バージョン固定)、
    走行時間と重複実行を縛る(timeout / concurrency)。
    """
    wf = (ROOT / ".github/workflows/validate.yml").read_text()
    assert "--strict" in wf
    assert ".claude-plugin/plugin.json" in wf and ".claude-plugin/marketplace.json" in wf
    assert re.search(r"@anthropic-ai/claude-code@\d+\.\d+\.\d+", wf), "バージョン未固定"
    assert "timeout-minutes:" in wf
    assert "cancel-in-progress: true" in wf


def test_external_issue_opt_in_is_described_consistently() -> None:
    """外部起票の扱いを「使わない」で終わらせず、opt-in の実装と一致させること。

    data-boundary skill と loop.md 冒頭が「外部 issue を受け付ける repo では使わない」と
    断じる一方、loop.md の起票者チェックは `tasuki:accepted` の opt-in を実装していた。
    共通規範が最も強い禁止を述べると、読み手は実装済みの経路を禁止機能と解する。
    """
    boundary = (ROOT / "skills/data-boundary/SKILL.md").read_text()
    loop = (ROOT / "commands/loop.md").read_text()
    for text, name in ((boundary, "data-boundary"), (loop, "loop.md")):
        assert "tasuki:accepted" in text, name
        assert "外部からの issue を受け付けるリポジトリでは tasuki を使わない" not in text, name
    # 境界の残る範囲(コメントは opt-in で守れない)を明示していること
    assert "コメント" in boundary
    assert "コメントまで信頼できないリポジトリでは使わない" in loop


def test_verifier_declares_every_input_its_steps_need() -> None:
    """verifier の入力宣言が、自分の手順が要求する入力を漏らさないこと。

    「入力は実行結果と成功基準・打ち切り条件のみ」と宣言しながら、手順1は PR の
    ブランチ名を、手順3は子 issue 要件を、統合の子では親 issue 本文を要求していた。
    宣言だけを読んで動く新規セッションは手順を実行できない。
    """
    verifier = (ROOT / "agents/verifier.md").read_text()
    for token in ("対象 PR のブランチ名", "受け入れ条件", "親 issue 本文"):
        assert token in verifier, token
    # 判定基準の版を固定する(worker のブランチ側の写しを読まない)
    assert "default branch の版を読む" in verifier
    # 呼び出し側(loop.md)が同じものを渡すこと
    loop = (ROOT / "commands/loop.md").read_text()
    assert "子 issue の要件(目的、受け入れ条件、成功基準、打ち切り条件)" in loop


def test_low_confidence_escalation_matches_the_gate_models() -> None:
    """low の行き先を「上位モデルで再判定」だけにしないこと。

    受理 / 分割 / 統合は標準が opus であり昇格先が無い。手順書は orchestrator が
    裁定すると定めているのに、判定者本人が読む定義は再判定だけを書いていた。
    """
    for path in ("skills/baton-contract/SKILL.md", "agents/gate-reviewer.md"):
        text = (ROOT / path).read_text()
        assert "orchestrator" in text, path
        assert "最上位" in text, path
