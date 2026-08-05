"""ゲート判定の LLM 回帰テスト(fixture runner)。

tests/fixtures/gate/ の判定例を、実際の契約(profiles/tasuki.yaml)と
突き合わせて haiku に判定させ、期待 verdict と一致するかを検める。
静的検査では守れない「判定の目盛り」の回帰を検出する。

LLM を呼ぶため、既定ではスキップする。実行は明示オプトイン:

    RUN_LLM_TESTS=1 uv run pytest -q tests/test_llm_gates.py

1件あたりの目安は haiku で数円・10秒程度。CI では回さない(認証と課金が
人間の判断に属するため)。回帰の確認は PR 前の関門(CLAUDE.md)の一部として
ローカルで行う。
"""

from __future__ import annotations

import json
import os
import re
import subprocess

import pytest
import yaml
from conftest import ROOT

FIXTURE_DIR = ROOT / "tests" / "fixtures" / "gate"
MODEL = "haiku"
TIMEOUT_SECONDS = 120

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LLM_TESTS") != "1",
    reason="LLM を呼ぶため既定でスキップ(RUN_LLM_TESTS=1 で実行)",
)


def _load_contract() -> dict:
    return yaml.safe_load((ROOT / "profiles" / "tasuki.yaml").read_text())


def _receives_for(gate_id: str) -> dict:
    """ゲートが検める受け渡し先の receives 定義を、実契約から引く。

    プロンプトに写しを埋め込まず契約から組み立てることで、契約を変えたのに
    テストが旧基準で判定し続ける、というズレを防ぐ(単一ソース)。
    """
    contract = _load_contract()
    gates = {g["id"]: g for g in contract["gates"]}
    phases = {p["name"]: p for p in contract["phases"]}
    phase = gates[gate_id]["phase"]
    return phases[phase]["receives"]


def _build_prompt(gate_id: str, body: str, requirements: str | None = None) -> str:
    receives = _receives_for(gate_id)
    # 照合先を要する判定(分割 / 成果 / 統合)は requirements 無しでは孤児判定ができない
    # (規則は skills/baton-contract/SKILL.md)。fixture が持つなら必ず渡す。
    against = f"照合先(要件):\n{requirements}\n\n" if requirements else ""
    return (
        "あなたは抽象度ゲートの判定者である。契約と入力を照合し、"
        "verdict JSON のみを出力せよ(説明文は不要)。\n\n"
        f"契約(受け入れ側):\n"
        f"- waiting_level: {receives['waiting_level']}\n"
        f"- too_abstract_signals: {receives['too_abstract_signals']}\n"
        f"- too_concrete_signals: {receives['too_concrete_signals']}\n\n"
        f"{against}"
        f"入力:\n{body}\n\n"
        '出力スキーマ: {"gate": "' + gate_id + '", "verdict": "PASS|TOO_ABSTRACT|TOO_CONCRETE", '
        '"confidence": "high|low", "reasons": ["..."]}'
    )


def _judge(prompt: str) -> dict:
    proc = subprocess.run(
        ["claude", "-p", "--model", MODEL, "--output-format", "json"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS,
    )
    assert proc.returncode == 0, proc.stderr[:500]
    data = json.loads(proc.stdout)
    messages = data if isinstance(data, list) else [data]
    result = next((m for m in messages if m.get("type") == "result"), messages[-1])
    match = re.search(r"\{.*\}", result.get("result", ""), re.S)
    assert match, f"verdict JSON が出力に無い: {result.get('result', '')[:300]}"
    return json.loads(match.group(0))


def _fixtures() -> list:
    return sorted(FIXTURE_DIR.glob("*.yaml"))


@pytest.mark.parametrize("path", _fixtures(), ids=lambda p: p.stem)
def test_gate_fixture(path) -> None:
    fixture = yaml.safe_load(path.read_text())
    verdict = _judge(_build_prompt(fixture["gate"], fixture["input"], fixture.get("requirements")))
    assert verdict["verdict"] == fixture["expected_verdict"], (
        f"{path.stem}: expected {fixture['expected_verdict']} "
        f"got {verdict['verdict']} (reasons={verdict.get('reasons')})"
    )
