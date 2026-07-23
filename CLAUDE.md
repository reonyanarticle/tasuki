# tasuki 開発ガイド

tasuki は、AI エージェント間のタスク受け渡しを抽象度ゲートで検めながら GitHub issue を自走で完走させる Claude Code plugin。
このファイルは tasuki 自体を開発するためのガイドであり、plugin 利用者には読み込まれない(plugin ルートの CLAUDE.md はコンテキストに載らない。利用者向けの知識は skills/ に置く)。

## 正とする文書

- 実装の正は [docs/](docs/README.md)。docs 内で食い違いを見つけたら、docs を直してから実装する

## 実装前の必須確認

- 実装順は [docs/ROADMAP.md](docs/ROADMAP.md) の段階導入に従う(フェーズ1: G2 + GM のみ)
- Claude Code の機能仕様に依存する箇所(subagent の `model:` / `isolation:`、plugin.json スキーマ等)は、着手前に docs.claude.com の現行仕様を確認する。一覧は ROADMAP.md の「実装時検証事項」

## 規約

- plugin agent の `name:` には `tasuki-` 接頭辞を付ける(プロジェクト agent との衝突回避。衝突判定はファイル名ではなく `name:`)
- コミットは Conventional Commits(`<type>: <summary>`)
- 言語固有の情報は `packs/` の中にのみ置く(core は言語非依存を保つ)
- このリポジトリの Python コードは [docs/PYTHON.md](docs/PYTHON.md) に従う(lint = Ruff、整形 = Black、型 = basedpyright、uv 管理)
- ドキュメントの文体は一文一行とし、日本語の並列に中黒(・)を使わない
