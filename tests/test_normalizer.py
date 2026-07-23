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
