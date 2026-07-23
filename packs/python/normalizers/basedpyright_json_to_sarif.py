"""basedpyright の JSON 出力を SARIF 2.1.0 に変換する normalizer。

core の findings 判定器は SARIF / JUnit XML のみを読む(docs/DESIGN.md)。
basedpyright は SARIF を直接出力できないため、CI 上でこのスクリプトを挟んで変換する。
終了コードは常に 0(ゲート判定は SARIF / summary を読む側が行う)。

Usage: python basedpyright_json_to_sarif.py <basedpyright.json> <output.sarif>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# basedpyright の severity → SARIF level
_LEVEL_MAP = {"error": "error", "warning": "warning", "information": "note"}


def _results_from_diagnostics(diagnostics: list[dict]) -> list[dict]:
    """generalDiagnostics から SARIF results を組み立てる。"""
    results: list[dict] = []
    for diag in diagnostics:
        start = diag.get("range", {}).get("start", {})
        results.append(
            {
                "ruleId": diag.get("rule", "basedpyright"),
                "level": _LEVEL_MAP.get(diag.get("severity", "error"), "error"),
                "message": {"text": diag.get("message", "").strip()},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": diag.get("file", "")},
                            "region": {
                                # pyright の行・桁は 0 始まり、SARIF は 1 始まり
                                "startLine": int(start.get("line", 0)) + 1,
                                "startColumn": int(start.get("character", 0)) + 1,
                            },
                        }
                    }
                ],
            }
        )
    return results


def convert(json_path: Path, sarif_path: Path) -> int:
    """変換を実行し、error レベルの件数を返す。"""
    report = json.loads(json_path.read_text())
    results = _results_from_diagnostics(report.get("generalDiagnostics", []))
    sarif = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "basedpyright",
                        "informationUri": "https://docs.basedpyright.com/",
                    }
                },
                "results": results,
            }
        ],
    }
    sarif_path.write_text(json.dumps(sarif, ensure_ascii=False, indent=2))
    return sum(1 for r in results if r["level"] == "error")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    error_count = convert(Path(argv[1]), Path(argv[2]))
    print(f"basedpyright findings: {error_count} error(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
