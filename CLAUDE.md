# tasuki 開発ガイド

tasuki は、AI エージェント間のタスク受け渡しを抽象度ゲートで検めながら GitHub issue を自走で完走させる Claude Code plugin。
このファイルは tasuki 自体を開発するためのガイドであり、plugin 利用者には読み込まれない(plugin ルートの CLAUDE.md はコンテキストに載らない。利用者向けの知識は skills/ に置く)。

## 正とする文書

- 実装の正は [docs/](docs/README.md)。docs 内で食い違いを見つけたら、docs を直してから実装する

## 実装前の必須確認

- 実装順は [docs/ROADMAP.md](docs/ROADMAP.md) の段階導入に従う(フェーズ1: 着手ゲート + 形式ゲートのみ)
- Claude Code の機能仕様に依存する箇所(subagent の `model:` / `isolation:`、plugin.json スキーマ等)は、着手前に docs.claude.com の現行仕様を確認する。一覧は ROADMAP.md の「実装時検証事項」

## 規約

- plugin agent の `name:` には `tasuki-` 接頭辞を付ける(プロジェクト agent との衝突回避。衝突判定はファイル名ではなく `name:`)
- コミットは Conventional Commits(`<type>: <summary>`)
- 言語固有の情報は `packs/` の中にのみ置く(core は言語非依存を保つ)
- このリポジトリの Python コードは [docs/PYTHON.md](docs/PYTHON.md) に従う(lint = Ruff、整形 = Black、型 = basedpyright、uv 管理)
- 変更したら `uv run pytest` を実行する(plugin の整合性テスト。CI = validate.yml が PR で強制)
- ドキュメントの文体は一文一行とし、日本語の並列に中黒(・)を使わない

## PR を作る前の関門(このリポジトリ自身の開発フロー)

実装が固まったら、PR を作る前に次を通す。
順序に意味がある(機械が落とせるものを先に落とし、人間とレビューの時間を後段に使う)。

1. `uv run pytest` と Ruff / Black / basedpyright をすべて緑にする
2. **`/code-review` を5観点で回す。** 一度に全部を渡さず、1観点ずつ指定して5回に分ける。観点は [commands/loop.md](commands/loop.md) の「2g. 出荷前レビュー」の表を正とする(設計と統合、正しさと境界条件、テストの妥当性、複雑さと可読性、運用影響)。表をここに写さない(二重管理を避ける)
3. **所見をそのまま信じない。** 対象コードを読み、再現条件を確かめ、実在するものだけ直す(どのツリーに対して走ったかを最初に確認する。古いブランチや worktree に対する所見が混ざる)
4. 変更が認証、権限、外部入力、秘密情報、CI 設定のいずれかに触れるなら `/claude-security:claude-security` を回す
5. 直した結果をもう一度1に戻して緑にする
6. ここまで自分で確認できて初めて PR を作る
