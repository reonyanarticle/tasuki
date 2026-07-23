# アーキテクチャとロール

設計判断の由来は [PHILOSOPHY.md](PHILOSOPHY.md)、個々のゲートの仕様は [GATES.md](GATES.md) を参照。

## 三層構造

言語に固有な情報は language pack の中にのみ現れる。
2言語目は pack を1枚追加するだけで対応する。

```
core(言語非依存)
├── ゲート分類・verdict スキーマ・契約スキーマ
├── orchestrator ロジック(レイヤー実行・差し戻し管理・エスカレーション)
├── 質問ルーティング
├── findings 判定器(SARIF / JUnit XML のみを読む)
└── テンプレ生成器(契約 → issue テンプレ / CI workflow)

language pack(v1: python)
├── providers.yaml(lint / format / typecheck / test / security のコマンド定義)
├── 言語検出条件(pyproject.toml の存在)
└── normalizer(SARIF 非対応ツールの出力変換)

repo override(プロジェクト固有)
└── コマンド・閾値・待ち位置定義の上書きのみ
```

core の findings 判定器が SARIF / JUnit XML のみを読む点が、言語非依存を成立させる要である。
ツール固有の出力形式は pack の normalizer が吸収する。

## plugin ディレクトリ構成

```
tasuki/
├── .claude-plugin/plugin.json    # name: tasuki
├── skills/
│   ├── gate-review/SKILL.md      # ゲート判定手順(3値判定・差し戻し文の書式)
│   ├── baton-contract/SKILL.md   # 契約(待ち位置)の書き方・読み方
│   └── loop-report/SKILL.md      # レポート作成手順(対応表必須)
├── agents/
│   ├── decomposer.md
│   ├── gate-reviewer.md          # haiku(G2 標準)。コンテキスト非共有・読み取り専用
│   ├── gate-reviewer-sonnet.md   # sonnet(G3 標準、G2 エスカレーション先)
│   ├── gate-reviewer-opus.md     # opus(G0/G1/G4 標準、G3 エスカレーション先)
│   ├── worker.md                 # isolation: worktree
│   └── verifier.md
├── commands/
│   ├── loop-init.md              # ブートストラップ
│   ├── loop.md                   # ループ起動(親 issue 指定)。実行セッション= orchestrator
│   └── loop-status.md            # 進行状況・メトリクス表示
├── packs/
│   └── python/
│       ├── providers.yaml
│       └── normalizers/
└── profiles/
    ├── experiment.yaml
    └── development.yaml
```

orchestrator は agent としては存在しない。
Claude Code の subagent は既定で別の subagent を起動できないため([ROADMAP.md](ROADMAP.md) 検証結果)、orchestrator は `/tasuki:loop` を実行するメインセッションが務める。
また agent frontmatter の `model:` は起動ごとに変えられないため、ゲート別モデル(後述のレイヤードレート構造)は gate-reviewer のモデル固定3変種として実装する。

命名規約として、plugin 側の agent は `name:` フィールドに `tasuki-` 接頭辞を付けて名前空間を切る(衝突判定の対象はファイル名ではなく `name:`)。
コマンドは plugin 名で自動的に名前空間化される(`/tasuki:loop-init`)。

## 状態管理

ループの状態はすべて GitHub 上に置き、plugin はローカル状態ファイルを持たない。

| 状態 | 置き場所 |
|---|---|
| タスクの親子関係 | sub-issues |
| 着手順 | issue dependencies |
| ゲート判定と差し戻し理由 | issue コメント(監査ログを兼ねる) |
| ゲート通過状況 | ラベル(`gate:g2-passed` 等) |
| 成果物 | ブランチと PR |
| 判断原則の変更履歴 | 契約ファイルへの PR |

状態が GitHub に外部化されているため、クラッシュや中断のあともラベルと issue コメントから復元して途中再開できる(冪等性の要件はレビュー観点 #19)。

## ロール定義

| ロール | 責務 | コンテキスト | 対応ゲート |
|---|---|---|---|
| orchestrator | 依存グラフ構築、レイヤー実行、差し戻し回数管理、エスカレーション。**コードを書かない** | 全体(ただし要約のみ保持) | 全ゲートの呼び出し元 |
| decomposer | 親 issue →子 issue の分割案作成 | 親 issue のみ | G1 被検査者 |
| gate-reviewer | 契約照合、3値判定、質問の型付け。読み取り専用ツールのみ | 前工程出力+契約のみ(作業コンテキスト非共有) | G0〜G4 |
| worker | worktree 作成→実装/実験→ self-verify → PR 作成→報告→掃除。worker : worktree = 1 : 1 | 担当子 issue のみ | GM 被検査者 |
| verifier | 成功基準と打ち切り条件の判定(maker と別コンテキスト) | 実行結果+基準のみ | 内側ループの出口 |
| 人間 | 最終マージ、axis-question の承認、エスカレーション受け | — | 最終ゲート |

gate-reviewer が maker の作業コンテキストを共有しない点は要件である。
共有すると maker/checker 分離が崩れ、maker の思い込みを checker が引き継ぐ。

## Lead-Worker 型の実行構造

orchestrator が依存グラフからレイヤーを作り、レイヤー内は worker 並列、レイヤー間は直列で実行する。
レイヤー完了ごとに default branch を更新してから次レイヤーへ進む。
依存の循環はエラーとして検出し、報告して停止する。

deploy と release の分離(feature flag)により、未完成の機能を理由にレイヤー実行を止めない。

## レイヤードレート構造(モデル選択)

原則は、**最上位モデルはオーケストレーションに限定し、トークンの物量は worker レートで流す** ことにある。
Fable 5 が計画と委譲を行い、作業は下位レートの worker(Sonnet)へ委譲することで、消費トークンの大半を worker レートで課金させる。
個々のゲートのモデルは「頻度×誤判定の下流コスト」で決める。
誤 PASS はゲートより下流をすべて無駄にするが、誤 REJECT は前フェーズ1回の再実行で済み `max_iterations` で有界という非対称性がある。

| 層 | ロール | モデル | 根拠 |
|---|---|---|---|
| 統括 | orchestrator | Fable 5 | 極少トークン、最高判断。計画、依存グラフ、委譲、エスカレーション裁定のみ。**ゲート判定は兼ねない**(maker/checker 分離とレート戦略の両方が崩れるため) |
| 高レバレッジ判定 | G0 / G1 / G4 reviewer | Opus | 親 issue あたり1回程度の低頻度。誤 PASS の下流コスト最大 |
| 中頻度判定 | G3 reviewer / decomposer | Sonnet(G3 は Opus へ昇格可) | 意味検証だが毎反復発生 |
| 高頻度照合 | G2 reviewer | Haiku(Sonnet へ昇格可) | チェックリスト照合。門前払いが機械処理済 |
| 物量 | worker / verifier | Sonnet | トークンの大半。worker レート課金の主戦場 |

実装上、reviewer のモデルは gate-reviewer の3変種(`tasuki-gate-reviewer` = haiku、`-sonnet`、`-opus`)への振り分けで決まり、昇格は変種の切り替えである。
orchestrator のモデルはメインセッションのモデルそのものであり、plugin からは強制できない(`/tasuki:loop` の実行時に Fable 5 を選ぶことを推奨とする)。

### エスカレーション規則(非対称ルール)

1. verdict に `confidence: high | low` を必須化する。**low の PASS は破棄して `escalate_to` の上位モデルで再判定** する。low の REJECT はそのまま差し戻してよい(誤 REJECT は安いため)
2. 同一ゲートで差し戻しが2回連続した場合も上位モデルへ昇格する(小型モデルの判定基準自体のズレを検出)
3. エスカレーション連鎖の終点は `haiku → sonnet → opus → Fable 裁定 → 人間`。差し戻し上限超過時、Fable が状況を要約し「契約の不備 / タスクの筋の悪さ / モデル能力の限界」を切り分けてから triage inbox に渡す(人間の判断コスト削減)

v1 は `model_selection: static` とし、v2 で `bandit`(Thompson Sampling 等によるタスク複雑度ベースの動的選択)を予約する。
回帰 fixture([OPERATIONS.md](OPERATIONS.md))に判定モデルを記録しておくことで、人間の正解ラベルがそのまま bandit の報酬データになる。
