"""basedpyright JSON → SARIF normalizer の単体テスト。"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from conftest import ROOT

_SPEC = importlib.util.spec_from_file_location(
    "basedpyright_json_to_sarif",
    ROOT / "packs/python/normalizers/basedpyright_json_to_sarif.py",
)
assert _SPEC and _SPEC.loader
normalizer = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(normalizer)


@pytest.fixture
def report() -> dict:
    return {
        "generalDiagnostics": [
            {
                "file": "src/app.py",
                "severity": "error",
                "message": "bad type",
                "range": {"start": {"line": 11, "character": 4}},
                "rule": "reportReturnType",
            },
            {
                "file": "src/app.py",
                "severity": "warning",
                "message": "unused",
                "range": {"start": {"line": 19, "character": 0}},
            },
            {
                "file": "src/util.py",
                "severity": "information",
                "message": "note",
                "range": {"start": {"line": 2, "character": 0}},
            },
        ],
        "summary": {"errorCount": 1},
    }


def test_convert(tmp_path: Path, report: dict) -> None:
    src = tmp_path / "basedpyright.json"
    dst = tmp_path / "out.sarif"
    src.write_text(json.dumps(report))

    error_count = normalizer.convert(src, dst)

    assert error_count == 1
    sarif = json.loads(dst.read_text())
    results = sarif["runs"][0]["results"]
    assert [r["level"] for r in results] == ["error", "warning", "note"]
    # pyright は 0 始まり、SARIF は 1 始まり
    region = results[0]["locations"][0]["physicalLocation"]["region"]
    assert (region["startLine"], region["startColumn"]) == (12, 5)
    # rule が無い診断はツール名にフォールバック
    assert results[1]["ruleId"] == "basedpyright"


def test_convert_empty_diagnostics(tmp_path: Path) -> None:
    src = tmp_path / "empty.json"
    dst = tmp_path / "out.sarif"
    src.write_text(json.dumps({"generalDiagnostics": [], "summary": {"errorCount": 0}}))

    assert normalizer.convert(src, dst) == 0
    assert json.loads(dst.read_text())["runs"][0]["results"] == []


def test_main_usage_error() -> None:
    assert normalizer.main(["prog"]) == 2


def test_absolute_paths_become_repo_relative(tmp_path: Path) -> None:
    """絶対パスは repo ルートからの相対 uri になること(code scanning の対応づけ要件)。"""
    root = tmp_path / "repo"
    report = {
        "generalDiagnostics": [
            {
                "file": str(root / "src/api.py"),
                "severity": "error",
                "message": "bad",
                "range": {"start": {"line": 0, "character": 0}},
            }
        ]
    }
    src = tmp_path / "in.json"
    src.write_text(json.dumps(report))
    out = tmp_path / "out.sarif"
    normalizer.convert(src, out, root=root)
    sarif = json.loads(out.read_text())
    uri = sarif["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"][
        "uri"
    ]
    assert uri == "src/api.py"


def test_unknown_severity_degrades_to_note(tmp_path: Path) -> None:
    """未知の severity は error に昇格させず note に倒すこと。"""
    report = {
        "generalDiagnostics": [
            {
                "file": "a.py",
                "severity": "hint",
                "message": "unreachable",
                "range": {"start": {"line": 0, "character": 0}},
            }
        ]
    }
    src = tmp_path / "in.json"
    src.write_text(json.dumps(report))
    out = tmp_path / "out.sarif"
    error_count = normalizer.convert(src, out)
    assert error_count == 0
    assert json.loads(out.read_text())["runs"][0]["results"][0]["level"] == "note"


@pytest.mark.parametrize(
    "raw",
    [
        "",  # typecheck が落ちて 0 バイトになった場合
        "{ broken",
        '{"generalDiagnostics": null}',
        '{"generalDiagnostics": [{"file": null, "range": null, "severity": null}]}',
    ],
    ids=["empty", "malformed", "null-diagnostics", "null-fields"],
)
def test_broken_input_still_writes_sarif(tmp_path: Path, raw: str) -> None:
    """入力が壊れていても例外を投げず SARIF を書くこと(後続の upload-sarif を守る)。"""
    src = tmp_path / "in.json"
    src.write_text(raw)
    out = tmp_path / "out.sarif"
    assert normalizer.convert(src, out) == 0
    assert json.loads(out.read_text())["version"] == "2.1.0"


def test_binary_input_does_not_raise(tmp_path: Path) -> None:
    """UTF-8 として壊れた出力でも例外を投げないこと。

    kill された typecheck は多バイト文字の途中で切れたファイルを残しうる。
    ここで UnicodeDecodeError が漏れると、後続の upload-sarif が
    「ファイルが無い」で失敗し、本当の原因が隠れる。
    """
    src = tmp_path / "in.json"
    src.write_bytes(b'{"generalDiagnostics": [{"message": "\xe6\x97')  # 途中で切れた UTF-8
    out = tmp_path / "out.sarif"
    assert normalizer.convert(src, out) == 0
    assert json.loads(out.read_text())["version"] == "2.1.0"


def test_infinite_line_number_does_not_raise(tmp_path: Path) -> None:
    """行番号が inf でも例外を投げないこと(JSON の 1e400 は inf になる)。"""
    src = tmp_path / "in.json"
    src.write_text(
        '{"generalDiagnostics": [{"file":"a.py","severity":"error","message":"m",'
        '"range":{"start":{"line":1e400,"character":0}}}]}'
    )
    out = tmp_path / "out.sarif"
    assert normalizer.convert(src, out) == 1
    assert (
        json.loads(out.read_text())["runs"][0]["results"][0]["locations"][0]["physicalLocation"][
            "region"
        ]["startLine"]
        == 1
    )
