"""plugin.json と契約プロファイルの整合性。"""

from __future__ import annotations

import json

import pytest
from conftest import ROOT


def test_plugin_manifest() -> None:
    manifest = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
    assert manifest["name"] == "tasuki"
    assert manifest["description"]


@pytest.mark.parametrize("profile_name", ["dev_profile", "exp_profile"])
class TestProfiles:
    def test_mechanical_providers_exist(
        self, profile_name: str, providers: dict, request: pytest.FixtureRequest
    ) -> None:
        """mechanical ゲートの provider は pack に定義されていること。"""
        profile = request.getfixturevalue(profile_name)
        pack_providers = providers["providers"]
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
        g1 = next(g for g in profile["gates"] if g["id"] == "g1")
        assert any("循環" in s for s in g1["set_signals"])
        assert any("親予算" in s for s in g1["set_signals"])
        second = profile["phases"][1]["receives"]["too_abstract_signals"]
        assert any("実現可能性" in s for s in second)

    def test_phase3_gates_enabled(self, profile_name: str, request: pytest.FixtureRequest) -> None:
        """フェーズ3: 全 abstraction ゲートが有効であること(ROADMAP の段階導入)。"""
        profile = request.getfixturevalue(profile_name)
        assert {"g0", "g1", "g2", "g3", "g4"} <= set(profile["enabled_gates"])

    def test_g3_wiring(self, profile_name: str, request: pytest.FixtureRequest) -> None:
        """G3 は門前払い(report-fields)を持ち、report signals が判定基準を契約由来にする。"""
        profile = request.getfixturevalue(profile_name)
        g3 = next(g for g in profile["gates"] if g["id"] == "g3")
        assert g3["preflight"] == "report-fields"
        report = next(p for p in profile["phases"] if p["name"] == "report")
        signals = report["receives"]["too_abstract_signals"]
        assert "再現手順の欠落" in signals
        assert any("期待値の根拠" in s for s in signals)
        concrete = report["receives"]["too_concrete_signals"]
        assert any("secrets" in s for s in concrete)
        assert "期待値の根拠" in profile["templates"]["report_required_fields"]

    def test_security_is_opt_in(self, profile_name: str, request: pytest.FixtureRequest) -> None:
        """gm-security は定義されつつ、既定の enabled_gates には入らないこと。"""
        profile = request.getfixturevalue(profile_name)
        gate_ids = {gate["id"] for gate in profile["gates"]}
        assert "gm-security" in gate_ids
        assert "gm-security" not in profile["enabled_gates"]

    def test_no_dead_models_block(self, profile_name: str, request: pytest.FixtureRequest) -> None:
        """どこからも読まれない models ブロックを持たないこと。"""
        profile = request.getfixturevalue(profile_name)
        assert "models" not in profile

    def test_criteria_skills_defined(
        self, profile_name: str, request: pytest.FixtureRequest
    ) -> None:
        """g2 / g3 に criteria_skills キーがあること(橋渡しの接続点)。"""
        profile = request.getfixturevalue(profile_name)
        for gate_id in ("g2", "g3"):
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
    for name in ("development", "experiment"):
        budgets = yaml.safe_load((ROOT / f"profiles/{name}.yaml").read_text())["budgets"]
        missing = sorted(referenced - set(budgets))
        assert not missing, (name, missing)
