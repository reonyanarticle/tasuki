# tasuki ドキュメント

[tasuki-spec.md](../tasuki-spec.md)(v0.9)を分冊した設計文書である。
仕様と食い違いを見つけたら、docs を直してから実装する。

## 読む順序

はじめて読むなら PHILOSOPHY、DESIGN、GATES の順を推奨する。
実装に着手するなら、先に ROADMAP の「実装時検証事項」を確認する。

| ドキュメント | 内容 |
|---|---|
| [PHILOSOPHY.md](PHILOSOPHY.md) | 思想。受け手基準の抽象度、バトンパスの3値判定、コンテキスト境界、製造業と制御工学との対応 |
| [DESIGN.md](DESIGN.md) | アーキテクチャ。三層構造、plugin ディレクトリ、状態管理、ロール定義、レイヤードレート構造(モデル選択) |
| [GATES.md](GATES.md) | ゲート体系。ゲートカタログ(G0〜G4 / GM)、verdict スキーマ、レビュー観点カタログ(25観点) |
| [CONTRACTS.md](CONTRACTS.md) | 契約。プロファイル YAML、providers.yaml、issue / PR テンプレート、質問ルーティング、初期 fixture |
| [OPERATIONS.md](OPERATIONS.md) | 運用。`/tasuki:loop-init` と CI 生成、コスト管理とエスカレーション、メトリクス、回帰テスト |
| [INTEGRATION.md](INTEGRATION.md) | 橋渡し。外部の subagent、skill、検査ツールの接続点と、プロジェクト直下アセットとの統合ルール |
| [ROADMAP.md](ROADMAP.md) | 導入。v1 スコープ、段階導入(フェーズ1〜3)、未決事項、実装時検証事項 |
| [PYTHON.md](PYTHON.md) | この plugin リポジトリ自身の Python コーディング規約(lint = Ruff、整形 = Black、型 = basedpyright) |

## 概念の置き場所

- ゲートとは何か、なぜ3値か → PHILOSOPHY
- どのゲートが何を検査するか → GATES
- ゲートのモデルとエスカレーション → DESIGN
- 契約 YAML の書き方 → CONTRACTS
- 実装をどこから始めるか → ROADMAP
