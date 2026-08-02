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


@pytest.fixture(scope="session")
def dev_profile() -> dict:
    return load_yaml("profiles/development.yaml")


@pytest.fixture(scope="session")
def exp_profile() -> dict:
    return load_yaml("profiles/experiment.yaml")


@pytest.fixture(scope="session")
def res_profile() -> dict:
    return load_yaml("profiles/research.yaml")


@pytest.fixture(scope="session")
def providers() -> dict:
    return load_yaml("packs/python/providers.yaml")


@pytest.fixture(scope="session")
def docs_providers() -> dict:
    return load_yaml("packs/docs/providers.yaml")
