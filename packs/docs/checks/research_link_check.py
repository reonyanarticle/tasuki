"""調査文書の出典 URL 到達性検査(決定的)。

対象ディレクトリ配下の markdown から http(s) URL を抽出し、到達できるかを検める。
到達できない URL があれば非0で終了し、URL 一覧を stderr へ出す。
リンクが生きていることは「主張が支持されていること」を意味しない(そちらは verifier の引用検証)。

出典 URL は外部ページ由来の未検証データであり、この検査はそれを取得する。
そのため私有アドレスへの要求を拒否し(SSRF 対策)、リダイレクトは追従先を同じ基準で検め直す。
検査を走らせるのは開発端末と CI ランナーであり、
どちらも攻撃者が直接到達できない内部ホストに届く位置にいる。

使い方: python3 research_link_check.py <docs_dir>
標準ライブラリのみで動く(依存の追加インストールなし)。
"""

from __future__ import annotations

import ipaddress
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

TIMEOUT_SECONDS = 15
USER_AGENT = "tasuki-link-check/1"
MAX_URLS = 200  # 1回の検査で取得する URL の総数(調査文書の出典として現実的な上限)
MAX_REDIRECTS = 5

# URL は ASCII の URL 文字だけを取る(日本語の句読点で確実に止める)。
# 丸括弧は許可した上で、閉じ括弧の余りだけを後段で剥がす(百科事典系の
# `.../Diff_(Unix)` を途中で切ると、生きている出典を到達不能と誤検出する)。
_URL = re.compile(r"https?://[A-Za-z0-9\-._~:/?#@!$&*+;=%()]+")


def extract_urls(text: str) -> list[str]:
    """本文から URL を重複なく抽出する(コードブロック内も出典として数える)。"""
    urls = []
    for m in _URL.findall(text):
        u = m.rstrip(".,;:。、")
        while u.endswith(")") and u.count("(") < u.count(")"):
            u = u[:-1].rstrip(".,;:。、")
        if u not in urls:
            urls.append(u)
    return urls


class BlockedTarget(Exception):
    """検査してはいけない宛先(私有アドレス、非 http スキーム)。"""


def _assert_public_http(url: str) -> None:
    """公開の http(s) 宛先であることを確かめる。私有アドレスなら BlockedTarget。

    出典 URL は外部ページ由来であり、内部ホストへの到達可否を二値で漏らす調査手段になる。
    名前解決した全アドレスを検めるのは、公開名を私有アドレスへ向ける細工を防ぐためである。
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise BlockedTarget(f"http(s) 以外のスキーム: {parsed.scheme}")
    host = parsed.hostname
    if not host:
        raise BlockedTarget("ホスト名が無い")
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
    except OSError as e:
        raise BlockedTarget(f"名前解決に失敗: {e}") from e
    for info in infos:
        addr = ipaddress.ip_address(info[4][0])
        if not addr.is_global:  # ループバック、リンクローカル、RFC1918、共有アドレス等
            raise BlockedTarget(f"公開されていないアドレス: {addr}")


def _open(url: str, method: str) -> int:
    """リダイレクトを自分で辿る(追従先も毎回同じ基準で検める)。戻り値は最終ステータス。"""

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args: object, **kwargs: object) -> None:
            return None  # 追従は呼び出し側が制御する

    opener = urllib.request.build_opener(_NoRedirect)
    for _ in range(MAX_REDIRECTS):
        _assert_public_http(url)
        req = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
        try:
            with opener.open(req, timeout=TIMEOUT_SECONDS) as res:
                return res.status
        except urllib.error.HTTPError as e:
            if 300 <= e.code < 400:
                location = e.headers.get("Location") if e.headers else None
                if not location:
                    return e.code  # 追従先が無い 3xx は到達として扱う
                url = urllib.parse.urljoin(url, location)
                continue
            return e.code
    raise BlockedTarget("リダイレクトが多すぎる")


def is_reachable(url: str) -> bool:
    # 一時的なネットワーク不調(タイムアウト、接続断)を内容の欠陥と区別するため、
    # OSError は1回だけ再試行する(この検査の赤は子 issue の反復予算を消費する)
    for attempt in (1, 2):
        try:
            status = _open(url, "HEAD")
            if status in (403, 405, 429):  # HEAD 拒否やレート制限は GET で再確認する
                status = _open(url, "GET")
            return status < 400
        except BlockedTarget:
            raise
        except OSError:
            if attempt == 1:
                time.sleep(2)
                continue
            return False
    return False


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: research_link_check.py <docs_dir>", file=sys.stderr)
        return 2
    docs_dir = Path(argv[1])
    # 統合ブランチの初期状態(文書がまだ無い)を赤にしない(schema 検査と同じ判断)
    if not docs_dir.is_dir():
        print(f"docs_dir が無い(初期状態として緑): {docs_dir}", file=sys.stderr)
        return 0
    failed = False
    checked = 0
    for f in sorted(docs_dir.rglob("*.md")):
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            failed = True
            print(f"{f}: UTF-8 として読めない({e})", file=sys.stderr)
            continue
        for url in extract_urls(text):
            checked += 1
            if checked > MAX_URLS:
                # 打ち切りは黙って緑にしない(未検査を成功と誤読させない)
                failed = True
                print(f"{f}: 出典 URL が上限 {MAX_URLS} 件を超えた(未検査あり)", file=sys.stderr)
                return 1
            try:
                ok = is_reachable(url)
            except BlockedTarget as e:
                # 遮断は握りつぶさず検査の失敗として報告する(SSRF の試みが記録に残る)
                failed = True
                print(f"{f}: 検査を拒否した出典: {url}({e})", file=sys.stderr)
                continue
            if not ok:
                failed = True
                print(f"{f}: 到達できない出典: {url}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
