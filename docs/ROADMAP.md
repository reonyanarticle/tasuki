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
| language pack | python(uv / ruff / black / basedpyright / pytest) |

### 含まない

- python 以外の language pack(インターフェースだけ切っておく)
- タスク複雑度によるモデル自動選択(将来のコスト最適化候補)
- worker セッション内の常駐セキュリティガード(security-guidance 等はユーザー任意導入)
- 外部 issue を受け付けるリポジトリでの運用(信頼境界のハードニングは v2。[SECURITY.md](SECURITY.md))
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

### フェーズ1の E2E 実施結果(2026-07-23、tasuki-e2e リポジトリで headless 実行)

| 受け入れ条件 | 結果 |
|---|---|
| loop-init が素の Python リポジトリに契約雛形、テンプレ、`loop-gates.yml`、ラベルを生成 | 達成(uv.lock 生成、security オプトアウト構成を含む) |
| 必須欄が空の子 issue が門前払いで差し戻される(LLM なし) | 達成(親 issue の門前払いも動作) |
| 手書き fixture 5件で gate-reviewer(haiku)が4件以上一致 | 達成(5/5、confidence すべて high) |
| 差し戻し verdict が issue コメントに JSON で記録 | 達成 |
| G2 通過の子 issue を worker が実装し draft PR 作成、GM 実行到達 | 達成(GM 緑 → verifier met → PR ready 化まで完走) |
| 差し戻し2連続で sonnet エスカレーション発火 | 達成(verdict 履歴 haiku → haiku → sonnet。昇格後の判定で PASS し、worker が issue 予算内で完走) |

E2E で発見し修正した不具合:workflow scope 前提の過剰要求(SSH では不要)、`.claude/loop/` の機密ファイルガード衝突(`.tasuki/` へ移設)、CI テンプレートの YAML 不正(notify の `: ` )、SARIF アップロードの GHAS 依存(best-effort 化)。
check-run ゼロ件の fail-closed が YAML 不正を設計どおり捕捉したことも確認した。
追加の運用ギャップ2件(差し戻し再入の編集検知は timeline ではなく GraphQL の lastEditedAt を使う、変更済み worker worktree は自動掃除されないため orchestrator が終了時に削除する)も E2E で発見して修正した。
GM ハイブリッド(GM-local / GM-ci)、task-question の回答反映と再入、worker による前提不在の検出(実在しない関数を前提とした issue への task-question)も実地で動作確認済み。

### フェーズ2: G3(成果ゲート)を追加

昇る側の対応表検証を回す。

**フェーズ2の受け入れ条件(完了の定義)**：

- `enabled_gates` に `g3` を含む契約で、verifier の met 後に worker のレポートが G3(sonnet)で照合される
- G3 の判定例 fixture 3件(PASS / TOO_ABSTRACT / TOO_CONCRETE)で、gate-reviewer-sonnet の判定が人間の正解ラベルと3件中3件一致する(目盛り合わせ)
- 対応表または結論を欠くレポートが TOO_ABSTRACT、生ログ貼り付けが TOO_CONCRETE で差し戻される
- 書き方の不足の差し戻しでは、worker が実装に触れずレポートのみを新規セッションで再出力する
- G3 PASS 後にのみ ready 化される(GM-ci と併せて)

### フェーズ2の E2E 実施結果(2026-07-23、tasuki-e2e リポジトリ)

| 受け入れ条件 | 結果 |
|---|---|
| verifier met 後に G3(sonnet)がレポートを照合 | 達成(#8 で実レポートを PASS / high 判定。対応表の N対1 と孤児なしを reasons で確認) |
| G3 fixture 3件で3件一致 | 達成(較正の往復2回を経て4 fixture 全一致。不一致2回はいずれも fixture 側の欠陥で、reviewer は孤児検出と「両シグナル該当時は抽象側優先」規則を正しく適用していた) |
| 対応表、結論の欠如が TOO_ABSTRACT、生ログ貼り付けが TOO_CONCRETE | 達成(fixture 検証) |
| 書き方の不足はレポートのみ再出力 | 達成(悪いレポートを仕込んだ実走で検証。G3 門前払いが欠落4欄を LLM なしで検出し、worker が実装に触れずレポートのみ再出力、2f 再判定で PASS) |
| G3 差し戻し状態からの run 境界の再入 | 達成(差し戻し直後のセッション死亡を模擬。次の run が起票者待ちにせず、2a と G2 をやり直さず、再出力 worker を自力起動して 2f から復旧) |
| G3 PASS 後にのみ ready 化 | 達成(gate:g3-passed → GM-ci → ready の順序を確認) |

副次の実地確認:WIP 制限(観点 #24)が ready PR 3件の滞留で発火し、worker 起動を正しく保留した。親 issue の予算欄(子3件)と実子4件の不一致も orchestrator が人間に指摘した。
G3 レビュー(3観点、確定16件)後の再実走では、拡充した契約 signals(要件 ID の採番一致、期待値の根拠の仕様由来、secrets 不在)が verdict の reasons にそのまま現れることも確認した。
実ループ未発火のまま残る経路は、`return_to: implementation`(内容の不足による実装差し戻し)と 2g の CI 失敗分岐の2つ(手順、fixture、テストでの検証のみ)。

### フェーズ3: G0 / G1 / G4 とレイヤー並列実行

フルループへ移行する。

**フェーズ3の受け入れ条件(完了の定義)**：

- `enabled_gates` に全 abstraction ゲートを含む契約で、親 issue が G0(opus)の受理判定を受ける
- 子 issue が無い親に対し、decomposer の分割案が G1(opus)で照合され、PASS 後に orchestrator が子 issue を起票して紐付ける(必須欄、AC-n / SC-n 採番、依存設定、`via tasuki-decomposer` 記載)
- 依存の循環がエラーとして検出され、実行せずに停止する
- 依存グラフからレイヤーが構成され、レイヤー内の子 issue が並行処理される。次レイヤーへは前レイヤーの ready PR がすべて人間にマージされるまで進まない
- 全子 issue のマージ後に G4 が親要件へのロールアップを照合し、孤児の親要件があれば差し戻して追加分割を提案する
- G0 / G1 / G4 の判定例 fixture(各2件以上)で人間ラベルと全一致する(目盛り合わせ)

### フェーズ3の E2E 実施結果(2026-07-23、tasuki-e2e リポジトリ)

| 受け入れ条件 | 結果 |
|---|---|
| G0(opus)の受理判定 | 達成(親 #12 が PASS。gate:g0-passed) |
| decomposer 分割 → G1 → 子 issue 起票 | 達成(子なし親から2子を自動分割、起票。必須欄、AC-n 採番、依存 #14←#13、via 記載。実装方式を子タイトルに持ち込まない粒度を維持) |
| 依存の循環をエラーとして停止 | 達成(実走で GitHub がネイティブ依存の循環を API 拒否すると判明。§1c は二重の安全網とし、実効防衛は G1 の set_signals=opus が分割案の循環を検出。fixture g1-003 で PASS→TOO_ABSTRACT を実証) |
| レイヤー構成と前進規則 | 達成(L1→合流→人間マージ→L2、マージ済み子を除く再構成も動作)。1レイヤー複数子の並行も別シナリオで実証(独立子2件が同一 L1 で処理され両 PR ready) |
| G4 の親要件ロールアップ照合 | 達成(integration フェーズの契約で opus が PASS / ロールアップ表を親にコメント。孤児差し戻し側は fixture g4-002 で検証) |
| G0 / G1 / G4 の fixture 較正 | 達成(6/6 全一致、初回) |

フェーズ3レビュー(3観点、確定16件)の修正のうち、クラッシュ復旧系(部分起票の突合、g0-returned 再入、分割案の verdict 添付からの復旧等)は手順、テスト検証のみで実走未発火。実運用で自然発火した際が実地検証になる。

2026-07-24 に claude-security スキャン(7観点)を実施し、信頼境界の設計上の弱点を確定した([SECURITY.md](SECURITY.md))。
未検証の issue / コメント本文が Bash を持つ worker / verifier に流れる点が根本原因で、指示レベルの緩和を全 agent に入れたうえで、v1 の適用範囲を信頼できる issue のリポジトリに限定すると明記した。
作者認証と worker/verifier の sandbox は v2 のハードニングとする。

## 未決事項

1. ~~G0(受理ゲート)のコスト見積もりを誰が書くか~~ **決着(2026-07-23)**：起票者(人間)がテンプレ必須欄として記入する(門前払いと整合する最小構成)。decomposer による見積もり案と人間承認のフローは v2 予約
2. ~~`/tasuki:loop` の起動形態~~ **決着(2026-07-23)**：v1 は手動起動のみ。スケジュール実行(automations)は v2 予約
3. experiment プロファイルの成果物置き場。実験ログや生成モデル等の大容量成果物の保存先規約(GitHub 外ストレージとの接続)

## 実装時検証事項(着手前に公式ドキュメントで確認)

本設計は Claude Code の機能仕様に依存する記述を含む。
以下は策定時点の理解であり、**実装着手時に必ず docs.claude.com の現行ドキュメントで確認し、差異があれば docs を先に修正する**(思い込みでの実装開始を門前払いする)。

1. subagent frontmatter の `model:` フィールド。指定可能な値と、Fable 5 のモデル名文字列。指定不可の場合はメインセッション= orchestrator とする代替構成(レート構造は維持可能、[DESIGN.md](DESIGN.md) 参照)
2. subagent の `isolation: worktree` 設定。記法と挙動(worktree の自動作成と掃除の範囲)
3. plugin.json のスキーマ。commands / agents / skills / hooks の配置規約とマニフェスト書式
4. subagent からの `gh` CLI 利用。allowed-tools の指定方法と、Bash 許可の粒度(`Bash(gh *)` 等)
5. `/security-review` の headless 実行。`claude -p` からのスラッシュコマンド呼び出し可否。不可なら GitHub Action 側([OPERATIONS.md](OPERATIONS.md))のみを GM に使う
6. GitHub sub-issues / issue dependencies。`gh` CLI と REST API の対応範囲。未対応操作は GraphQL API へフォールバック
7. plugin からの CI workflow ファイル生成。GitHub Apps / Actions の権限(`workflows` 書き込み権限が必要な点)

### 検証結果(2026-07-23、公式ドキュメントで確認済み)

1. `model:` は `haiku` / `sonnet` / `opus` / `fable` を受け付け、省略時は `inherit`(メイン会話と同モデル)。plugin agent でも同じ
2. `isolation: worktree` は有効。worktree は自動作成され、変更がなければ自動で掃除される。agent 種別の制約なし
3. plugin.json は `name` のみ必須。commands / agents / skills は規約ディレクトリから自動発見される(マニフェストへの列挙は不要)
4. **差異あり**：agent frontmatter の `tools:` はツール名のみで、`Bash(gh *)` の粒度は書けない。粒度制御は permissions 設定か hooks 側。ただしコマンド(commands/*.md)の `allowed-tools:` は粒度指定可。対応として gate-reviewer には Bash を渡さず(orchestrator が issue 本文を渡す)、コマンド側は `allowed-tools: Bash(gh *)` で絞る
5. **差異あり**：組み込みコマンドは `claude -p` から呼べない。対応として GM の security は GitHub Action(`anthropics/claude-code-security-review`)のみを使う。同 Action は SARIF 非出力(PR コメント+ JSON 成果物)、`claude-api-key` が必須
6. sub-issues と issue dependencies は REST / GraphQL とも GA。`gh` CLI はどちらも v2.94.0(2026-06)からネイティブ対応(`--parent` / `--blocked-by` 等)。それ未満は `gh api` フォールバック
7. `.github/workflows/` への push には classic PAT で `workflow` scope、fine-grained / Apps で `workflows: write` が必要。Actions の `GITHUB_TOKEN` では不可。`gh auth refresh -s workflow` で付与できる。**E2E での追記(2026-07-23)**：この制約は OAuth token による HTTPS push に対するもので、SSH 鍵での push には適用されない(実地確認済み)。前提チェックは protocol が https のときのみ scope を要求する

**設計への反映**：subagent は既定で別の subagent を起動できない(`Agent` ツールが除去される)ことも確認した。
このため orchestrator は agent ではなく、`/tasuki:loop` を実行するメインセッションが務める([DESIGN.md](DESIGN.md))。
また agent frontmatter の `model:` は静的なため、ゲート別モデルは gate-reviewer の3変種(haiku / sonnet / opus)として実装し、エスカレーションは変種の切り替えで行う。
worker からプロジェクト subagent への委譲は、導入先の `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` 設定によるオプトインで可能にする([DESIGN.md](DESIGN.md))。
