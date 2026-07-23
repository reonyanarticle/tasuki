# tasuki(襷)仕様書 v0.9

**tasuki** は、AI エージェント間の襷(タスク・契約)の受け渡しを中継所(ゲート)で検めながら、GitHub issue を自走で完走させる Claude Code plugin。名前は駅伝の襷から: 区間=フェーズ、走者= agent、中継所=ゲート、襷=契約、繰り上げスタート=打ち切り条件、往路・復路=降りるゲート・昇るゲート。

> **実装者へ**: 実装順は §14(段階導入)、成果物一覧は §3.2、着手前に必ず §16(実装時検証事項)を公式ドキュメントで確認すること。

参照した先行例: Ralph Wiggum ループ(状態のファイル外部化・毎サイクル新規コンテキスト・completion promise+反復上限)、OpenHands(追記専用イベントログ・サンドボックス実行・StuckDetector)、Claude Code `/goal`(別モデルによる停止判定)、C3/claude-code-conductor(餌ファイル契約・門前払い・質問の宛先設計)、Findy Library(コンテキスト境界での役割分割・Lead-Worker・タスク分割条件)。

Claude Code plugin として、GitHub issue 駆動の自律ループ(実装・検証)に「抽象度ゲート」を組み込むフレームワーク。検証(実験)と開発の両方で使える汎用構成とし、まず Python を対象に実装する。

---

## 1. 目的・背景

具体と抽象の往復では、各つなぎ目で「この出力は、受け手が追加の解釈なしに受け取れる抽象度か?」の検証が必要になる。抽象度は相対的であり、判定基準は常に受け手基準で決まる。

仕事の受け渡しをリレーのバトンパスと見ると、渡し手の「引き渡し位置」と受け手の「待ち位置」の組み合わせで4パターンが生じ、成立するのは位置が一致する2パターンのみ。ここから、ゲートの判定は絶対基準ではなく **受け手が宣言した待ち位置との照合** であり、判定結果は3値になる。

| 判定 | バトンパターン | 意味 |
|---|---|---|
| `PASS` | 位置一致 | 引き渡し位置=待ち位置 |
| `TOO_ABSTRACT` | バトンが落ちる | 曖昧語残り・受け入れ条件なし等 |
| `TOO_CONCRETE` | 受け手を追い抜く | 実装方式の過剰指定・生ログのままの報告等 |

AI が実装→レビューを自律的に回すループでは、人間がズレを都度是正できないため、ズレ検知を仕組み(=ゲート)として各フェーズのつなぎ目に埋め込む。ループの基本部品は、スケジュール実行(automations)・worktree 分離・skills・plugins/connectors・subagents の5つと、会話の外に置く記憶であり、本 plugin では **記憶=GitHub issue** とする。

## 2. スコープ

### v1 に含む

| 項目 | 内容 |
|---|---|
| ゲート機構 | abstraction ゲート(G0〜G4)+ mechanical ゲート(CI 実行) |
| ロール | orchestrator / decomposer / gate-reviewer(降・昇) / worker / verifier |
| 契約 | プロファイル YAML(フェーズ・待ち位置・ゲート・予算) |
| ブートストラップ | `/loop-init`(言語検出→pack 選択→契約・テンプレ・CI 生成) |
| CI | plugin が生成する前提。既存 CI は前提にしない |
| 質問ルーティング | task-question / axis-question の型付けと宛先分離 |
| 橋渡し | 外部 subagent・skill・検査ツールを接続するインターフェース |
| language pack | python(uv / ruff / mypy / pytest) |

### v1 に含まない

- python 以外の language pack(インターフェースだけ切っておく)
- タスク複雑度によるモデル自動選択(将来のコスト最適化候補)
- worker セッション内の常駐セキュリティガード(security-guidance 等はユーザー任意導入)
- 複数リポジトリ横断のループ

## 3. アーキテクチャ

### 3.1 三層構造

```
core(言語非依存)
├── ゲート分類・verdict スキーマ・契約スキーマ
├── orchestrator ロジック(レイヤー実行・差し戻し管理・エスカレーション)
├── 質問ルーティング
├── findings 判定器(SARIF / JUnit XML のみを読む)
└── テンプレ生成器(契約 → issue テンプレ / CI workflow)

language pack(v1: python)
├── providers.yaml(lint / typecheck / test / security のコマンド定義)
├── 言語検出条件(pyproject.toml の存在)
└── normalizer(SARIF 非対応ツールの出力変換)

repo override(プロジェクト固有)
└── コマンド・閾値・待ち位置定義の上書きのみ
```

言語に固有な情報は pack の中にのみ現れる。2言語目は pack を1枚追加するだけで対応する。

### 3.2 plugin ディレクトリ構成

```
tasuki/
├── .claude-plugin/plugin.json    # name: tasuki
├── skills/
│   ├── gate-review/SKILL.md      # ゲート判定手順(3値判定・差し戻し文の書式)
│   ├── baton-contract/SKILL.md   # 契約(待ち位置)の書き方・読み方
│   └── loop-report/SKILL.md      # レポート作成手順(対応表必須)
├── agents/
│   ├── orchestrator.md
│   ├── decomposer.md
│   ├── gate-reviewer.md          # コンテキスト非共有・読み取り専用
│   ├── worker.md                 # isolation: worktree
│   └── verifier.md
├── commands/
│   ├── loop-init.md              # ブートストラップ
│   ├── loop.md                   # ループ起動(親 issue 指定)
│   └── loop-status.md            # 進行状況・メトリクス表示
├── packs/
│   └── python/
│       ├── providers.yaml
│       └── normalizers/
└── profiles/
    ├── experiment.yaml
    └── development.yaml
```

### 3.3 状態管理

ループの状態はすべて GitHub 上に置き、plugin はローカル状態ファイルを持たない。

| 状態 | 置き場所 |
|---|---|
| タスクの親子関係 | sub-issues |
| 着手順 | issue dependencies |
| ゲート判定・差し戻し理由 | issue コメント(監査ログを兼ねる) |
| ゲート通過状況 | ラベル(`gate:g2-passed` 等) |
| 成果物 | ブランチ・PR |
| 判断原則の変更履歴 | 契約ファイルへの PR |

## 4. ゲート体系

### 4.1 ゲート種別

| kind | verdict | 判定主体 |
|---|---|---|
| `abstraction` | `PASS` / `TOO_ABSTRACT` / `TOO_CONCRETE` | gate-reviewer(LLM、独立コンテキスト) |
| `mechanical` | `PASS` / `FAIL` + findings[severity] | CI(生成された workflow) |

abstraction ゲートは二段構成とする: (1) 門前払い — テンプレ必須欄の空・欠落を機械チェック(LLM 不要、ループ入口で品質担保)、(2) 契約照合 — gate-reviewer による3値判定。

### 4.2 ゲートカタログ

| ID | 名称 | 位置 | kind | 主な検査 |
|---|---|---|---|---|
| G0 | 受理ゲート | 親 issue 起票時 | abstraction | 課題価値とコスト予算の釣り合い、実現可能性の前提 |
| G1 | 分割ゲート | 親→子分割時 | abstraction | 良いタスクの4条件、依存の非循環、待ち位置整合 |
| G2 | 着手ゲート | 子 issue →実装前 | abstraction | 要件充足性(受け入れ条件・成功基準・打ち切り条件・実験条件)、予算欄 |
| GM | 形式ゲート | PR 作成時(CI) | mechanical | lint / 型 / テスト / セキュリティ |
| G3 | 成果ゲート | レポート→ issue | abstraction | 要件⇔結果の対応表(N対1)、生ログ排除 |
| G4 | 統合ゲート | 全子完了→親 | abstraction | 子成果の親要件へのロールアップ、孤児要件なし |
| — | 最終ゲート | マージ | 人間 | 要件適合の最終判断。**マージは常に人間が実行** |

G1 の「良いタスクの4条件」: 単独でマージして壊れない / テストを同梱 / 単独で revert できる / 一読で理解できる。加えて **常に分ける** 組み合わせを差し戻し基準に含める: リファクタリングと機能追加、ライブラリ更新と機能開発、性能改善と機能開発、データ移行と機能開発、feature flag の各段階(add → enable → remove)、相互に依存しない機能同士。deploy と release の分離(feature flag)により、未完成の機能を理由にレイヤー実行を止めない。

### 4.3 verdict スキーマ

```json
{
  "gate": "g2",
  "verdict": "TOO_ABSTRACT",
  "confidence": "high",
  "model": "haiku",
  "reasons": ["受け入れ条件が『使いやすく』のまま", "打ち切り条件が未定義"],
  "return_to": "decomposer | worker | reporter",
  "questions": [
    {"type": "task-question", "to": "issue-author", "text": "..."},
    {"type": "axis-question", "to": "contract-pr", "text": "..."}
  ]
}
```

差し戻し先は2種類を区別する: 内容の不足(前フェーズへ)と、書き方の不足(同フェーズの再出力)。

**差し戻し再実行は必ず新規セッションで行う。** 前回セッションを継続せず、渡すのは契約+差し戻し verdict のみ(コンテキスト衛生、観点 #16)。継続セッションでの再試行はコンテキスト腐敗を再導入し、同じ誤りに固執する原因になる。

### 4.4 モデル選択: レイヤードレート構造

原則: **最上位モデルはオーケストレーションに限定し、トークンの物量は worker レートで流す。** Fable 5 が計画・委譲を行い、作業は下位レートの worker(Sonnet)へ委譲することで、消費トークンの大半を worker レートで課金させる。個々のゲートのモデルは「頻度×誤判定の下流コスト」で決める(誤 PASS はゲートより下流をすべて無駄にするが、誤 REJECT は前フェーズ1回の再実行で済み `max_iterations` で有界という非対称性)。

| 層 | ロール | モデル | 根拠 |
|---|---|---|---|
| 統括 | orchestrator | Fable 5 | 極少トークン・最高判断。計画・依存グラフ・委譲・エスカレーション裁定のみ。**ゲート判定は兼ねない**(maker/checker 分離とレート戦略の両方が崩れるため) |
| 高レバレッジ判定 | G0 / G1 / G4 reviewer | Opus | 親 issue あたり1回程度の低頻度。誤 PASS の下流コスト最大 |
| 中頻度判定 | G3 reviewer / decomposer | Sonnet(G3 は Opus へ昇格可) | 意味検証だが毎反復発生 |
| 高頻度照合 | G2 reviewer | Haiku(Sonnet へ昇格可) | チェックリスト照合。門前払いが機械処理済 |
| 物量 | worker / verifier | Sonnet | トークンの大半。worker レート課金の主戦場 |

エスカレーション規則(非対称ルール):

1. verdict に `confidence: high | low` を必須化。**low の PASS は破棄して `escalate_to` の上位モデルで再判定**する。low の REJECT はそのまま差し戻してよい(誤 REJECT は安いため)
2. 同一ゲートで差し戻しが2回連続した場合も上位モデルへ昇格(小型モデルの判定基準自体のズレを検出)
3. エスカレーション連鎖の終点: `haiku → sonnet → opus → Fable 裁定 → 人間`。差し戻し上限超過時、Fable が状況を要約し「契約の不備 / タスクの筋の悪さ / モデル能力の限界」を切り分けてから triage inbox に渡す(人間の判断コスト削減)

`model_selection: static` を v1 とし、v2 で `bandit`(Thompson Sampling 等によるタスク複雑度ベースの動的選択)を予約する。§13 の回帰 fixture に判定モデルを記録しておくことで、人間の正解ラベルがそのまま bandit の報酬データになる。

## 5. ロール定義

| ロール | 責務 | コンテキスト | 対応ゲート |
|---|---|---|---|
| orchestrator | 依存グラフ構築・レイヤー実行・差し戻し回数管理・エスカレーション。**コードを書かない** | 全体(ただし要約のみ保持) | 全ゲートの呼び出し元 |
| decomposer | 親 issue →子 issue の分割案作成 | 親 issue のみ | G1 被検査者 |
| gate-reviewer | 契約照合・3値判定・質問の型付け。読み取り専用ツールのみ | 前工程出力+契約のみ(作業コンテキスト非共有) | G0〜G4 |
| worker | worktree 作成→実装/実験→ self-verify → PR 作成→報告→掃除。worker : worktree = 1 : 1 | 担当子 issue のみ | GM 被検査者 |
| verifier | 成功基準・打ち切り条件の判定(maker と別コンテキスト) | 実行結果+基準のみ | 内側ループの出口 |
| 人間 | 最終マージ、axis-question の承認、エスカレーション受け | — | 最終ゲート |

役割分割の原則: 作業の種類ではなく **コンテキスト境界** で切る。フェーズ間の引き継ぎ物は「issue 本文だけで自己完結する契約」に強制されるため、境界での転送は契約のみになる。抽象度ゲートはコンテキスト境界を作る装置を兼ねる。

実行構造は Lead-Worker 型: orchestrator が依存グラフからレイヤーを作り、レイヤー内は worker 並列、レイヤー間は直列。レイヤー完了ごとに default branch を更新してから次レイヤーへ進む。依存の循環はエラーとして検出・報告・停止。

## 6. レビュー観点カタログ

各観点がどのゲートで・何を・どう検査するかの一覧。契約 YAML とテンプレ必須欄はこの表から導出する。

| # | 観点 | 問い | ゲート | 不合格時 |
|---|---|---|---|---|
| 1 | 要件充足性 | 受け入れ条件・成功基準が揃い、曖昧語が残っていないか | G2 | 差し戻し or task-question |
| 2 | コスト妥当性 | 課題の価値に対し予算(最大反復数・実行コスト・想定時間)が釣り合うか | G0 | 人間へエスカレーション |
| 3 | 実現可能性・前提 | データ・環境・権限・依存ライブラリが揃っているか(実験ならデータ入手性) | G2 | task-question |
| 4 | 分割妥当性 | 4条件を満たすか、依存が非循環か | G1 | decomposer へ差し戻し |
| 5 | 抽象度整合(降り) | 引き渡し位置=待ち位置か | G1, G2 | `TOO_ABSTRACT` / `TOO_CONCRETE` |
| 6 | 抽象度整合(昇り) | 各成果が元要件のどれに対応するか明示されているか(N対1) | G3, G4 | 同上 |
| 7 | 形式品質 | lint・型・テスト・セキュリティが閾値を満たすか | GM | worker へ差し戻し |
| 8 | リスク・可逆性 | 影響範囲は把握されているか、revert 可能か、破壊的変更は明示されているか | G1, PR 本文 | 人間の判断材料として提示 |
| 9 | 再現性 | 実験: seed・環境固定(lockfile)・データ版数の記録。開発: ビルド再現 | G2 必須欄+G3 検証 | 差し戻し |
| 10 | セキュリティ・権限 | 質問の型と宛先が守られているか、原則変更が承認を経ているか | 常時 | axis-question 昇格 |
| 11 | 観測性 | 判定が issue コメントに残り、メトリクスが収集できるか | 機構要件 | — |
| 12 | 知識還流 | ループの学びが契約・skill に還流したか | ループ終端(任意) | — |
| 13 | 人間の関与 | 最終マージが人間か、差し戻し上限のエスカレーションが機能するか、成果物を人間が読んだか | 最終ゲート | — |
| 14 | 停滞検知 | 同一アクション反復・ピンポンパターン・進捗なきモノローグに陥っていないか | 実行中(watchdog) | 停止して人間へ報告 |
| 15 | 実行環境の隔離・権限最小化 | worker のツール allowlist は最小か、secrets は CI のみか、ネットワーク・書き込み範囲は制限されているか | 機構要件 | — |
| 16 | コンテキスト衛生 | 各実行が新規セッションで始まり、引き継ぎが契約のみに限定されているか。コンテキスト予算は守られているか | 機構要件 | — |
| 17 | フィードバック速度 | ゲートのレイテンシは予算内か(PR ゲート CI は5〜10分以内、門前払いは秒オーダー) | 機構要件 | — |
| 18 | テストの信頼性 | worker が書いたテストは「壊れたら落ちる」か。既存テストの削除・skip・アサーション弱化がないか。期待値は仕様由来か | GM(機械検知)+ G3(レビュー観点) | worker へ差し戻し |
| 19 | 冪等性・再開可能性 | クラッシュ・中断後にラベルと issue コメントから状態復元して途中再開できるか。全操作は冪等か(再実行で二重コメント・二重 PR を作らない) | 機構要件 | — |
| 20 | 並行整合性 | issue 割り当ての排他(assignee / ラベルロック)、orchestrator 二重起動の防止、レイヤー内のマージ順規約 | 機構要件 | — |
| 21 | 目的漂流の検知 | 反復のたびに「今の作業は元の issue 要件に向かっているか」を軽量チェック | 内側ループ(verifier に付随) | worker へ指摘・軌道修正 |
| 22 | 評価データの分離(実験) | 内側ループの反復は dev セットのみ、テストセット評価は最終報告の1回だけか | G2 必須欄+ G3 検証 | 差し戻し |
| 23 | 出力衛生 | レポート・issue コメントに機密データ・個人情報・secrets が混入していないか(記憶= GitHub なので混入は永続化する) | G3 + ログ経路のマスキング | 差し戻し |
| 24 | スループット管理(WIP 制限) | 仕掛り(未レビュー PR・未承認 axis-question)が制約=人間レビュー帯域の閾値を超えていないか | orchestrator(起動制御) | 新規 worker 起動を停止 |
| 25 | ゲートの発振検知 | 同一箇所で TOO_ABSTRACT ⇄ TOO_CONCRETE が交互に出ていないか | gate-reviewer 履歴 | 契約不備として axis-question 昇格 |

補足:

- **#2 コスト妥当性** — 子 issue テンプレに予算欄(`max_iterations` / 想定実行コスト)を必須化。ループの token コストは運用形態で大きく変動するため、予算超過は自動でエスカレーションする。
- **#8 リスク・可逆性** — ゲートが機械判定するのは「明示されているか」まで。リスクを取るかどうかの判断は人間に残す(機械検証できるものは AI へ、文脈依存の判断は人間へ、の責任境界)。
- **#12 知識還流** — 差し戻しが繰り返された原因が契約の不備なら axis-question として契約 PR に、手順の不備なら skill 更新提案として出力する。エージェントは毎セッション白紙で始まるため、学びを外部化しないとループが毎周同じ穴に落ちる。
- **#14 停滞検知** — 反復回数上限とは直交する停止装置。同一コマンドの反復、2つの action-observation ペアの交互出現、進捗のない連続メッセージをパターン検知する。ただし実験プロファイルでは学習・推論ジョブの「待ち」を「停滞」と誤検知しないこと: 長時間ジョブはジョブ状態のポーリング(ハートビート)で待ちと判定し、watchdog の対象から除外する。
- **#15 実行環境の隔離** — 標準は権限最小化のみとする: agent ごとのツール allowlist(gate-reviewer は読み取り専用、worker は担当 worktree 内の書き込みのみ)、secrets(API キー等)は CI 環境にのみ置き worker セッションには渡さない。コンテナ等のサンドボックス実行は必須にせず、worker 単位の契約オプション `sandbox: none | container`(デフォルト none)とし、信頼できない外部入力やサードパーティコードを扱うタスクでのみ有効化する。
- **#16 コンテキスト衛生** — ループが長く回るほどコンテキスト腐敗が品質を落とす。フェーズ実行・差し戻し再実行・ゲート判定はすべて新規セッションで始め、引き継ぎは契約(issue 本文+verdict)のみとする。状態が issue に外部化されているため、セッションを捨てても失うものはない。
- **#17 フィードバック速度** — ループは反復×ゲート数だけ待ち時間を払う。生成する CI workflow には依存キャッシュ・テスト並列化・paths-ignore を最初から焼き込み、PR ゲートを5〜10分以内に保つ。CI 最適化は計測ループとして扱う(最大の時間スライスを特定→1つ変更→差分検証)。
- **#18 テストの信頼性(検証器の検証)** — verifier の判定はテストの質に上限を規定される。AI 生成テストは「守ること」より「緑になること」に最適化しがちで、テスト対象ロジック自体のモック、実装出力の期待値化、断片的アサーションが典型的な false negative 源。対策: (1) GM に diff ベースの機械検知(既存テストの削除・skip・アサーション弱化)、(2) G3 レビュー観点に「期待値は仕様(issue の受け入れ条件)由来か、実装出力由来か」を追加、(3) テストは実装と同一 PR に同梱(G1 の4条件と整合)。GM ではあわせて flaky テストの検知(再実行で結果が変わるテストの隔離)と依存追加の検知(lockfile diff)も行う。
- **#19 / #20 冪等性・並行整合性** — 本番のループはデモと違い、クラッシュは書き込みの途中で起き、リトライは半分だけ着地したステップを再実行する。状態機械(ラベル遷移)は「読み→判定→書き」を再入可能に設計し、コメント・PR 作成は既存有無を確認してから行う。orchestrator は concurrency group(同一親 issue につき1実行)で排他し、worker への issue 割り当ては assignee 設定を CAS 的に扱う。
- **#21 目的漂流** — 差し戻し対応を繰り返すうち、いつのまにか別の問題を解き始める失敗。局所的には各応答が一貫して見えるため気づきにくい。verifier の判定に「成功基準への適合」だけでなく「元要件との方向一致」の軽量チェックを含め、漂流を検知したら G2 相当の再照合に戻す。
- **#22 評価データの分離** — 「成功基準を満たすまで反復」は評価セットへの多重比較そのもの。反復回数分だけ評価セットに過学習するため、experiment 契約の必須欄に dev / test 分離を入れ、テストセットでの評価は最終報告時の1回に制限する。G3 はレポートの数字がどちらのセット由来かの明記を要求する。
- **#23 出力衛生** — 状態を GitHub に置く設計の裏面として、issue コメント・レポートへの機密混入は監査ログとして永続化する。レポートテンプレに「本文に掲載可能なデータの規約」(集計値のみ・生サンプル禁止等)を持たせ、生データはアクセス制御されたリンクのみとする。secrets は CI 環境限定(#15)に加え、ログ・コメント経路でのマスキングを機構要件とする。
- **#24 スループット管理(TOC / DBR)** — システム全体のスループットは制約(ボトルネック)が決める。本ループの制約は通常、人間レビュー帯域。制約をドラムとし、仕掛り上限(バッファ)を契約に持たせ、超過したら orchestrator が新規 worker 起動を止める(ロープ)。非制約工程(worker 並列度)をいくら上げても、未レビュー PR が積み上がるだけでスループットは上がらない。§13 の改善も TOC の5集中ステップに従う: 制約を特定→制約を徹底活用→他工程を制約に従属→制約を強化→繰り返す。
- **#25 ゲートの発振(制御工学)** — 同一箇所での TOO_ABSTRACT ⇄ TOO_CONCRETE の交互出現は、修正指示が過大(ループゲイン過大)か、契約の `waiting_level` 自体が曖昧で目標値が定まっていないことを示す。worker への再差し戻しでは解決しないため、契約不備として axis-question に昇格する。#14 停滞検知(同じ場所で止まる)と対をなす「行き過ぎて往復する」側の検知。差し戻し verdict には前回 verdict との方向比較を含める。なお #17(フィードバック速度)は効率要件ではなく安定性要件でもある: 検証の遅延はフィードバック系を不安定化させる。

## 7. 契約スキーマ(プロファイル YAML)

```yaml
# profiles/development.yaml
profile: development
budgets:
  max_iterations_per_gate: 3      # 超過で人間にエスカレーション
  max_inner_loop: 5               # verifier の打ち切り上限デフォルト
  wip_limit_prs: 3                # 未レビュー PR の上限(#24)。超過で新規 worker 起動を停止

models:                           # レイヤードレート構造(§4.4)
  orchestrator: fable
  decomposer: sonnet
  worker: sonnet
  verifier: sonnet
  escalation_arbiter: fable       # 差し戻し上限超過時の裁定

phases:
  - name: requirements            # 親 issue
    hands_off:
      to: decomposition
  - name: decomposition
    receives:
      from: requirements
      waiting_level: "背景・目的・価値・予算が記載され、解き方は未指定"
      too_abstract_signals: ["価値の記載なし", "予算欄が空"]
      too_concrete_signals: ["子タスクの実装方式まで指定"]
    hands_off:
      to: implementation
  - name: implementation
    receives:
      from: decomposition
      waiting_level: "受け入れ条件つきで単独マージ可能な単位。実装方式は未指定"
      too_abstract_signals: ["曖昧語(適切に・柔軟に等)", "受け入れ条件の欠落", "打ち切り条件の欠落"]
      too_concrete_signals: ["特定ライブラリ・実装方式の指定"]
    hands_off:
      to: report
      exit_criteria_required: true
  - name: report
    receives:
      from: implementation
      waiting_level: "要件⇔結果の対応表と結論。生データは添付リンクのみ"
      too_abstract_signals: ["対応表なし", "結論なし"]
      too_concrete_signals: ["生ログ・生データの本文貼り付け"]

gates:
  - id: g0
    kind: abstraction
    reviewer: gate-reviewer       # 外部 subagent 名に差し替え可能
    model: opus                   # 低頻度・高レバレッジ
  - id: g1
    kind: abstraction
    reviewer: gate-reviewer
    model: opus
  - id: g2
    kind: abstraction
    reviewer: gate-reviewer
    model: haiku                  # 高頻度・照合型
    escalate_to: sonnet           # low-confidence PASS / 差し戻し2連続で昇格
    preflight: template-fields    # 門前払い(機械チェック)
  - id: gm-lint
    kind: mechanical
    provider: lint                # pack の providers.yaml を参照
    blocking_threshold: error     # SARIF level
  - id: gm-typecheck
    kind: mechanical
    provider: typecheck
    blocking_threshold: error
  - id: gm-test
    kind: mechanical
    provider: test                # JUnit XML: failures == 0
  - id: gm-security
    kind: mechanical
    provider: security-review
    blocking_threshold: high
  - id: g3
    kind: abstraction
    reviewer: gate-reviewer
    model: sonnet
    escalate_to: opus
  - id: g4
    kind: abstraction
    reviewer: gate-reviewer
    model: opus

model_selection: static           # v2 で bandit(タスク複雑度ベースの動的選択)を予約

question_routing:
  task-question: issue-comment    # 起票者へ。回答で issue 本文を更新
  axis-question: contract-pr      # 契約ファイル変更 PR として起票。人間が承認
```

experiment.yaml との差分は phases の名称(課題定義→実験計画→実行→分析→報告)、`exit_criteria_required` の中身(評価指標・データセット・seed)、G2 必須欄(実験条件・データ版数)のみ。ゲート機構・verdict・ルーティングは共通。

```yaml
# packs/python/providers.yaml
detect: ["pyproject.toml"]
providers:
  lint:      "uv run ruff check --output-format sarif ."
  typecheck: "uv run mypy . --junit-xml mypy.xml"   # normalizer で SARIF 化
  test:      "uv run pytest --junitxml=junit.xml"
  security:  "claude-code-security-review"           # GitHub Action(§9)
```

## 8. issue テンプレート仕様

契約 YAML から `/loop-init` が生成する(単一ソース原則: 契約とテンプレの二重管理をしない)。

| テンプレ | 必須欄 |
|---|---|
| 親 issue | 背景 / 目的 / 価値 / 予算(コスト上限) / 完了の定義 |
| 子 issue | 対応する親要件 / 目的 / 受け入れ条件 / 成功基準 / 打ち切り条件 / 予算(max_iterations) / 実験条件(experiment のみ: データ・環境・パラメータ・seed) |
| レポート | 要件 ID ⇔結果の対応表 / 結論 / 再現手順(コマンド・環境) / 生データへのリンク |
| PR 本文 | 概要 / 変更点 / 影響範囲・revert 可否 / 対応 issue / 検証方法 |

必須欄の空チェックが G2 の門前払いに直結する。

## 9. `/loop-init`(ブートストラップ)と CI 生成

CI は plugin が **作ることを前提** とする。`/loop-init` の手順:

1. 言語検出 → language pack 選択(`pyproject.toml` → python)
2. **プロジェクト資産の棚卸し**: `.claude/agents/`・`.claude/skills/`・CLAUDE.md・導入済み plugin を走査し、ゲート/provider への接続候補を提案(§11.5)。ループ系 plugin の併用を検出したら警告
3. 契約プロファイル雛形の配置(experiment / development を選択)+ repo override(`.claude/loop/`)
4. issue / PR テンプレート生成(§8)。worker のコミット規約は Conventional Commits(`<type>: <summary>`)とし、PR は draft で開いて方向性を早期確認、GM+G3 通過で ready 化する
5. **CI workflow 生成**: providers.yaml から `loop-gates.yml` を生成
   - lint / typecheck job: SARIF 出力をアップロード
   - test job: JUnit XML 出力+**テスト改変検知**(既存テストの削除・skip・アサーション弱化の diff チェック、観点 #18)
   - security job: `anthropics/claude-code-security-review` Action(PR コメント形式)
   - 依存キャッシュ・テスト並列化・paths-ignore をデフォルトで焼き込み、PR ゲートを5〜10分以内に保つ(観点 #17)
   - 通知は失敗だけでなく成功も送る(沈黙が「成功」か「通知経路の故障」か区別できないため)
6. ラベル作成(`gate:*` 系)、sub-issues / issue dependencies の利用確認
7. `max_iterations` 等バジェットのデフォルト設定

providers.yaml が単一ソースであり、CI workflow はそこからの射影。worker はプッシュ前に同じコマンドをローカル実行できる(高速フィードバック)が、**ゲートとして正となるのは CI の判定**。orchestrator は `gh api` で check-runs を読み、GM の verdict に変換する。

制約事項: security-review Action はプロンプトインジェクション対策が施されておらず、信頼できる PR のみを対象とする。本ループの PR は自リポジトリの worker が生成するため v1 では許容するが、外部コントリビューションを受けるリポジトリへの転用時は要再検討。

## 10. 質問ルーティング

質問には寿命があり、寿命が宛先を決める。

| 型 | 寿命 | 例 | 宛先 | 動作 |
|---|---|---|---|---|
| `task-question` | タスクと共に終わる | 再現手順・仕様の細部 | issue 起票者 | issue コメントで質問し、回答を issue 本文に反映して再開 |
| `axis-question` | タスク後も生きる | 判断原則・設計方針・待ち位置の定義変更 | 契約ファイル | 契約 YAML への変更 PR として起票。人間の承認後に反映 |

起票者の回答でプロジェクトの原則が書き換わることは権限昇格であり、一人運用でも axis-question を issue コメントで即答させない。原則の変更は必ずバージョン管理された契約 PR を経由する。軸の欠落(待ち位置が未定義)はブロッキング、原則の改善提案は非ブロッキング(進めつつ PR を非同期起票)。

## 11. 橋渡しインターフェース

plugin の成立条件は、外部の subagent・skill・検査ツールを接続できること。接続点は4つ。

| 接続点 | インターフェース | 例 |
|---|---|---|
| gate reviewer 差し替え | 契約 YAML の `reviewer:` に subagent 名を指定。入力: 前工程出力+契約 / 出力: verdict JSON(§4.3) | 外部コレクションのレビュアー系 agent を G2 に割り当て |
| worker 差し替え | 入力: 子 issue 本文のみ / 義務: worktree 作成→実装→ self-verify → PR →報告→掃除 / 出力: PR URL +レポート | 特化 worker(データ処理専用等)への置換 |
| mechanical provider 追加 | コマンド+ SARIF または JUnit XML 出力(非対応ツールは pack の normalizer を挟む) | 任意の linter・スキャナ |
| skill 参照 | ゲート判定基準は skill として外出し可能。worker は対象リポジトリの skill / CLAUDE.md を通常通り参照 | プロジェクト固有規約の注入 |

方針は「ペルソナは薄く、契約を厚く」。外部 subagent の人格プロンプトには依存せず、入出力契約(verdict JSON / worker 義務)への適合のみを要求する。

### 11.5 プロジェクト直下アセットとの統合

対象リポジトリに既にある `.claude/agents/`・`.claude/skills/`・CLAUDE.md・導入済み plugin との組み合わせを、次の4ルールで扱う。

1. **発見**: `/loop-init` がプロジェクト直下と導入済み plugin を棚卸しし、接続候補を提案する。レビュアー系 agent → ゲート reviewer / GM への割り当て提案、コマンド提供 plugin(`/security-review` 等)→ provider 登録提案。採用結果は契約 YAML に書き込まれる。
2. **優先順位**: 名前解決は project > repo override(`.claude/loop/`)> language pack > plugin デフォルト。Claude Code のネイティブな衝突解決(プロジェクト定義がグローバルを上書き)に揃える。plugin 側の agent は `name:` フィールドに `tasuki-` 接頭辞を付けて名前空間を切り(ファイル名ではなく `name:` が衝突判定の対象)、プロジェクトの既存 agent と衝突させない。コマンドは plugin 名で自動的に名前空間化される(`/tasuki:loop-init`)。
3. **コンテキスト境界**: worker はプロジェクトの CLAUDE.md・skill を意図的に継承する(プロジェクト規約=ガードレール)。gate-reviewer が継承するのは CLAUDE.md(共有知識)までで、maker の作業コンテキストは渡さない。プロジェクト skill をゲート判定基準に加えたい場合は、契約 YAML の `criteria_skills:` に skill 名を列挙して gate-reviewer に参照させる。
4. **非互換の明記**: Stop hook でセッションを回すループ系 plugin(ralph-wiggum 等)との併用は二重ループになるため禁止。`/loop-init` の棚卸しで検出したら警告する。編集時 lint 等の一般 hooks は worker セッション内で通常どおり発火してよい(干渉しない)。

## 12. コスト管理・エスカレーション

| 機構 | 内容 |
|---|---|
| ゲート差し戻し上限 | `max_iterations_per_gate` 超過で人間へエスカレーション(ズレたまま暴走する事故の抑止) |
| 内側ループ打ち切り | verifier が成功基準・打ち切り条件で判定。基準は G2 で事前定義済であること(自己採点の防止) |
| issue 予算 | 子 issue の予算欄超過で停止・報告 |
| triage inbox | エスカレーション・axis-question 承認待ちを人間向けに一覧化(`/loop-status`) |
| watchdog | 反復回数と直交する第二の停止装置。wall-clock・token 消費の上限超過で停止・報告(反復1回が異常に長い/高い事故を検出) |
| 停滞検知 | 反復・ピンポン・モノローグのパターン検知(観点 #14)。実験ジョブの「待ち」はハートビートで除外 |

役割の整理: **verifier の成功基準・打ち切り条件がブレーキ、`max_iterations`・watchdog はシートベルト**。上限はループが既に浪費した後に発火するバックストップであり、停止条件の本体は G2 で事前定義された基準の側にある。上限発火が常態化しているなら、直すべきは上限値ではなく契約。

## 13. 観測性・メトリクス

ゲート判定はすべて issue コメントに構造化して残るため、そこから収集する。

| メトリクス | 用途 |
|---|---|
| ゲート別差し戻し率・差し戻し理由分布 | too_*_signals の精度改善(契約のチューニング材料) |
| 差し戻し→通過までの反復回数 | バジェットのデフォルト調整 |
| サイクルタイム(子 issue 起票→マージ) | ループ全体のボトルネック特定。**加工時間(worker・ゲート実行)と待ち時間(キュー滞留・人間待ち)に分解**して計測する(IE の滞留分析)。改善は TOC の5集中ステップに従い、制約となっている工程だけに投資する |
| axis-question 発生数 | 契約の成熟度指標(減っていけば原則が安定) |
| モデル別トークン消費の内訳 | レート戦略の KPI。**worker レート(Sonnet)比率** が主指標。Fable+Opus 比率の膨張はエスカレーション多発=契約(too_*_signals)の精度低下シグナルであり、そのまま契約チューニングの入力になる |

これらは「ループを改善するメタループ」の入力であり、v1 では `/loop-status` での表示までをスコープとする。

**ゲート判定の回帰テスト**: 実運用で得た判定例(入力と人間が正とした verdict)を fixture として蓄積し、gate-review skill や too_*_signals を変更した際に過去事例で再判定して精度が落ちていないか検証する。誤差し戻し(false reject)と見逃し(false pass)の両方を人間ラベルで拾う。fixture には判定に使ったモデルも記録する(§4.4 の bandit 化に向けた報酬データを兼ねる)。フレームワーク自身にも検証ループを適用する、という自己言及的な要件。

## 14. 導入戦略

抽象と具体の往復にはコストがあり、ゲート全部入りで始めるとオーバーヘッドでループ自体が回らない。IE(工程分析)の原則——**検査・運搬・停滞は付加価値を生まない**——に従い、ゲート(=検査)は必要最小限から始めて差し戻しの質で増減を判断する。段階導入を標準とする。

1. **フェーズ1**: G2(着手ゲート)のみ+ GM。門前払いと契約照合の効果を差し戻しの質で確認する

   **フェーズ1の受け入れ条件(完了の定義)**:
   - `/tasuki:loop-init` が素の Python リポジトリ(pyproject.toml のみ)に対して、契約雛形・issue/PR テンプレ・`loop-gates.yml`・ラベルを生成できる
   - 必須欄が空の子 issue が門前払いで差し戻される(LLM 呼び出しなし)
   - 手書き fixture 5件に対し、gate-reviewer(haiku)の判定が人間の正解ラベルと5件中4件以上一致する
   - 差し戻し verdict が issue コメントに §4.3 スキーマの JSON で記録される
   - G2 通過の子 issue を worker が worktree 上で実装し、draft PR 作成・GM(CI)実行まで到達する
   - 差し戻し2連続で sonnet へのエスカレーションが発火する

2. **フェーズ2**: G3(成果ゲート)を追加し、昇る側の対応表検証を回す
3. **フェーズ3**: G0 / G1 / G4 とレイヤー並列実行を有効化し、フルループへ

**初期 fixture の手書き(必須)**: 契約の `waiting_level` や `too_*_signals` は自然言語の抽象であり、書いた人間と読む gate-reviewer の「目盛り」は最初必ずズレている。抽象的な基準は具体例とセットでないと伝わらないため、`/loop-init` の推奨手順として、運用開始前に判定例 fixture を5件程度手書きする(「この子 issue は PASS のはず」「これは TOO_ABSTRACT のはず」)。これは回帰テスト(§13)の初期データであると同時に、契約作成者とレビュアーの目盛り合わせそのものである。

## 15. 未決事項

1. G0(受理ゲート)のコスト見積もりを誰が書くか — 起票者(人間)記入か、decomposer が見積もり案を出して人間承認か
2. `/loop` の起動形態 — 手動起動のみか、スケジュール実行(automations)まで v1 に含むか
3. experiment プロファイルの成果物置き場 — 実験ログ・生成モデル等の大容量成果物の保存先規約(GitHub 外ストレージとの接続)

## 16. 実装時検証事項(着手前に公式ドキュメントで確認)

本仕様は Claude Code の機能仕様に依存する記述を含む。以下は仕様策定時点の理解であり、**実装着手時に必ず docs.claude.com の現行ドキュメントで確認し、差異があれば本仕様を先に修正する**(思い込みでの実装開始を門前払いする)。

1. subagent frontmatter の `model:` フィールド — 指定可能な値と、Fable 5 のモデル名文字列。指定不可の場合はメインセッション= orchestrator とする代替構成(§4.4 の注記どおりレート構造は維持可能)
2. subagent の `isolation: worktree` 設定 — 記法と挙動(worktree の自動作成・掃除の範囲)
3. plugin.json のスキーマ — commands / agents / skills / hooks の配置規約とマニフェスト書式
4. subagent からの `gh` CLI 利用 — allowed-tools の指定方法と、Bash 許可の粒度(`Bash(gh *)` 等)
5. `/security-review` の headless 実行 — `claude -p` からのスラッシュコマンド呼び出し可否。不可なら GitHub Action 側(§9)のみを GM に使う
6. GitHub sub-issues / issue dependencies — `gh` CLI・REST API の対応範囲。未対応操作は GraphQL API へフォールバック
7. plugin からの CI workflow ファイル生成 — GitHub Apps / Actions の権限(`workflows` 書き込み権限が必要な点)

## 付録A. 製造業・制御工学の概念との対応

本設計は工程設計・生産管理の体系と同型であり、以下の対応で読み替えられる。命名や説明にはこの語彙を優先的に使う。

| 製造業・制御工学 | 本設計 |
|---|---|
| 自働化(異常があれば止まる) | 抽象度ゲート・mechanical ゲート |
| 後工程はお客様 | 受け手基準の抽象度(waiting_level) |
| ポカヨケ | 門前払い・テンプレ必須欄 |
| 標準作業(標準なきところに改善なし) | skill・契約 YAML・初期 fixture |
| アンドン | triage inbox・通知 |
| なぜなぜ分析 | Fable 裁定の原因3分類 |
| かんばん(仕掛り制限) | WIP 制限(#24) |
| ドラム・バッファー・ロープ(TOC) | 人間レビュー帯域を制約とした起動制御 |
| 段取り替え時間の短縮 | ゲートレイテンシ・CI 速度(#17) |
| 検査・運搬・停滞は付加価値を生まない(IE) | ゲート最小化・段階導入(§14)・滞留分析(§13) |
| フィードバック制御の発振・ループゲイン | ゲートの発振検知(#25) |
| むだ時間(遅延)による不安定化 | 検証遅延の安定性要件(#17) |
