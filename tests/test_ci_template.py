"""loop-init.md に埋め込まれた CI テンプレートの不変条件。

E2E で「テンプレートの YAML 不正が workflow 全体を 0 job failure にする」事故が
実際に起きたため(ROADMAP の E2E 結果)、テンプレートは常にここで検証する。
"""

from __future__ import annotations

import re

import pytest
import yaml
from conftest import ROOT

# PR のコードを実行する job(write 権限を持ってはならない)
CODE_EXECUTING_JOBS = {"lint", "format", "typecheck", "test"}


@pytest.fixture(scope="module")
def template() -> dict:
    text = (ROOT / "commands/loop-init.md").read_text()
    match = re.search(r"```yaml\n(name: loop-gates.*?)```", text, re.S)
    assert match, "loop-init.md に loop-gates テンプレートがない"
    raw = re.sub(r"<providers\.[a-z_.]+>", "echo dummy", match.group(1))
    raw = raw.replace("<コミット SHA>", "0000000")
    return yaml.safe_load(raw)


def test_template_parses_and_has_all_jobs(template: dict) -> None:
    assert set(template["jobs"]) == CODE_EXECUTING_JOBS | {"security", "notify-success"}


def test_workflow_default_permissions_empty(template: dict) -> None:
    """workflow 既定は無権限で、job ごとに最小付与する。"""
    assert template["permissions"] == {}


def test_code_executing_jobs_have_no_write_permissions(template: dict) -> None:
    """PR コードを実行する job は pull-requests: write を持たない。"""
    for name in CODE_EXECUTING_JOBS:
        permissions = template["jobs"][name].get("permissions", {})
        assert permissions.get("pull-requests") != "write", name


def test_checkout_never_persists_credentials(template: dict) -> None:
    """GITHUB_TOKEN を .git/config に残さない(PR コードからの読み出し防止)。"""
    for name, job in template["jobs"].items():
        for step in job.get("steps", []):
            if str(step.get("uses", "")).startswith("actions/checkout"):
                assert step["with"]["persist-credentials"] is False, name


def test_no_paths_ignore(template: dict) -> None:
    """paths-ignore は check-run ゼロ件の fail-open を生むため使わない。"""
    on_config = template.get("on") or template.get(True)
    assert "paths-ignore" not in str(on_config)


def test_sarif_uploads_are_best_effort(template: dict) -> None:
    """SARIF アップロードは best-effort(private リポジトリの GHAS なし環境対応)。"""
    for name, job in template["jobs"].items():
        for step in job.get("steps", []):
            if "upload-sarif" in str(step.get("uses", "")):
                assert step.get("continue-on-error") is True, name


def test_typecheck_gate_is_fail_closed(template: dict) -> None:
    """typecheck の合否は jq -e ステップが決める(summary 欠落で失敗する)。"""
    steps = template["jobs"]["typecheck"]["steps"]
    gate_steps = [s for s in steps if s.get("name") == "typecheck gate"]
    assert gate_steps and "jq -er" in gate_steps[0]["run"]


def test_security_action_not_on_mutable_ref(template: dict) -> None:
    """security Action は可変参照(@main / @master)で参照しない。"""
    for step in template["jobs"]["security"]["steps"]:
        uses = str(step.get("uses", ""))
        if "claude-code-security-review" in uses:
            assert not uses.endswith(("@main", "@master"))


def test_notify_needs_all_gates(template: dict) -> None:
    needs = set(template["jobs"]["notify-success"]["needs"])
    assert CODE_EXECUTING_JOBS | {"security"} == needs
