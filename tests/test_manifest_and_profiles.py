"""plugin.json と契約プロファイルの整合性。"""

from __future__ import annotations

import json

from conftest import ROOT


def test_plugin_manifest() -> None:
    manifest = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
    assert manifest["name"] == "tasuki"
    assert manifest["description"]


class TestProfiles:
    """唯一の契約(profiles/tasuki.yaml)の整合性。

    かつては複数プロファイルを parametrize で回していたが、器を1つに戻したので
    fixture を直接引く(プロファイルが再び増えたら parametrize を戻す)。
    """

    def test_mechanical_providers_exist(self, dev_profile: dict, providers: dict) -> None:
        """mechanical ゲートの provider は、そのプロファイルが使う pack に定義されていること。"""
        pack_providers = providers["providers"]
        for gate in dev_profile["gates"]:
            if gate["kind"] == "mechanical":
                assert gate["provider"] in pack_providers, gate["id"]

    def test_enabled_gates_subset(self, dev_profile: dict) -> None:
        """enabled_gates は定義済みゲート ID の部分集合であること。"""
        gate_ids = {gate["id"] for gate in dev_profile["gates"]}
        assert set(dev_profile["enabled_gates"]) <= gate_ids

    def test_phase3_review_fixes(self, dev_profile: dict) -> None:
        """フェーズ3レビュー修正: integration フェーズ、g1 set_signals、分割・前提シグナル。"""
        names = [ph["name"] for ph in dev_profile["phases"]]
        assert names[-1] == "integration"
        integration = dev_profile["phases"][-1]
        assert any("孤児" in s for s in integration["receives"]["too_abstract_signals"])
        g1 = next(g for g in dev_profile["gates"] if g["id"] == "split")
        assert any("循環" in s for s in g1["set_signals"])
        assert any("親予算" in s for s in g1["set_signals"])
        decomp = next(p for p in dev_profile["phases"] if p["name"] == "decomposition")
        assert any("実現可能性" in s for s in decomp["receives"]["too_abstract_signals"])

    def test_phase3_gates_enabled(self, dev_profile: dict) -> None:
        """フェーズ3: 全 abstraction ゲートが有効であること(ROADMAP の段階導入)。"""
        enabled = set(dev_profile["enabled_gates"])
        assert {"intake", "split", "start", "outcome", "integration"} <= enabled

    def test_g3_wiring(self, dev_profile: dict) -> None:
        """成果ゲートは門前払いを持ち、report signals が判定基準を契約由来にする。"""
        g3 = next(g for g in dev_profile["gates"] if g["id"] == "outcome")
        assert g3["preflight"] == "report-fields"
        report = next(p for p in dev_profile["phases"] if p["name"] == "report")
        signals = report["receives"]["too_abstract_signals"]
        concrete = report["receives"]["too_concrete_signals"]
        assert "再現手順の欠落" in signals
        assert any("期待値の根拠" in s for s in signals)
        assert any("secrets" in s for s in concrete)
        assert "期待値の根拠" in dev_profile["templates"]["report_required_fields"]

    def test_security_is_opt_in(self, dev_profile: dict) -> None:
        """checks-security は定義されつつ、既定の enabled_gates には入らないこと。"""
        gate_ids = {gate["id"] for gate in dev_profile["gates"]}
        assert "checks-security" in gate_ids
        assert "checks-security" not in dev_profile["enabled_gates"]

    def test_no_dead_models_block(self, dev_profile: dict) -> None:
        """どこからも読まれない models ブロックを持たないこと。"""
        assert "models" not in dev_profile

    def test_criteria_skills_defined(self, dev_profile: dict) -> None:
        """g2 / g3 に criteria_skills キーがあること(橋渡しの接続点)。"""
        for gate_id in ("start", "outcome"):
            gate = next(g for g in dev_profile["gates"] if g["id"] == gate_id)
            assert "criteria_skills" in gate, gate_id

    def test_phases_are_all_referenced_by_gates(self, dev_profile: dict) -> None:
        """phases は gates[].phase が指すものだけを持つこと(読まれない待ち位置を残さない)。

        かつて requirements フェーズはどのゲートからも指されず、hands_off と
        receives.from も手順書に読み手が無かった(experiment を廃止した根拠と同じ形)。
        """
        names = [p["name"] for p in dev_profile["phases"]]
        assert len(names) == len(set(names)), names
        targeted = {g["phase"] for g in dev_profile["gates"] if "phase" in g}
        assert set(names) == targeted, (sorted(names), sorted(targeted))
        for phase in dev_profile["phases"]:
            assert set(phase) == {"name", "receives"}, phase["name"]
            assert set(phase["receives"]) == {
                "waiting_level",
                "too_abstract_signals",
                "too_concrete_signals",
            }, phase["name"]

    def test_templates_required_fields(self, dev_profile: dict) -> None:
        """門前払いの対象となる必須欄リストが空でないこと。"""
        templates = dev_profile["templates"]
        for key in (
            "parent_issue_required_fields",
            "child_issue_required_fields",
            "report_required_fields",
            "pr_required_fields",
        ):
            assert templates[key], key

    def test_split_criteria_defined(self, dev_profile: dict) -> None:
        """分割基準が契約由来であること(decomposer と分割ゲートはここから引く)。

        3つ目のプロファイルを試作したとき、「良いタスクの4条件」が agent 定義に literal に
        書かれていたため読み替え節を足す羽目になった。基準の置き場所を契約に固定する。
        """
        criteria = dev_profile["split_criteria"]
        assert criteria["good_task_conditions"]
        assert criteria["always_separate"]


def test_single_profile_carries_evaluation_discipline(dev_profile: dict) -> None:
    """実験の規律が、専用プロファイルではなく唯一の契約に載っていること。

    experiment プロファイルを廃止したとき、規律(評価データの分離、統制条件、数字の由来セット)を
    条件付きシグナルとして唯一の契約へ畳んだ。これが消えると、実験を回したときに
    データ漏洩と再現不能を止める装置がどこにも無くなる。
    """
    assert not (ROOT / "profiles/experiment.yaml").exists()  # 器は1つに戻した
    phases = {p["name"]: p for p in dev_profile["phases"]}
    impl = phases["implementation"]["receives"]["too_abstract_signals"]
    assert any("評価データの分離" in s and "統制条件" in s for s in impl), impl
    report = phases["report"]["receives"]["too_abstract_signals"]
    assert any("由来セット" in s for s in report), report
    # 欄コメント側にも再現の統制条件が残っていること(raw テキストで見る)
    raw = (ROOT / "profiles/tasuki.yaml").read_text()
    assert "seed" in raw and "データ版数" in raw
    # 測定と測定対象を同じ子に入れない
    separate = dev_profile["split_criteria"]["always_separate"]
    assert any("測定と測定対象の変更" in s for s in separate), separate
    # maker 側の適用条件も、契約の欄名ではなく仕事の性質で書かれていること
    worker = (ROOT / "agents/worker.md").read_text()
    assert "## 評価や測定を伴うタスクの規律" in worker
    assert "契約の子 issue 欄に" not in worker  # 存在しない欄を条件にしない
    # 契約に写した CONTRACTS のサンプルが、新しいシグナルまで一致していること
    sample = (ROOT / "docs/CONTRACTS.md").read_text()
    assert "評価データの分離(dev/test)と統制条件" in sample
    assert "由来セット(dev/test)が不明" in sample


def test_contract_has_no_unread_keys(dev_profile: dict) -> None:
    """契約は「今読まれるキー」だけを持つこと(dead config を作らない)。

    experiment 廃止で exit_criteria_fields が死んだのを外したのと同じ理由で、
    手順書・agent・skill のどこからも読まれないキーを契約に残さない。
    v2 の予約は ROADMAP に書けば足りる。
    """
    readers = "\n".join(
        p.read_text()
        for base in ("commands", "agents", "skills")
        for p in (ROOT / base).rglob("*.md")
    )

    def keys_of(node: object) -> set[str]:
        """契約のキーを入れ子も含めて集める(死んだキーが下層に隠れないように)。"""
        found: set[str] = set()
        if isinstance(node, dict):
            for k, v in node.items():  # pyright: ignore[reportUnknownVariableType]
                found.add(str(k))
                found |= keys_of(v)
        elif isinstance(node, list):
            for item in node:  # pyright: ignore[reportUnknownVariableType]
                found |= keys_of(item)
        return found

    # 手順書が別名で引くキーは、その別名を読まれた証拠とする
    aliases: dict[str, str] = {
        "phases": "`receives` 定義",
        "budgets": "max_iterations_per_gate",
        "receives": "`receives` 定義",
        "name": "`gates[].phase`",
        "phase": "`gates[].phase`",
        "id": "`enabled_gates`",
        "kind": "`kind: mechanical`",
        "provider": "その provider が `command` を持つもの",
        "preflight": "`preflight: template-fields`",
    }
    # 欄名そのもの(日本語)はキーではなく値なので対象外
    for key in sorted(k for k in keys_of(dev_profile) if k.isascii()):
        alias = aliases.get(key)
        # 別名を持たないキーは、コード表記(`key` か key:)で引かれていることを求める。
        # 素の部分文字列一致にすると、無関係な語に含まれて素通りする(profile が
        # .tasuki/profile.yaml に含まれる等)。
        hit = alias in readers if alias else (f"`{key}`" in readers or f"{key}:" in readers)
        assert hit, f"どの手順書からも読まれない契約キー: {key}"


def test_repo_override_may_add_required_fields() -> None:
    """必須欄の追加を repo override の許容範囲として明示していること。

    仕事の型ごとに plugin 側の雛形を増やさない代わりに、導入先が自分の契約へ
    欄を足せることが逃げ道になる。これが書かれていないと、型ごとの雛形が復活する。
    """
    contracts = (ROOT / "docs/CONTRACTS.md").read_text()
    assert "必須欄(`templates`)の追加" in contracts
    assert "欄の削除は行わない" in contracts
    # 走行中に欄が増えると既存の子が一斉に差し戻される(反映のタイミングを定める)
    assert "走行中(open)の親 issue が無いときに反映する" in contracts
    init = (ROOT / "commands/loop-init.md").read_text()
    assert "必須欄(`templates`)の追加" in init
    # 追加したい欄を棚卸しで採取する手順があること
    assert "毎回テンプレが問いかけたい欄があるかをユーザーに確認する" in init
    loop = (ROOT / "commands/loop.md").read_text()
    # 導入先が足した欄の意味が着手ゲートに届くこと
    assert "`child_issue_required_fields`(欄コメントを含む" in loop
    assert "`child_issue_required_fields`" in (ROOT / "skills/gate-review/SKILL.md").read_text()


def test_providers_normalizer_exists(providers: dict) -> None:
    """typecheck の normalizer が実在すること。"""
    normalizer = providers["providers"]["typecheck"]["normalizer"]
    assert (ROOT / "packs/python" / normalizer).is_file()


def test_providers_detect(providers: dict) -> None:
    assert providers["detect"] == ["pyproject.toml"]


def test_loop_contract_keys_exist_in_profiles() -> None:
    """loop.md が参照する契約キーが profiles に実在すること(dead config を作らない)。"""
    import re

    import yaml

    loop = (ROOT / "commands/loop.md").read_text()
    referenced = set(
        re.findall(
            r"`(max_iterations_per_gate|max_inner_loop|wip_limit_prs|stale_assignment_minutes)`",
            loop,
        )
    )
    assert referenced, "契約キーの参照が見つからない"
    budgets = yaml.safe_load((ROOT / "profiles/tasuki.yaml").read_text())["budgets"]
    missing = sorted(referenced - set(budgets))
    assert not missing, missing


def test_gate_phase_resolves_in_every_profile() -> None:
    """abstraction ゲートの phase が、どのプロファイルでも実在するフェーズを指すこと。

    loop.md がフェーズ名をハードコードしていた頃、フェーズ名を言い換えた契約では
    受理と分割と着手のゲートが参照先を解決できなかった。同じ壊れ方を防ぐ。
    """
    import yaml

    profile = yaml.safe_load((ROOT / "profiles/tasuki.yaml").read_text())
    phases = {p["name"] for p in profile["phases"]}
    for gate in profile["gates"]:
        if gate.get("kind") != "abstraction":
            continue
        assert "phase" in gate, gate["id"]
        assert gate["phase"] in phases, (gate["id"], gate["phase"], sorted(phases))


def test_loop_does_not_hardcode_phase_names() -> None:
    """loop.md がプロファイル固有のフェーズ名を直接書かないこと。"""
    import re

    loop = (ROOT / "commands/loop.md").read_text()
    hardcoded = re.findall(r"(?:decomposition|implementation|execution|analysis) フェーズ", loop)
    assert not hardcoded, hardcoded
    assert loop.count("phase`") >= 5  # 5つの abstraction ゲートすべてが契約から引く


def test_pr_template_carries_traceability() -> None:
    """PR 単体で「何のための変更か」が判断できる必須欄を持つこと。

    Closes #N だけでは、レビューする人が受け入れ条件も親要件も見られず、
    issue を開き直さないと判断できない。レビューが起きる場所は PR である。
    """
    import yaml

    fields = yaml.safe_load((ROOT / "profiles/tasuki.yaml").read_text())["templates"][
        "pr_required_fields"
    ]
    assert "対応する親要件" in fields
    assert "受け入れ条件の充足" in fields
    worker = (ROOT / "agents/worker.md").read_text()
    assert "PR 単体で判断できるようにする" in worker


def test_pack_declares_artifacts_and_hygiene_is_wired() -> None:
    """pack が生成物パターンを持ち、loop-init と worker がそれを使うこと。

    E2E で __pycache__ の .pyc がコミットされ、ブランチ間で生成物どうしが
    2連続で競合した。言語固有のパターンは pack に置く(三層構造)。
    """
    import yaml

    pack = yaml.safe_load((ROOT / "packs/python/providers.yaml").read_text())
    assert "__pycache__/" in pack["artifacts"]
    assert "*.pyc" in pack["artifacts"]
    init = (ROOT / "commands/loop-init.md").read_text()
    assert "生成物が .gitignore で除外されているか検査する" in init
    worker = (ROOT / "agents/worker.md").read_text()
    assert "生成物" in worker and "コミットしない" in worker


def test_packs_protect_governance_files_from_tampering() -> None:
    """検査コマンドの単一ソース(.tasuki/providers.yaml)と契約が改変検知の対象であること。

    providers.yaml は検査の実行コマンドを持つ。書き換えられると
    検査対象を空ディレクトリへ向けて素通りさせられるため、検知の対象から外せない。
    """
    import yaml

    for pack in ("python",):
        cfg = yaml.safe_load((ROOT / f"packs/{pack}/providers.yaml").read_text())
        paths = cfg["ci"]["config_tampering"]["paths"]
        assert ".tasuki/providers.yaml" in paths, pack
        assert ".tasuki/profile.yaml" in paths, pack


def test_packs_have_no_empty_pathspec_keys() -> None:
    """pathspec に使うキーは空リストで持たない(空だと git が全ファイルを対象にする)。

    `git diff -- ` は pathspec が空だと全ファイルにマッチするため、
    空リストをテンプレートへ展開すると新規ファイルを追加した PR がすべて赤になる。
    """
    import yaml

    for pack in ("python",):
        ci = yaml.safe_load((ROOT / f"packs/{pack}/providers.yaml").read_text())["ci"]
        for key in ("new_config_files",):
            assert ci.get(key) != [], (pack, key)
        for key in ("config_tampering", "test_tampering"):
            if key in ci:
                assert ci[key].get("paths"), (pack, key)


def test_gate_fixtures_resolve_against_the_contract(dev_profile: dict) -> None:
    """LLM fixture が、実契約に対して静的に解決できること。

    tests/test_llm_gates.py は既定でスキップ(LLM を呼ぶため)であり、
    fixture と契約の対応が検められるのは LLM を実行したときだけだった。
    ゲート ID やフェーズ名を改名すると fixture が黙って腐るため、
    LLM を呼ばない静的検査をここに置く。
    """
    import yaml
    from test_llm_gates import _receives_for  # pyright: ignore[reportPrivateUsage]

    # 現在の fixture は start × 3 と outcome × 1 であり、split / integration は未整備
    # (それらの枝はまだ一度も実行されない)。
    verdicts = {"PASS", "TOO_ABSTRACT", "TOO_CONCRETE"}
    # 照合先(親要件や子要件)が無いと孤児判定ができないゲート
    needs_requirements = {"split", "outcome", "integration"}
    paths = sorted((ROOT / "tests/fixtures/gate").glob("*.yaml"))
    assert paths, "fixture が1件も無い"
    for path in paths:
        fixture = yaml.safe_load(path.read_text())
        gate = fixture["gate"]
        assert gate in dev_profile["enabled_gates"], (path.name, gate)
        assert fixture["expected_verdict"] in verdicts, path.name
        assert fixture["input"].strip(), path.name
        receives = _receives_for(gate)
        assert receives["waiting_level"], (path.name, gate)
        if gate in needs_requirements:
            assert fixture.get("requirements", "").strip(), (path.name, "照合先が無い")


def test_override_range_is_listed_in_one_place() -> None:
    """repo override の範囲は契約冒頭のコメントが正で、写しは1つに限ること。

    かつて同じ6項目が契約、loop-init、skill、CONTRACTS の4箇所にあり、
    1項目の増減で3箇所を追随させる必要があった(一致を固定するテストも無かった)。
    説明を置くのは CONTRACTS だけとし、その一致をここで固定する。
    """
    contract = (ROOT / "profiles/tasuki.yaml").read_text()
    header = contract.split("budgets:")[0]
    items = (
        "コマンド",
        "閾値",
        "待ち位置定義",
        "reviewer / criteria_skills の割り当て",
        "enabled_gates",
    )
    for item in items:
        assert item in header, item
    # 説明の写しは CONTRACTS の1節だけ(ファイル全体で探すと別文脈の同じ語に当たる)
    doc = (ROOT / "docs/CONTRACTS.md").read_text()
    section = doc.split("### repo override で変えてよい範囲")[1].split("\n### ")[0]
    for item in items:
        assert item in section, item
    # 手順書 / skill / DESIGN は列挙せず、正を指すだけであること。
    # 語の並びではなく共起で見る(読点や助詞を変えた写しを素通りさせない)。
    for rel in ("commands/loop-init.md", "skills/baton-contract/SKILL.md", "docs/DESIGN.md"):
        text = (ROOT / rel).read_text()
        assert "契約ファイル冒頭のコメント" in text or "profile.yaml` 冒頭のコメント" in text, rel
        for line in text.splitlines():
            assert not ("待ち位置定義" in line and "criteria_skills" in line), (rel, line)
