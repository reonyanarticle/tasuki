"""調査文書の必須節検査(決定的)。

対象ディレクトリ配下の markdown が、契約の report_required_fields に対応する
`## 見出し` をすべて持つかを検める。欠落があれば非0で終了し、欠落一覧を stderr へ出す。
LLM を使わない(形式ゲートは機械判定のみ)。

使い方: python3 research_schema_check.py <docs_dir> [必須節名 ...]
必須節名を省略した場合は既定を使う。
既定は research プロファイルの report_required_fields から、報告コメント専用の欄
(「参照した skill と委譲した subagent」)を除いたものと一致する(一致はテストが固定する)。
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


def _strip_fenced_code(text: str) -> str:
    # コードブロック内の「## 見出し」(テンプレート例等)を節として数えないため
    out: list[str] = []
    in_fence = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append(line)
    return "\n".join(out)


def missing_sections(text: str, required: list[str]) -> list[str]:
    # 完全一致で判定する。部分一致だと「出典一覧を今回は作らなかった理由」のような
    # 打ち消しの見出しが必須節として数えられ、検査が空洞化する
    headings = {m.strip() for m in re.findall(r"^#{2,3}\s+(.+)$", _strip_fenced_code(text), re.M)}
    return [r for r in required if r not in headings]


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: research_schema_check.py <docs_dir> [required ...]", file=sys.stderr)
        return 2
    docs_dir = Path(argv[1])
    required = argv[2:] or DEFAULT_REQUIRED_SECTIONS
    # 文書が0件の状態は緑にする。統合ブランチは空の状態から始まり、最初の子が
    # 取り込まれるまで docs_dir が存在しない(文書の存在自体は成果ゲートと PR の diff が保証する)
    if not docs_dir.is_dir():
        print(f"docs_dir が無い(初期状態として緑): {docs_dir}", file=sys.stderr)
        return 0
    files = sorted(docs_dir.rglob("*.md"))
    if not files:
        print(f"調査文書が0件(初期状態として緑): {docs_dir}", file=sys.stderr)
        return 0
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
