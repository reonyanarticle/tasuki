"""plugin.json と契約プロファイルの整合性。"""

from __future__ import annotations

import json

import pytest
from conftest import ROOT


def test_plugin_manifest() -> None:
    manifest = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
    assert manifest["name"] == "tasuki"
    assert manifest["description"]


@pytest.mark.parametrize("profile_name", ["dev_profile"])
class TestProfiles:
    def test_mechanical_providers_exist(
        self, profile_name: str, request: pytest.FixtureRequest
    ) -> None:
        """mechanical ゲートの provider は、そのプロファイルが使う pack に定義されていること。"""
        profile = request.getfixturevalue(profile_name)
        pack_providers = request.getfixturevalue("providers")["providers"]
        for gate in profile["gates"]:
            if gate["kind"] == "mechanical":
                assert gate["provider"] in pack_providers, gate["id"]

    def test_enabled_gates_subset(self, profile_name: str, request: pytest.FixtureRequest) -> None:
        """enabled_gates は定義済みゲート ID の部分集合であること。"""
        profile = request.getfixturevalue(profile_name)
        gate_ids = {gate["id"] for gate in profile["gates"]}
        assert set(profile["enabled_gates"]) <= gate_ids

    def test_phase3_review_fixes(self, profile_name: str, request: pytest.FixtureRequest) -> None:
        """フェーズ3レビュー修正: integration フェーズ、g1 set_signals、分割・前提シグナル。"""
        profile = request.getfixturevalue(profile_name)
        names = [ph["name"] for ph in profile["phases"]]
        assert names[-1] == "integration"
        integration = profile["phases"][-1]
        assert any("孤児" in s for s in integration["receives"]["too_abstract_signals"])
        g1 = next(g for g in profile["gates"] if g["id"] == "split")
        assert any("循環" in s for s in g1["set_signals"])
        assert any("親予算" in s for s in g1["set_signals"])
        second = profile["phases"][1]["receives"]["too_abstract_signals"]
        assert any("実現可能性" in s for s in second)

    def test_phase3_gates_enabled(self, profile_name: str, request: pytest.FixtureRequest) -> None:
        """フェーズ3: 全 abstraction ゲートが有効であること(ROADMAP の段階導入)。"""
        profile = request.getfixturevalue(profile_name)
        enabled = set(profile["enabled_gates"])
        assert {"intake", "split", "start", "outcome", "integration"} <= enabled

    def test_g3_wiring(self, profile_name: str, request: pytest.FixtureRequest) -> None:
        """成果ゲートは門前払いを持ち、report signals が判定基準を契約由来にする。"""
        profile = request.getfixturevalue(profile_name)
        g3 = next(g for g in profile["gates"] if g["id"] == "outcome")
        assert g3["preflight"] == "report-fields"
        report = next(p for p in profile["phases"] if p["name"] == "report")
        signals = report["receives"]["too_abstract_signals"]
        concrete = report["receives"]["too_concrete_signals"]
        assert "再現手順の欠落" in signals
        assert any("期待値の根拠" in s for s in signals)
        assert any("secrets" in s for s in concrete)
        assert "期待値の根拠" in profile["templates"]["report_required_fields"]

    def test_security_is_opt_in(self, profile_name: str, request: pytest.FixtureRequest) -> None:
        """checks-security は定義されつつ、既定の enabled_gates には入らないこと。"""
        profile = request.getfixturevalue(profile_name)
        gate_ids = {gate["id"] for gate in profile["gates"]}
        assert "checks-security" in gate_ids
        assert "checks-security" not in profile["enabled_gates"]

    def test_no_dead_models_block(self, profile_name: str, request: pytest.FixtureRequest) -> None:
        """どこからも読まれない models ブロックを持たないこと。"""
        profile = request.getfixturevalue(profile_name)
        assert "models" not in profile

    def test_criteria_skills_defined(
        self, profile_name: str, request: pytest.FixtureRequest
    ) -> None:
        """g2 / g3 に criteria_skills キーがあること(橋渡しの接続点)。"""
        profile = request.getfixturevalue(profile_name)
        for gate_id in ("start", "outcome"):
            gate = next(g for g in profile["gates"] if g["id"] == gate_id)
            assert "criteria_skills" in gate, gate_id

    def test_phase_handoff_chain(self, profile_name: str, request: pytest.FixtureRequest) -> None:
        """phases の hands_off.to / receives.from が実在フェーズを指し、連鎖すること。"""
        profile = request.getfixturevalue(profile_name)
        phases = profile["phases"]
        names = [p["name"] for p in phases]
        for i, phase in enumerate(phases):
            if "hands_off" in phase:
                assert phase["hands_off"]["to"] in names, phase["name"]
            if "receives" in phase:
                assert phase["receives"]["from"] == names[i - 1], phase["name"]

    def test_templates_required_fields(
        self, profile_name: str, request: pytest.FixtureRequest
    ) -> None:
        """門前払いの対象となる必須欄リストが空でないこと。"""
        profile = request.getfixturevalue(profile_name)
        templates = profile["templates"]
        for key in (
            "parent_issue_required_fields",
            "child_issue_required_fields",
            "report_required_fields",
            "pr_required_fields",
        ):
            assert templates[key], key

    def test_split_criteria_defined(
        self, profile_name: str, request: pytest.FixtureRequest
    ) -> None:
        """分割基準が契約由来であること(decomposer と分割ゲートはここから引く)。

        3つ目のプロファイルを試作したとき、「良いタスクの4条件」が agent 定義に literal に
        書かれていたため読み替え節を足す羽目になった。基準の置き場所を契約に固定する。
        """
        profile = request.getfixturevalue(profile_name)
        criteria = profile["split_criteria"]
        assert criteria["good_task_conditions"], profile_name
        assert criteria["always_separate"], profile_name


def test_single_profile_carries_evaluation_discipline(dev_profile: dict) -> None:
    """実験の規律が、専用プロファイルではなく development の契約に載っていること。

    experiment プロファイルを廃止したとき、規律(評価データの分離、統制条件、数字の由来セット)を
    条件付きシグナルとして development へ畳んだ。これが消えると、実験を回したときに
    データ漏洩と再現不能を止める装置がどこにも無くなる。
    """
    assert not (ROOT / "profiles/experiment.yaml").exists()  # 器は1つに戻した
    phases = {p["name"]: p for p in dev_profile["phases"]}
    impl = phases["implementation"]["receives"]["too_abstract_signals"]
    assert any("評価データの分離" in s and "統制条件" in s for s in impl), impl
    report = phases["report"]["receives"]["too_abstract_signals"]
    assert any("由来セット" in s for s in report), report
    # 欄コメント側にも再現の統制条件が残っていること(raw テキストで見る)
    raw = (ROOT / "profiles/development.yaml").read_text()
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
        "hands_off": "`receives` 定義",
        "from": "`receives` 定義",
        "name": "`gates[].phase`",
        "phase": "`gates[].phase`",
        "id": "`enabled_gates`",
        "kind": "`kind: mechanical`",
        "provider": "provider",
        "preflight": "`preflight: template-fields`",
        "with": "`ci.setup`",
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
    for name in ("development",):
        budgets = yaml.safe_load((ROOT / f"profiles/{name}.yaml").read_text())["budgets"]
        missing = sorted(referenced - set(budgets))
        assert not missing, (name, missing)


def test_gate_phase_resolves_in_every_profile() -> None:
    """abstraction ゲートの phase が、どのプロファイルでも実在するフェーズを指すこと。

    loop.md がフェーズ名をハードコードしていた頃、フェーズ名を言い換えた契約では
    受理と分割と着手のゲートが参照先を解決できなかった。同じ壊れ方を防ぐ。
    """
    import yaml

    for name in ("development",):
        profile = yaml.safe_load((ROOT / f"profiles/{name}.yaml").read_text())
        phases = {p["name"] for p in profile["phases"]}
        for gate in profile["gates"]:
            if gate.get("kind") != "abstraction":
                continue
            assert "phase" in gate, (name, gate["id"])
            assert gate["phase"] in phases, (name, gate["id"], gate["phase"], sorted(phases))


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

    for name in ("development",):
        fields = yaml.safe_load((ROOT / f"profiles/{name}.yaml").read_text())["templates"][
            "pr_required_fields"
        ]
        assert "対応する親要件" in fields, name
        assert "受け入れ条件の充足" in fields, name
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
