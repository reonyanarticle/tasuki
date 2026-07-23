# Python コーディング規約

この plugin リポジトリ自身の Python コード(`packs/python/normalizers/` 等、tasuki の開発で書くコード)に適用する規約である。
**対象リポジトリ(plugin の導入先)には適用しない。**
worker は対象リポジトリの CLAUDE.md と skill の規約に従う([INTEGRATION.md](INTEGRATION.md))。
なお python pack のデフォルトツール選定([providers.yaml](../packs/python/providers.yaml))は本規約と同じ選定に揃えているが、対象リポジトリは repo override で変更できる。

出典は Astral 公式(docs.astral.sh)、Real Python、PEP 484 / 526、Effective Python(第3版)。
📘 印は Effective Python 由来の設計原則。

## 0. 確定事項(参考文献より優先)

- **lint = Ruff**。Ruff は lint 専用に使う
- **整形 = Black**。参考文献は `ruff format` 単独を推すが、本規約は Black を採用する
- **型チェッカ = basedpyright**(pyright 系)。`ty` はプレビューのため不採用。**mypy は採用しない**
- **パッケージと環境の管理は uv を単一の真実の源**とする。pip / virtualenv / pyenv / poetry を混在させない
- **テスト = pytest**(補助: `pytest-cov`、必要なら `pytest-asyncio` / `hypothesis`)
- **型定義は `models.py`、グローバル状態と設定は `settings.py`(pydantic-settings)に集約**する。これはアプリケーション規模のコードを書く場合の標準であり、normalizer のような単発スクリプトには適用しない

## 1. ツールチェーン

- 依存追加は `uv add <pkg>`、開発依存は `uv add --dev <pkg>`、実行は `uv run <cmd>`(手動 activate 不要)
- Python バージョンは `uv python pin` + `.python-version` でプロジェクト固定。`uv.lock` はコミットし、手動編集しない
- lint: `uv run ruff check .`(自動修正は `--fix`)。日本語コメント中の全角文字を誤検知する `RUF001`〜`RUF003` は無効化する
- 整形: `uv run black .`(チェックは `--check`)
- 型: `uv run basedpyright`。新規プロジェクトは standard で開始し、段階的に厳しくする
- 設定は `pyproject.toml` に集約する(setup.py / setup.cfg / .flake8 / mypy.ini を新設しない)

```toml
[tool.ruff]
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM", "RUF", "PTH", "C4", "PIE"]
ignore = ["RUF001", "RUF002", "RUF003"]  # 日本語の全角文字を誤検知するため

[tool.black]
line-length = 100

[tool.basedpyright]
typeCheckingMode = "standard"
reportMissingTypeStubs = false

[tool.pytest.ini_options]
testpaths = ["tests"]
```

## 2. 型ヒント(必須)

- 公開 API と重要ロジックには必ず型ヒントを付ける。型はドキュメントではなく、補完、静的解析、実行時検証の基盤である
- モダン記法を使う: `X | None`(`Optional` 不可)、`list[int]` / `dict[str, int]`(`typing.List` 等不可)。必要に応じ `from __future__ import annotations`
- 構造的部分型は `Protocol` を使う(継承を強制しない)。継承を強制したいときのみ ABC
- `Any` は最小限にする。動的データ(JSON 等)は早期に具体型へナローイングする
- 構造化データは TypedDict → dataclass → Pydantic を用途で使い分け、実行時バリデーションが要るなら Pydantic
- 📘 辞書ネストやタプル多用で複雑化したら、その場しのぎをやめて dataclass 等にリファクタし、意図と型を明示する

## 3. アーキテクチャと設計

- **コアを純粋に保つ(Ports & Adapters)**。中核ロジックは純粋関数+データクラスに閉じ、フレームワークや I/O を知らないこと。副作用(外部 API、DB、ファイル)は外側のシェル層へ
- 小さな自動化でも「ソフトウェア」として構造化する(実データ操作や外部 API を扱う時点でスクリプトではない)
- 責務でモジュールを分割し、巨大モジュールを避ける
- 📘 戻り値が4つ以上なら専用の結果オブジェクト(dataclass 等)を返す。特殊状態を `None` で表さず例外を送出する
- 📘 例外は階層設計にする。ルート独自例外を定義して派生させ、呼び出し側が対処できる粒度で投げる
- 📘 リソースは必ず `with`(コンテキストマネージャ)で扱う

## 4. コーディングスタイル

- PEP 8(4スペース、関数 snake_case、クラス PascalCase、定数 UPPER、private は `_` 前置)。整形は Black に任せ、人手で議論しない
- f-string を標準とする(`%` / `.format()` 不可)。デバッグは `f"{value=}"`
- `pathlib.Path` を使う(`os.path` 不可)
- データ保持は `dataclass`(`__init__` / `__repr__` / `__eq__` を手書きしない)
- import 順は Ruff(isort)に従う。相対 import は使わない
- 自己文書化を優先する。命名と構造で意図を表し、コメントは「why」を書いて「what」を繰り返さない。docstring は日本語可
- docstring を各関数、クラス、モジュールに付け、`__all__` で公開 API を明示する

## 5. Pythonic な書き方(📘 Effective Python)

- 複雑な式を1行に詰めない(ヘルパーへ抽出)。`match` は分割代入を伴う分岐に限る
- 手動インデックスより `enumerate`、複数イテラブルは `zip`
- 辞書の欠損キーは `get` / `setdefault` / `defaultdict` を使い分ける
- `map` / `filter` より内包表記。ただし3段以上ネストする内包表記は通常ループに展開する
- 大きなデータはジェネレータ(`yield`)で逐次処理する
- 可変デフォルト引数の罠: デフォルトに `[]` / `{}` / 現在時刻を使わず `None` を番兵にする
- 並行性は用途で使い分ける: ブロッキング I/O は `Thread`、CPU バウンドは `Process`、高水準は `concurrent.futures`。性能は推測でなく計測(`cProfile`)

## 6. 運用と品質

- テストは pytest のフィクスチャで前提を整え、依存をモック分離する
- CI で lint、整形、型チェック、テストを必須化する(基準未達はマージ不可)
- 構造化ログを小規模でも入れる。依存脆弱性は `uv audit`
- pre-commit でコミット前に Ruff、Black、型チェックを走らせる(CI 往復を防ぐ)

## 7. 一次情報

- uv: https://docs.astral.sh/uv/
- Ruff: https://github.com/astral-sh/ruff
- basedpyright: https://docs.basedpyright.com/
- Real Python(Best Practices): https://realpython.com/tutorials/best-practices/
- PEP 484 / PEP 526、Effective Python 3rd Edition: https://effectivepython.com/
