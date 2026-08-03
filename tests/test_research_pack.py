"""docs pack の検査スクリプトの単体テスト(hermetic: ネットワークに出ない)。"""

from __future__ import annotations

import sys
from pathlib import Path

from conftest import ROOT

sys.path.insert(0, str(ROOT / "packs" / "docs" / "checks"))

import research_schema_check as schemacheck  # pyright: ignore[reportMissingImports]

FULL_DOC = """# 調査: 例

## 問い⇔発見の対応表

| 問い | 発見 |

## 結論(離散値+確信度)

採用(確信度: 中)

## 反証と対立仮説

探したが見つからなかった。

## 除外と不採用の記録

なし。

## 検索戦略の実行記録

検索語 A、B。

## 出典一覧

- [S1] https://example.com/a
"""


def test_schema_passes_when_all_sections_present() -> None:
    assert schemacheck.missing_sections(FULL_DOC, schemacheck.DEFAULT_REQUIRED_SECTIONS) == []


def test_schema_reports_missing_sections() -> None:
    doc = FULL_DOC.replace("## 反証と対立仮説", "## 別の節")
    miss = schemacheck.missing_sections(doc, schemacheck.DEFAULT_REQUIRED_SECTIONS)
    assert miss == ["反証と対立仮説"]


def test_schema_requires_exact_heading() -> None:
    # 部分一致は「出典一覧を今回は作らなかった理由」のような打ち消し見出しを
    # 必須節として数えてしまうため、完全一致だけを認める
    doc = FULL_DOC.replace("## 出典一覧", "## 出典一覧を今回は作らなかった理由")
    assert schemacheck.missing_sections(doc, schemacheck.DEFAULT_REQUIRED_SECTIONS) == ["出典一覧"]


def test_schema_accepts_level3_heading() -> None:
    doc = FULL_DOC.replace("## 結論(離散値+確信度)", "### 結論(離散値+確信度)")
    assert "結論(離散値+確信度)" not in schemacheck.missing_sections(
        doc, schemacheck.DEFAULT_REQUIRED_SECTIONS
    )


def test_schema_ignores_headings_inside_code_blocks() -> None:
    # テンプレート例としてコードブロックに書いた見出しを実在の節と数えない
    doc = FULL_DOC.replace(
        "## 出典一覧\n\n- [S1] https://example.com/a\n",
        "```\n## 出典一覧\n```\n",
    )
    assert schemacheck.missing_sections(doc, schemacheck.DEFAULT_REQUIRED_SECTIONS) == ["出典一覧"]


def test_schema_main_green_on_missing_or_empty_dir(tmp_path: Path) -> None:
    # 統合ブランチの初期状態(文書がまだ無い)を赤にしない
    assert schemacheck.main(["prog", str(tmp_path)]) == 0
    assert schemacheck.main(["prog", str(tmp_path / "nai")]) == 0


def test_schema_main_green_on_valid_doc(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text(FULL_DOC, encoding="utf-8")
    assert schemacheck.main(["prog", str(tmp_path)]) == 0


def test_schema_main_fails_on_partially_missing_doc(tmp_path: Path) -> None:
    doc = FULL_DOC.replace("## 検索戦略の実行記録", "## 何か別の節")
    (tmp_path / "a.md").write_text(doc, encoding="utf-8")
    assert schemacheck.main(["prog", str(tmp_path)]) == 1


def test_schema_main_fails_on_non_utf8(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_bytes("結論".encode("shift_jis"))
    assert schemacheck.main(["prog", str(tmp_path)]) == 1


def test_docs_pack_commands_use_docs_dir_placeholder() -> None:
    """provider コマンドは <docs_dir> プレースホルダを使い、パスを二重に書かないこと。

    リテラルで書くと、repo override で docs_dir を変えても検査対象が変わらない。
    """
    import yaml

    pack = yaml.safe_load((ROOT / "packs/docs/providers.yaml").read_text())
    assert pack["docs_dir"]
    for name, provider in pack["providers"].items():
        assert "<docs_dir>" in provider["command"], name
        assert pack["docs_dir"] not in provider["command"], name


def test_schema_url_extraction_dedupes_and_keeps_parens() -> None:
    text = "本文 https://example.com/a、再掲 https://example.com/a と https://en.wikipedia.org/wiki/Diff_(Unix))"
    assert schemacheck.extract_urls(text) == [
        "https://example.com/a",
        "https://en.wikipedia.org/wiki/Diff_(Unix)",
    ]


def test_schema_flags_malformed_urls_offline() -> None:
    """出典 URL の形式検査はオフラインで決定的に行う(取得はしない)。

    範囲外ポートは urlparse の .port が ValueError を上げる形式であり、
    放置すると URL を扱う後段(verifier 等)で壊れる。
    """
    text = "出典 https://example.com:99999/x と https://ok.example/y"
    assert schemacheck.malformed_urls(text) == ["https://example.com:99999/x"]


def test_schema_main_fails_on_malformed_url(tmp_path: Path) -> None:
    doc = FULL_DOC + "\n追加出典 https://example.com:99999/x\n"
    (tmp_path / "a.md").write_text(doc, encoding="utf-8")
    assert schemacheck.main(["prog", str(tmp_path)]) == 1


def test_checks_are_hermetic_no_network_imports() -> None:
    """packs の検査スクリプトはネットワークに出ない(mechanical ゲートは hermetic)。

    到達性検査を一度置いて、環境差の赤(ボット遮断、リダイレクト追従の版差)と
    SSRF の攻撃面を実際に生んだ。検査はリポジトリの内容だけで判定する。
    """
    for script in (ROOT / "packs").rglob("checks/*.py"):
        text = script.read_text()
        for banned in ("urllib.request", "import socket", "http.client", "import requests"):
            assert banned not in text, (script.name, banned)
