# ブートストラップと運用

## `/tasuki:loop-init`(ブートストラップ)と CI 生成

CI は plugin が **作ることを前提** とする(既存 CI は前提にしない)。
手順は次のとおり。

1. 言語検出 → language pack 選択(`pyproject.toml` → python)
2. **プロジェクト資産の棚卸し**：`.claude/agents/`、`.claude/skills/`、CLAUDE.md、導入済み plugin を走査し、ゲート / provider への接続候補を提案する([INTEGRATION.md](INTEGRATION.md))。ループ系 plugin の併用を検出したら警告する
3. 契約プロファイル雛形の配置(experiment / development を選択)+ repo override(`.claude/loop/`)
4. issue / PR テンプレート生成([CONTRACTS.md](CONTRACTS.md))。worker のコミット規約は Conventional Commits(`<type>: <summary>`)とし、PR は draft で開いて方向性を早期確認、GM + G3 通過で ready 化する
5. **CI workflow 生成**：providers.yaml から `loop-gates.yml` を生成する
   - lint / typecheck job は SARIF 出力をアップロードする(basedpyright は normalizer で SARIF 化)
   - format job は `black --check` の exit code で判定する
   - test job は JUnit XML 出力に加え、**テスト改変検知**(既存テストの削除、skip、アサーション弱化の diff チェック、観点 #18)を行う
   - security job は `anthropics/claude-code-security-review` Action(PR コメント形式)
   - 依存キャッシュ、テスト並列化、paths-ignore をデフォルトで焼き込み、PR ゲートを5〜10分以内に保つ(観点 #17)
   - 通知は失敗だけでなく成功も送る(沈黙が「成功」か「通知経路の故障」か区別できないため)
6. ラベル作成(`gate:*` 系)、sub-issues / issue dependencies の利用確認(`gh` v2.94.0 以上でネイティブ対応。それ未満は `gh api` フォールバック)
7. `max_iterations` 等バジェットのデフォルト設定

`.github/workflows/` への push には token の `workflow` scope が必要なため、前提チェックで確認する(なければ `gh auth refresh -s workflow` を案内)。

providers.yaml が単一ソースであり、CI workflow はそこからの射影である。
worker はプッシュ前に同じコマンドをローカル実行できる(高速フィードバック)が、**ゲートとして正となるのは CI の判定** である。
orchestrator は `gh api` で check-runs を読み、GM の verdict に変換する。

security-review Action の制約は3つある(2026-07 時点の README とドキュメントで確認)。

- `claude-api-key` secret が必須。secrets は CI 環境にのみ置く(観点 #15)
- 出力は PR インラインコメントと JSON 成果物で、SARIF 非対応。GM の判定には action outputs の findings 件数を使う
- プロンプトインジェクション対策が施されておらず、信頼できる PR のみを対象とする。本ループの PR は自リポジトリの worker が生成するため v1 では許容するが、外部コントリビューションを受けるリポジトリへの転用時は要再検討

## コスト管理とエスカレーション

| 機構 | 内容 |
|---|---|
| ゲート差し戻し上限 | `max_iterations_per_gate` 超過で人間へエスカレーション(ズレたまま暴走する事故の抑止) |
| 内側ループ打ち切り | verifier が成功基準と打ち切り条件で判定。基準は G2 で事前定義済であること(自己採点の防止) |
| issue 予算 | 子 issue の予算欄超過で停止して報告 |
| triage inbox | エスカレーションと axis-question 承認待ちを人間向けに一覧化(`/tasuki:loop-status`) |
| watchdog | 反復回数と直交する第二の停止装置。wall-clock と token 消費の上限超過で停止して報告(反復1回が異常に長い / 高い事故を検出) |
| 停滞検知 | 反復、ピンポン、モノローグのパターン検知(観点 #14)。実験ジョブの「待ち」はハートビートで除外 |

**verifier の成功基準と打ち切り条件がブレーキ、`max_iterations` と watchdog はシートベルト** である。
上限はループが既に浪費した後に発火するバックストップであり、停止条件の本体は G2 で事前定義された基準の側にある。
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
| モデル別トークン消費の内訳 | レート戦略の KPI。**worker レート(Sonnet)比率** が主指標。Fable + Opus 比率の膨張はエスカレーション多発=契約(too_*_signals)の精度低下シグナルであり、そのまま契約チューニングの入力になる |

これらは「ループを改善するメタループ」の入力であり、v1 では `/tasuki:loop-status` での表示までをスコープとする。

## ゲート判定の回帰テスト

実運用で得た判定例(入力と人間が正とした verdict)を fixture として蓄積し、gate-review skill や too_*_signals を変更した際に過去事例で再判定して精度が落ちていないか検証する。
誤差し戻し(false reject)と見逃し(false pass)の両方を人間ラベルで拾う。
fixture には判定に使ったモデルも記録する(bandit 化に向けた報酬データを兼ねる、[DESIGN.md](DESIGN.md) 参照)。
フレームワーク自身にも検証ループを適用する、という自己言及的な要件である。

初期 fixture は運用開始前に5件程度を手書きする([CONTRACTS.md](CONTRACTS.md) 参照)。
