# コード規約

- plugin agent の `name:` には `tasuki-` 接頭辞を付ける(プロジェクト agent との衝突回避。衝突判定はファイル名ではなく `name:`)
- コミットは Conventional Commits(`<type>: <summary>`)
- 言語固有の情報は `packs/` の中にのみ置く(core は言語非依存を保つ)
- このリポジトリの Python コードは [docs/PYTHON.md](../../docs/PYTHON.md) に従う(lint = Ruff、整形 = Black、型 = basedpyright、uv 管理)
- 変更したら `uv run pytest` を実行する(plugin の整合性テスト。CI = validate.yml が PR で強制)
