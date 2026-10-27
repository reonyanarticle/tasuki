"""tasuki plugin の整合性テスト共通フィクスチャ。"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent

_FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.S)


def load_yaml(relpath: str) -> dict:
    """リポジトリ相対パスの YAML を読む。"""
    return yaml.safe_load((ROOT / relpath).read_text())


def frontmatter(path: Path) -> dict:
    """markdown の frontmatter を dict で返す。無ければ AssertionError。"""
    match = _FRONTMATTER.match(path.read_text())
    assert match, f"frontmatter がない: {path}"
    return yaml.safe_load(match.group(1))


# /tasuki:loop の手順を構成するファイル(入口と、節ごとの skill)。節の順に並べる。
# 入口の対応表(commands/loop.md の「手順の読み込み」)と一致することは test_docs が検める。
LOOP_PROCEDURE_FILES = (
    "commands/loop.md",
    "skills/loop-rules/SKILL.md",
    "skills/loop-restore/SKILL.md",
    "skills/loop-plan/SKILL.md",
    "skills/loop-child/SKILL.md",
    "skills/loop-merge/SKILL.md",
    "skills/loop-brake/SKILL.md",
)


def loop_procedure() -> str:
    """/tasuki:loop の手順全体を、入口の frontmatter を先頭に節の順で連結して返す。

    手順は compaction に耐えるよう入口と節ごとの skill に分けてある。テストは手順の
    中身を1つの文書として検めるため、節の skill の frontmatter を外して連結する。
    """
    parts = []
    for i, rel in enumerate(LOOP_PROCEDURE_FILES):
        text = (ROOT / rel).read_text()
        parts.append(text if i == 0 else _FRONTMATTER.sub("", text, count=1))
    return "\n".join(parts)


@pytest.fixture(scope="session")
def dev_profile() -> dict:
    return load_yaml("profiles/tasuki.yaml")


@pytest.fixture(scope="session")
def providers() -> dict:
    return load_yaml("packs/python/providers.yaml")
