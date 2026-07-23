# 導入戦略

## スコープ(v1)

### 含む

| 項目 | 内容 |
|---|---|
| ゲート機構 | abstraction ゲート(G0〜G4)+ mechanical ゲート(CI 実行) |
| ロール | orchestrator / decomposer / gate-reviewer(降と昇) / worker / verifier |
| 契約 | プロファイル YAML(フェーズ、待ち位置、ゲート、予算) |
| ブートストラップ | `/tasuki:loop-init`(言語検出から契約、テンプレ、CI の生成まで) |
| CI | plugin が生成する前提。既存 CI は前提にしない |
| 質問ルーティング | task-question / axis-question の型付けと宛先分離 |
| 橋渡し | 外部の subagent、skill、検査ツールを接続するインターフェース |
| language pack | python(uv / ruff / mypy / pytest) |

### 含まない

- python 以外の language pack(インターフェースだけ切っておく)
- タスク複雑度によるモデル自動選択(将来のコスト最適化候補)
- worker セッション内の常駐セキュリティガード(security-guidance 等はユーザー任意導入)
- 複数リポジトリ横断のループ

## 段階導入

抽象と具体の往復にはコストがあり、ゲート全部入りで始めるとオーバーヘッドでループ自体が回らない。
IE(工程分析)の「検査、運搬、停滞は付加価値を生まない」という原則に従い、ゲート(=検査)は必要最小限から始めて差し戻しの質で増減を判断する。
段階導入を標準とする。

### フェーズ1: G2(着手ゲート)+ GM

門前払いと契約照合の効果を差し戻しの質で確認する。

**フェーズ1の受け入れ条件(完了の定義)**：

- `/tasuki:loop-init` が素の Python リポジトリ(pyproject.toml のみ)に対して、契約雛形、issue / PR テンプレ、`loop-gates.yml`、ラベルを生成できる
- 必須欄が空の子 issue が門前払いで差し戻される(LLM 呼び出しなし)
- 手書き fixture 5件に対し、gate-reviewer(haiku)の判定が人間の正解ラベルと5件中4件以上一致する
- 差し戻し verdict が issue コメントに verdict スキーマ([GATES.md](GATES.md))の JSON で記録される
- G2 通過の子 issue を worker が worktree 上で実装し、draft PR 作成、GM(CI)実行まで到達する
- 差し戻し2連続で sonnet へのエスカレーションが発火する

### フェーズ2: G3(成果ゲート)を追加

昇る側の対応表検証を回す。

### フェーズ3: G0 / G1 / G4 とレイヤー並列実行

フルループへ移行する。

## 未決事項

1. G0(受理ゲート)のコスト見積もりを誰が書くか。起票者(人間)記入か、decomposer が見積もり案を出して人間承認か
2. `/tasuki:loop` の起動形態。手動起動のみか、スケジュール実行(automations)まで v1 に含むか
3. experiment プロファイルの成果物置き場。実験ログや生成モデル等の大容量成果物の保存先規約(GitHub 外ストレージとの接続)

## 実装時検証事項(着手前に公式ドキュメントで確認)

本仕様は Claude Code の機能仕様に依存する記述を含む。
以下は仕様策定時点の理解であり、**実装着手時に必ず docs.claude.com の現行ドキュメントで確認し、差異があれば仕様と docs を先に修正する**(思い込みでの実装開始を門前払いする)。

1. subagent frontmatter の `model:` フィールド。指定可能な値と、Fable 5 のモデル名文字列。指定不可の場合はメインセッション= orchestrator とする代替構成(レート構造は維持可能、[DESIGN.md](DESIGN.md) 参照)
2. subagent の `isolation: worktree` 設定。記法と挙動(worktree の自動作成と掃除の範囲)
3. plugin.json のスキーマ。commands / agents / skills / hooks の配置規約とマニフェスト書式
4. subagent からの `gh` CLI 利用。allowed-tools の指定方法と、Bash 許可の粒度(`Bash(gh *)` 等)
5. `/security-review` の headless 実行。`claude -p` からのスラッシュコマンド呼び出し可否。不可なら GitHub Action 側([OPERATIONS.md](OPERATIONS.md))のみを GM に使う
6. GitHub sub-issues / issue dependencies。`gh` CLI と REST API の対応範囲。未対応操作は GraphQL API へフォールバック
7. plugin からの CI workflow ファイル生成。GitHub Apps / Actions の権限(`workflows` 書き込み権限が必要な点)
