# tasuki ドキュメント

tasuki の設計文書一式。
設計の正はこの docs であり、コードと食い違いを見つけたら docs を直してから実装する。
ただし**ループの手順そのものの正は [commands/loop.md](../commands/loop.md)** であり(docs は手順を説明する側)、開発規約の正は [.claude/rules/](../.claude/rules/) である。

## 読む順序

はじめて読むなら PHILOSOPHY、DESIGN、GATES の順を推奨する。
実装に着手するなら、先に ROADMAP の「実装時検証事項」を確認する。

| ドキュメント | 内容 |
|---|---|
| [PHILOSOPHY.md](PHILOSOPHY.md) | 思想。受け手基準の抽象度、バトンパスの3値判定、コンテキスト境界、製造業と制御工学との対応 |
| [DESIGN.md](DESIGN.md) | アーキテクチャ。三層構造、plugin ディレクトリ、状態管理、ロール定義、レイヤードレート構造(モデル選択) |
| [GATES.md](GATES.md) | ゲート体系。ゲートカタログ(受理ゲート〜統合 / 形式ゲート)、verdict スキーマ、レビュー観点カタログ(25観点) |
| [CONTRACTS.md](CONTRACTS.md) | 契約。プロファイル YAML、providers.yaml、issue / PR テンプレート、質問ルーティング、初期 fixture |
| [OPERATIONS.md](OPERATIONS.md) | 運用。`/tasuki:loop-init` と CI 生成、コスト管理とエスカレーション、メトリクス、回帰テスト |
| [INTEGRATION.md](INTEGRATION.md) | 橋渡し。外部の subagent、skill、検査ツールの接続点と、プロジェクト直下アセットとの統合ルール |
| [ROADMAP.md](ROADMAP.md) | 導入。v1 スコープ、段階導入、E2E の実施記録、拡張を撤回した記録(調査と実験)、未決事項、実装時検証事項 |
| [SECURITY.md](SECURITY.md) | 脅威モデルと信頼境界。v1 は信頼 issue 限定。守る範囲(CI)と守らない範囲(注入)、v2 ハードニング |
| [PYTHON.md](PYTHON.md) | この plugin リポジトリ自身の Python コーディング規約(lint = Ruff、整形 = Black、型 = basedpyright) |
| [FAQ.md](FAQ.md) | 導入時に実際に聞かれた質問と答え(worktree 分離、子 PR の扱い、replan、hotfix、起票支援) |

## 概念の置き場所

- ゲートとは何か、なぜ3値か → PHILOSOPHY
- どのゲートが何を検査するか → GATES
- ゲートのモデルとエスカレーション → DESIGN
- 契約 YAML の書き方 → CONTRACTS
- 実装をどこから始めるか → ROADMAP
- 出荷前レビュー(自動実行と規模制御) → OPERATIONS と CONTRACTS の preship_review