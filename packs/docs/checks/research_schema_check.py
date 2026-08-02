"""調査文書の必須節検査(決定的)。

対象ディレクトリ配下の markdown が、契約の report_required_fields に対応する
`## 見出し` をすべて持つかを検める。欠落があれば非0で終了し、欠落一覧を stderr へ出す。
LLM を使わない(形式ゲートは機械判定のみ)。

使い方: python3 research_schema_check.py <docs_dir> [必須節名 ...]
必須節名を省略した場合は既定(research プロファイルの report_required_fields と同じ)を使う。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DEFAULT_REQUIRED_SECTIONS = [
    "問い⇔発見の対応表",
    "結論(離散値+確信度)",
    "反証と対立仮説",
    "除外と不採用の記録",
    "検索戦略の実行記録",
    "出典一覧",
]


def missing_sections(text: str, required: list[str]) -> list[str]:
    headings = {m.strip() for m in re.findall(r"^#{2,3}\s+(.+)$", text, re.M)}
    return [r for r in required if not any(r in h for h in headings)]


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: research_schema_check.py <docs_dir> [required ...]", file=sys.stderr)
        return 2
    docs_dir = Path(argv[1])
    required = argv[2:] or DEFAULT_REQUIRED_SECTIONS
    if not docs_dir.is_dir():
        print(f"docs_dir が無い: {docs_dir}(調査文書が未コミット)", file=sys.stderr)
        return 1
    files = sorted(docs_dir.rglob("*.md"))
    if not files:
        print(f"調査文書が1件も無い: {docs_dir}", file=sys.stderr)
        return 1
    failed = False
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            failed = True
            print(f"{f}: UTF-8 として読めない({e})", file=sys.stderr)
            continue
        miss = missing_sections(text, required)
        if miss:
            failed = True
            print(f"{f}: 必須節の欠落: {', '.join(miss)}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
