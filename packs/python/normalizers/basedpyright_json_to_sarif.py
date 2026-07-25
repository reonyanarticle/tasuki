"""basedpyright の JSON 出力を SARIF 2.1.0 に変換する normalizer。

core の findings 判定器は SARIF / JUnit XML のみを読む(docs/DESIGN.md)。
basedpyright は SARIF を直接出力できないため、CI 上でこのスクリプトを挟んで変換する。
変換に成功する限り終了コードは 0(ゲート判定は SARIF / summary を読む側が行う)。
入力が壊れている場合も SARIF を空 results で書き出し、CI の後段(upload-sarif)を
道連れにしない。引数不正のみ 2 を返す。

Usage: python basedpyright_json_to_sarif.py <basedpyright.json> <output.sarif>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# basedpyright の severity → SARIF level
# 未知の severity は note に倒す。error に倒すと、CI ゲートが見る errorCount とは
# 一致しない件数が PR にブロック相当で表示される。
_LEVEL_MAP = {"error": "error", "warning": "warning", "information": "note"}
_DEFAULT_LEVEL = "note"


def _int_or_zero(value: object) -> int:
    """0 始まりの行・桁を安全に読む(null や非数値は 0 とみなす)。"""
    try:
        return int(value)  # pyright: ignore[reportArgumentType]
    except (TypeError, ValueError):
        return 0


def _relative_uri(raw: object, root: Path) -> str:
    """SARIF の uri をリポジトリルートからの相対パスにする。

    basedpyright は絶対パスを出す。絶対パスのままだと code scanning が
    追跡対象ファイルに対応づけられず、PR に注釈が出ない。
    """
    if not isinstance(raw, str) or not raw:
        return ""
    path = Path(raw)
    if not path.is_absolute():
        return path.as_posix()
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        # ルート外のファイル(依存ライブラリ等)はそのまま残す
        return path.as_posix()


def _results_from_diagnostics(diagnostics: list[dict], root: Path) -> list[dict]:
    """generalDiagnostics から SARIF results を組み立てる。"""
    results: list[dict] = []
    for diag in diagnostics:
        if not isinstance(diag, dict):
            continue
        raw_range = diag.get("range")
        raw_start = raw_range.get("start") if isinstance(raw_range, dict) else None
        start = raw_start if isinstance(raw_start, dict) else {}
        severity = diag.get("severity")
        message = diag.get("message")
        results.append(
            {
                "ruleId": diag.get("rule") or "basedpyright",
                "level": (
                    _LEVEL_MAP.get(severity, _DEFAULT_LEVEL)
                    if isinstance(severity, str)
                    else _DEFAULT_LEVEL
                ),
                "message": {"text": message.strip() if isinstance(message, str) else ""},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": _relative_uri(diag.get("file"), root)},
                            "region": {
                                # pyright の行・桁は 0 始まり、SARIF は 1 始まり
                                "startLine": _int_or_zero(start.get("line")) + 1,
                                "startColumn": _int_or_zero(start.get("character")) + 1,
                            },
                        }
                    }
                ],
            }
        )
    return results


def _load_report(json_path: Path) -> dict:
    """basedpyright の出力を読む。壊れていても例外を投げず空とみなす。

    typecheck が OOM 等で落ちると 0 バイトのファイルが残る。ここで例外を投げると
    SARIF が生成されず、後続の upload-sarif が「ファイルが無い」で失敗して
    本当の原因が隠れる。
    """
    try:
        report = json.loads(json_path.read_text())
    except (OSError, ValueError) as exc:
        # ValueError は JSONDecodeError と UnicodeDecodeError の両方を捕らえる。
        # 途中で kill された typecheck は UTF-8 の途中で切れたファイルを残しうる。
        print(f"basedpyright の出力を読めなかった: {exc}", file=sys.stderr)
        return {}
    return report if isinstance(report, dict) else {}


def convert(json_path: Path, sarif_path: Path, root: Path | None = None) -> int:
    """変換を実行し、error レベルの件数を返す。"""
    report = _load_report(json_path)
    diagnostics = report.get("generalDiagnostics", [])
    if not isinstance(diagnostics, list):
        diagnostics = []
    results = _results_from_diagnostics(diagnostics, root or Path.cwd())
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
