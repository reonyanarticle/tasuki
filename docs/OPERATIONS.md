# ブートストラップと運用

## `/tasuki:loop-init`(ブートストラップ)と CI 生成

CI は plugin が **作ることを前提** とする(既存 CI は前提にしない)。
手順は次のとおり。

1. pack 選択(各 pack の `detect` に挙がったファイルの有無で言語 pack を判定する)。pack の `providers` が使うツールの dev 依存と、`ci.lockfile` を整備する(lockfile が非 null で無ければ生成。`ci.setup` の依存解決の前提)
2. **プロジェクト資産の棚卸し**：`.claude/agents/`、`.claude/skills/`、CLAUDE.md、導入済み plugin を走査し、ゲート / provider への接続候補を提案する([INTEGRATION.md](INTEGRATION.md))。ループ系 plugin の併用を検出したら警告する
3. 契約プロファイル雛形の配置(`development`)+ repo override(`.tasuki/`。必須欄の追加を含む)
4. issue / PR テンプレート生成([CONTRACTS.md](CONTRACTS.md))。worker のコミット規約は Conventional Commits(`<type>: <summary>`)とし、PR は draft で開いて方向性を早期確認する(子 PR は checks-ci 全緑の後に orchestrator が ready 化して統合ブランチへ取り込む)
5. **CI workflow 生成**：providers.yaml から `loop-gates.yml` を生成する
   - SARIF を出す provider はそのままアップロードし、出せない provider は pack の `normalizer` で SARIF 化してからアップロードする
   - `output: exit-code` の provider(整形チェック等)は exit code だけで判定する
   - test job は JUnit XML を出力する
   - **改変検知は独立した `tampering` job で行う**(既存テストの削除、skip / xfail の追加、テストと型チェックの設定変更の diff チェック、観点「テストの信頼性」)。この job は checkout と diff だけを行い、PR のコードを実行しない(実行してから検知すると、実行されたコードが base ref を書き換えて検知を無効化できる)。アサーション弱化は機械検知せず成果ゲートのレビュー観点で検査する
   - security job は `anthropics/claude-code-security-review` Action(PR コメント形式)
   - 依存キャッシュと並列 job をデフォルトで焼き込み、PR ゲートを5〜10分以内に保つ(観点「フィードバック速度」)。paths-ignore は使わない(job を丸ごとスキップすると check-run が作られず、形式ゲート判定が fail-open になるため)
   - 通知は失敗だけでなく成功も送る(沈黙が「成功」か「通知経路の故障」か区別できないため)
7. ラベル作成(`gate:*`、`loop:*`、`tasuki:*`)、sub-issues / issue dependencies の利用確認(作成も `--json subIssues` での読み取りも `gh` v2.94.0 以上。未満は `gh api` フォールバック)
8. `max_iterations` 等バジェットのデフォルト設定と、判定例(fixture)の下書き生成
9. **生成物をブートストラップ用ブランチ(`tasuki/init`)へコミットして push し、default branch への PR を1件開く。** default branch へ直接 push しない。生成物はガバナンスの制定であり、人間がレビューしてマージすることで入る(反映の形はループ本体と同型で、機械は PR 作成まで)

HTTPS プロトコルで push する場合、`.github/workflows/` への push には token の `workflow` scope が必要になる。
前提チェックで Git operations protocol を確認し、https のときのみ scope を要求する(SSH 鍵での push には不要。E2E で実地確認済み)。

providers.yaml が単一ソースであり、CI workflow、orchestrator のローカル実行、worker の self-verify はすべてそこからの射影である。
形式ゲートは2段で実行する(観点「フィードバック速度」)。
反復中は orchestrator が一時 worktree で providers のコマンドを直接実行して即時判定し(checks-local。worker の自己申告は使わない)、CI の往復を待たない。
**マージ判断の正は CI** であり、verifier の met と成果ゲートの PASS の後に、最終コミットの check-runs 全成功を確認してから PR を ready 化する(checks-ci)。
工程内検査を手元に置き、出荷検査を CI に置く分担である。

security-review Action の制約は4つある(採用時に README とドキュメントで確認した)。

- `claude-api-key` secret が必須。secrets は CI 環境にのみ置く(観点「実行環境の隔離、権限最小化」)
- この Action は Claude API を直接呼ぶため、Claude Code の契約とは別の API 課金になる(ループ本体の orchestrator / reviewer / worker はユーザーの Claude Code セッションで動き、API キーを使わない)。このため **security job はオプトイン**とし、既定では生成しない。`/tasuki:loop-init` で選択した場合のみ job を生成し `enabled_gates` に `checks-security` を追加する(条件スキップによる見かけの成功は作らない)
- 出力は PR インラインコメントと JSON 成果物で、SARIF 非対応。形式ゲートの判定には action outputs の findings 件数を使う
- Action の参照はコミット SHA に固定する(ブランチやタグの参照は差し替え可能で supply-chain リスクになる)
- プロンプトインジェクション対策が施されておらず、信頼できる PR のみを対象とする。本ループの PR は自リポジトリの worker が生成するため v1 では許容するが、外部コントリビューションを受けるリポジトリへの転用時は要再検討

## コスト管理とエスカレーション

| 機構 | 内容 |
|---|---|
| ゲート差し戻し上限 | `max_iterations_per_gate` 超過で人間へエスカレーション(ズレたまま暴走する事故の抑止) |
| 内側ループ打ち切り | verifier が成功基準と打ち切り条件で判定。基準は着手ゲートで事前定義済であること(自己採点の防止) |
| issue 予算 | 子 issue の予算欄(max_iterations)を内側ループの有効上限に採用(契約値と issue 値の小さい方)。超過で停止して報告 |
| triage inbox | エスカレーションと axis-question 承認待ちを人間向けに一覧化(`/tasuki:loop-status`) |
| 停止した実行の回収 | assignee が `stale_assignment_minutes`(既定60分)を超えて残っている子を再入可能に戻す(落ちたセッションが担当のまま子を塞ぐ事故の回収)。wall-clock の上限は子 issue の打ち切り条件が持ち、worker 自身が守る。token 上限は計測手段の導入とあわせて v2 |
| 停滞検知 | 反復、ピンポン、モノローグのパターン検知(観点「停滞検知」)。実験ジョブの「待ち」はハートビートで除外 |

**verifier の成功基準と打ち切り条件がブレーキ、`max_iterations` と停滞検知はシートベルト** である。
上限はループが既に浪費した後に発火するバックストップであり、停止条件の本体は着手ゲートで事前定義された基準の側にある。
上限発火が常態化しているなら、直すべきは上限値ではなく契約である。

エスカレーションのモデル昇格連鎖(`haiku → sonnet → opus → Fable 裁定 → 人間`)は [DESIGN.md](DESIGN.md) を参照。

## 観測性とメトリクス

ゲート判定はすべて issue コメントに構造化して残るため、そこから収集する。

| メトリクス | 用途 |
|---|---|
| ゲート別差し戻し率と差し戻し理由の分布 | too_*_signals の精度改善(契約のチューニング材料) |
| 差し戻し→通過までの反復回数 | バジェットのデフォルト調整 |
| サイクルタイム(子 issue 起票→マージ) | ループ全体のボトルネック特定。**加工時間(worker とゲートの実行)と待ち時間(キュー滞留と人間待ち)に分解** して計測する(IE の滞留分析)。改善は TOC の5集中ステップに従い、制約となっている工程だけに投資する |
| axis-question 発生数 | 契約の成熟度指標(減っていけば原則が安定) |
| モデル別判定回数(トークン消費の代理指標。実測は v2) | レート戦略の KPI。**worker レート(Sonnet)比率**を近似する。上位モデル判定比率の膨張はエスカレーション多発=契約(too_*_signals)の精度低下シグナルであり、そのまま契約チューニングの入力になる |

これらは「ループを改善するメタループ」の入力であり、v1 では `/tasuki:loop-status` での表示までをスコープとする。

## 出荷前レビュー(最終コード評価)

形式ゲートと成果ゲートを通っても、**コードの設計と正しさは誰も見ていない**。
形式ゲートは機械判定、成果ゲートはレポートの形式照合であり、どちらも実装の良否を扱わない。
そこで親 PR に対して、orchestrator が subagent でレビューを自動実行する(loop.md の 3c「出荷前レビュー」)。

- 実行条件は「統合ゲート PASS、親 PR の check-runs 全緑、統合ブランチの merge-base が default branch の先端と一致」。反復のたびには行わず、フィーチャーの完成形(親 PR の全差分)に対して1回行う
- 5観点(設計と統合、正しさと境界条件、テストの妥当性、複雑さと可読性、運用影響)を、契約の `preship_review` の規模で回す(既定 scaled: 小さい diff は1セッションに5観点、大きい diff は観点別5セッション。manual にすると従来どおり人間が起動する)
- 変更が認証、権限、外部入力、秘密情報、CI 設定に触れるなら `/claude-security:claude-security` の実行を人間に案内する(別建ての API 課金が人間の判断に属するため、これは自動実行しない)
- 所見はそのまま採用しない。orchestrator がどのツリーに対して走ったかを確認し、再現条件を確かめ、実在するものだけを worker への差し戻しにする

観点の正は [commands/loop.md](../commands/loop.md) の出荷前レビュー節である。

## issue に残す出力の原則

ループが GitHub に残すものは、**人間可読の markdown を主とし、機械可読の JSON と YAML は `<details>` に畳む**。
生の JSON や YAML をそのまま貼らない。
状態復元は畳んだ JSON を読めば従来どおりできる。

| 出力 | 主に載せるもの | 畳むもの |
|---|---|---|
| verdict コメント | 状態印、理由、次の一手、質問 | verdict JSON |
| 分割ゲートの PASS | 子と対応する親要件の一覧 | 分割案 YAML |
| 計画コメント | 冒頭の要約と子の一覧表 | — |
| 実装方針(実装前) | 作るもの、既存への接続、選択と理由、確かめ方 | — |
| レポート | 要件と結果の対応表、結論 | 生データはリンク |

計画コメントの図は**条件を満たすときだけ**描く(合流や分岐がある、3レイヤー以上、子5件以上)。
判断基準は `tasuki:plan-comment` skill、図の記法は `tasuki:mermaid` skill にある。

## ゲート判定の回帰テスト

実運用で得た判定例(入力と人間が正とした verdict)を fixture として蓄積し、gate-review skill や too_*_signals を変更した際に過去事例で再判定して精度が落ちていないか検証する。
誤差し戻し(false reject)と見逃し(false pass)の両方を人間ラベルで拾う。
fixture には判定に使ったモデルも記録する(bandit 化に向けた報酬データを兼ねる、[DESIGN.md](DESIGN.md) 参照)。
フレームワーク自身にも検証ループを適用する、という自己言及的な要件である。

初期 fixture は運用開始前に5件程度を手書きする([CONTRACTS.md](CONTRACTS.md) 参照)。
