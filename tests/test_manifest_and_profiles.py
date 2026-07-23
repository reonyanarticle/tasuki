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

    def test_phase2_gates_enabled(self, profile_name: str, request: pytest.FixtureRequest) -> None:
        """フェーズ2: g2 と g3 が有効であること(ROADMAP の段階導入)。"""
        profile = request.getfixturevalue(profile_name)
        assert {"g2", "g3"} <= set(profile["enabled_gates"])

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
