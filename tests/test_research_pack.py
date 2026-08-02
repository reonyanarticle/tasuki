"""docs pack の検査スクリプトの単体テスト(ネットワークに出ない範囲)。"""

from __future__ import annotations

import sys
from pathlib import Path

from conftest import ROOT

sys.path.insert(0, str(ROOT / "packs" / "docs" / "checks"))

import research_link_check as linkcheck  # pyright: ignore[reportMissingImports]
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


def test_schema_accepts_heading_with_suffix() -> None:
    # 「## 結論(離散値+確信度)と補足」のような拡張見出しも節として数える
    doc = FULL_DOC.replace("## 結論(離散値+確信度)", "### 結論(離散値+確信度)の詳細")
    assert "結論(離散値+確信度)" not in schemacheck.missing_sections(
        doc, schemacheck.DEFAULT_REQUIRED_SECTIONS
    )


def test_schema_main_fails_on_empty_dir(tmp_path: Path) -> None:
    assert schemacheck.main(["prog", str(tmp_path)]) == 1


def test_schema_main_green_on_valid_doc(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text(FULL_DOC, encoding="utf-8")
    assert schemacheck.main(["prog", str(tmp_path)]) == 0


def test_link_extraction_dedupes_and_strips_punctuation() -> None:
    text = "本文 https://example.com/a、再掲 https://example.com/a と (https://example.com/b)。"
    assert linkcheck.extract_urls(text) == ["https://example.com/a", "https://example.com/b"]


def test_link_main_fails_when_dir_missing(tmp_path: Path) -> None:
    assert linkcheck.main(["prog", str(tmp_path / "nai")]) == 1


def test_schema_main_fails_on_partially_missing_doc(tmp_path: Path) -> None:
    doc = FULL_DOC.replace("## 検索戦略の実行記録", "## 何か別の節")
    (tmp_path / "a.md").write_text(doc, encoding="utf-8")
    assert schemacheck.main(["prog", str(tmp_path)]) == 1


def test_schema_main_fails_on_non_utf8(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_bytes("結論".encode("shift_jis"))
    assert schemacheck.main(["prog", str(tmp_path)]) == 1


def test_is_reachable_falls_back_to_get_on_head_rejection(monkeypatch) -> None:
    """HEAD が 405 を返すサイトでは GET で再確認する(実ネットワークは使わない)。"""
    import urllib.error

    calls: list[str] = []

    class _Res:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def fake_urlopen(req, timeout=0):
        calls.append(req.get_method())
        if req.get_method() == "HEAD":
            raise urllib.error.HTTPError(
                req.full_url,
                405,
                "method not allowed",
                None,  # pyright: ignore[reportArgumentType]
                None,
            )
        return _Res()

    monkeypatch.setattr(linkcheck.urllib.request, "urlopen", fake_urlopen)
    assert linkcheck.is_reachable("https://example.com/x") is True
    assert calls == ["HEAD", "GET"]


def test_is_reachable_false_when_get_also_fails(monkeypatch) -> None:
    import urllib.error

    def fake_urlopen(req, timeout=0):
        raise urllib.error.HTTPError(
            req.full_url, 403, "forbidden", None, None  # pyright: ignore[reportArgumentType]
        )

    monkeypatch.setattr(linkcheck.urllib.request, "urlopen", fake_urlopen)
    assert linkcheck.is_reachable("https://example.com/x") is False
