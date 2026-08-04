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
    assert set(template["jobs"]) == CODE_EXECUTING_JOBS | {
        "tampering",
        "security",
        "notify-success",
    }


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
    """typecheck の合否は fail-closed な件数読み取りが決める(summary 欠落で失敗する)。

    件数の読み方は言語依存なので pack が持つ。core は placeholder を置くだけであり、
    fail-closed の保証は pack 側(`jq -er` の -e)で検査する。
    """
    steps = template["jobs"]["typecheck"]["steps"]
    gate_steps = [s for s in steps if s.get("name") == "typecheck gate"]
    assert gate_steps
    assert "<pack.ci.blocking_count.typecheck>" in gate_steps[0]["run"]

    pack = yaml.safe_load((ROOT / "packs/python/providers.yaml").read_text())
    reader = pack["ci"]["blocking_count"]["typecheck"]
    assert "jq -er" in reader, reader


def test_core_template_has_no_language_specifics() -> None:
    """core(loop-init)に言語固有のツール名を書かない(CLAUDE.md の三層構造)。

    2言語目を pack の追加だけで通すための不変条件。
    """
    text = (ROOT / "commands/loop-init.md").read_text()
    forbidden = [
        "setup-uv",
        "uv sync",
        "uv.lock",
        "basedpyright",
        "errorCount",
        "pytest.ini",
        "pyrightconfig",  # basedpyright の部分文字列では拾えないため個別に禁止
        "tox.ini",
        "setup.cfg",
        "conftest.py",
        "pyproject",
    ]
    found = [tok for tok in forbidden if tok in text]
    assert not found, found


def test_security_action_not_on_mutable_ref(template: dict) -> None:
    """security Action は可変参照(@main / @master)で参照しない。"""
    for step in template["jobs"]["security"]["steps"]:
        uses = str(step.get("uses", ""))
        if "claude-code-security-review" in uses:
            assert not uses.endswith(("@main", "@master"))


def test_notify_needs_all_gates(template: dict) -> None:
    needs = set(template["jobs"]["notify-success"]["needs"])
    assert CODE_EXECUTING_JOBS | {"tampering", "security"} == needs


def test_tampering_job_does_not_execute_pr_code(template: dict) -> None:
    """改変検知は PR のコードを実行しない独立 job であること。

    同じ job でコードを実行してから検知すると、実行されたコード(pytest が収集で
    import する conftest.py 等)が base ref を書き換えて検知自体を無効化できる。
    """
    steps = template["jobs"]["tampering"]["steps"]
    runs = " ".join(s.get("run", "") for s in steps)
    uses = [s.get("uses", "") for s in steps]
    assert any(u.startswith("actions/checkout") for u in uses)
    # setup と install と provider の実行を持たない(checkout と diff だけ)
    assert not any("setup" in u for u in uses), uses
    assert "echo dummy" not in runs  # provider コマンドの置換痕跡が無いこと
    # base はこの job で取得し直す(ローカルの remote-tracking ref を信用しない)
    assert "git fetch" in runs
    # 検知の中身が test job から失われていないこと
    assert "def test_" in runs
    assert "config_tampering" in runs or "conf.diff" in runs


def test_code_executing_jobs_have_no_tampering_check(template: dict) -> None:
    """provider を実行する job に改変検知を埋め込まない(順序の逆転を防ぐ)。"""
    for name in CODE_EXECUTING_JOBS:
        runs = " ".join(s.get("run", "") for s in template["jobs"][name]["steps"])
        assert "def test_" not in runs, name
        assert "conf.diff" not in runs, name


def test_conftest_pathspec_matches_repo_root() -> None:
    """conftest.py の改変検知が直下のファイルも対象にすること。

    git の pathspec は `**/conftest.py` では直下の conftest.py にマッチしない。
    SECURITY.md が「全 conftest.py を対象にする」と掲げているため、ここで固定する。
    """
    pack = yaml.safe_load((ROOT / "packs/python/providers.yaml").read_text())
    paths = pack["ci"]["config_tampering"]["paths"]
    assert "conftest.py" in paths, paths  # 直下
    assert any(p.startswith(":(glob)") and p.endswith("conftest.py") for p in paths), paths
    assert "conftest.py" in pack["ci"]["new_config_files"]


def test_generation_forbids_empty_pathspec_expansion() -> None:
    """空リストのキーをそのまま展開しない規則が生成手順にあること。

    `git diff -- ` は pathspec が空だと全ファイルを対象にする。
    空リストやキー欠落をそのまま埋めると、ファイルを追加した PR がすべて
    改変検知に該当し、1件も取り込めなくなる(試作した pack で実際に踏んだ)。
    """
    init = (ROOT / "commands/loop-init.md").read_text()
    assert "値が空リストのキー、またはキー自体を持たないブロックは出力しない" in init
    assert "pathspec が空だと全ファイルを対象にする" in init
