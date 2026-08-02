"""調査文書の出典 URL 到達性検査(決定的)。

対象ディレクトリ配下の markdown から http(s) URL を抽出し、到達できるかを検める。
到達できない URL があれば非0で終了し、URL 一覧を stderr へ出す。
リンクが生きていることは「主張が支持されていること」を意味しない(そちらは verifier の引用検証)。

使い方: python3 research_link_check.py <docs_dir>
標準ライブラリのみで動く(依存の追加インストールなし)。
"""

from __future__ import annotations

import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

TIMEOUT_SECONDS = 15
USER_AGENT = "tasuki-link-check/1"

# URL は ASCII の URL 文字だけを取る(日本語の句読点や括弧で確実に止める)。
# 丸括弧を含む URL(百科事典系)は取りこぼすが、到達性検査の偽陰性より偽陽性の抑制を優先する。
_URL = re.compile(r"https?://[A-Za-z0-9\-._~:/?#@!$&*+;=%]+")


def extract_urls(text: str) -> list[str]:
    """本文から URL を重複なく抽出する(コードブロック内も出典として数える)。"""
    urls = []
    for m in _URL.findall(text):
        u = m.rstrip(".,;:。、")
        if u not in urls:
            urls.append(u)
    return urls


def is_reachable(url: str) -> bool:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as res:
            return res.status < 400
    except urllib.error.HTTPError as e:
        if e.code in (403, 405, 429):  # HEAD 拒否やレート制限は GET で再確認する
            try:
                get_req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(get_req, timeout=TIMEOUT_SECONDS) as res:
                    return res.status < 400
            except OSError:
                return False
        return False
    except OSError:
        return False


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: research_link_check.py <docs_dir>", file=sys.stderr)
        return 2
    docs_dir = Path(argv[1])
    if not docs_dir.is_dir():
        print(f"docs_dir が無い: {docs_dir}", file=sys.stderr)
        return 1
    failed = False
    for f in sorted(docs_dir.rglob("*.md")):
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            failed = True
            print(f"{f}: UTF-8 として読めない({e})", file=sys.stderr)
            continue
        for url in extract_urls(text):
            if not is_reachable(url):
                failed = True
                print(f"{f}: 到達できない出典: {url}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
