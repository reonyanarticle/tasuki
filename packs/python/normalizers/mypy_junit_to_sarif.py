"""mypy の JUnit XML 出力を SARIF 2.1.0 に変換する normalizer。

core の findings 判定器は SARIF / JUnit XML のみを読む(docs/DESIGN.md)。
mypy は SARIF を直接出力できないため、CI 上でこのスクリプトを挟んで変換する。

Usage: python mypy_junit_to_sarif.py <mypy-junit.xml> <output.sarif>
"""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# mypy のエラー行: "path/to/file.py:12: error: メッセージ" 形式
_ERROR_LINE = re.compile(
    r"^(?P<file>[^:\n]+):(?P<line>\d+)(?::(?P<col>\d+))?: (?P<level>error|warning|note): (?P<message>.*)$",
    re.MULTILINE,
)

_LEVEL_MAP = {"error": "error", "warning": "warning", "note": "note"}


def _results_from_junit(junit_path: Path) -> list[dict]:
    """JUnit XML の failure テキストから SARIF results を組み立てる。"""
    tree = ET.parse(junit_path)
    results: list[dict] = []
    for failure in tree.iter("failure"):
        text = failure.text or ""
        for match in _ERROR_LINE.finditer(text):
            results.append(
                {
                    "ruleId": "mypy",
                    "level": _LEVEL_MAP[match.group("level")],
                    "message": {"text": match.group("message").strip()},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": match.group("file")},
                                "region": {
                                    "startLine": int(match.group("line")),
                                    **(
                                        {"startColumn": int(match.group("col"))}
                                        if match.group("col")
                                        else {}
                                    ),
                                },
                            }
                        }
                    ],
                }
            )
    return results


def convert(junit_path: Path, sarif_path: Path) -> int:
    """変換を実行し、error レベルの件数を返す。"""
    results = _results_from_junit(junit_path)
    sarif = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "mypy",
                        "informationUri": "https://mypy-lang.org/",
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
    print(f"mypy findings: {error_count} error(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
