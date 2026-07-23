---
description: tasuki ループの起動。親 issue を指定し、子 issue を G2 ゲートと GM(CI)を通して自走させる。このコマンドを実行するメインセッションが orchestrator を務める
argument-hint: "<親 issue 番号>"
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Bash(gh *), Bash(git *)
---

# /tasuki:loop

このセッションはループの orchestrator である。
subagent は別の subagent を起動できないため、orchestrator はメインセッションが務める(docs/DESIGN.md)。
**orchestrator はコードを書かない。** 作業はすべて agent へ委譲し、自分は依存グラフ、差し戻し回数、エスカレーションだけを管理する。
コンテキストには要約のみを保持し、agent の作業ログを取り込まない。

現在は段階導入のフェーズ1であり、有効なゲートは契約の `enabled_gates`(G2 + GM)のみ。
G1 が無効の間、子 issue は人間が起票済みである前提とする。

## 0. 前提と状態復元(冪等性、観点 #19)

1. `.claude/loop/profile.yaml` を読む。なければ `/tasuki:loop-init` を案内して中断する
2. `$ARGUMENTS` の親 issue を `gh issue view` で読む。sub-issues で子 issue 一覧を得る(gh < 2.94.0 なら `gh api` フォールバック)
3. **状態はラベルと issue コメントから復元する。** ローカルに状態ファイルを持たない。各子 issue の `gate:*` ラベルと既存 verdict コメントを読み、途中から再開する
4. 二重起動の防止(観点 #20): 親 issue に自分より新しい orchestrator 開始コメントがないか確認してから、開始コメントを1件残す
5. WIP 確認(観点 #24): 未レビュー(open)の loop 由来 PR が `wip_limit_prs` 以上なら、新規 worker を起動せず、その旨を報告して人間レビューを促す

## 1. 子 issue ごとのゲート実行

依存(blocked-by)が解決している子 issue から着手する。
子 issue への割り当ては assignee 設定を CAS 的に扱う(設定済みなら他の実行が担当中とみなし触らない)。

### 1a. 門前払い(機械チェック、LLM なし)

契約の `child_issue_required_fields` の各見出しについて、issue 本文の該当セクションが空でないかを確認する。
空欄があれば、LLM を呼ばずに差し戻す: 不足欄を列挙したコメントを issue に残し、`gate:g2-returned` ラベルを付ける。
同じ内容のコメントが既にあれば再投稿しない(冪等)。

### 1b. G2(契約照合)

`tasuki-gate-reviewer`(haiku)へ委譲する。
渡すのは次の2つだけ(worker や過去セッションのコンテキストは渡さない)。

- 子 issue 本文
- 契約の該当フェーズ `receives` 定義(waiting_level / too_*_signals)+ 差し戻し履歴(過去 verdict があれば)

返った verdict JSON を issue コメントに記録する(既存の同一 verdict がないことを確認してから)。

**エスカレーション規則(docs/DESIGN.md)**：

- `confidence: low` の PASS → 破棄し、`tasuki-gate-reviewer-sonnet` で再判定する(low の REJECT はそのまま差し戻してよい)
- 同一ゲートで差し戻し2連続 → 次回判定を `tasuki-gate-reviewer-sonnet` へ昇格する
- 差し戻しが `max_iterations_per_gate` を超過 → 停止。状況を要約し「契約の不備 / タスクの筋の悪さ / モデル能力の限界」を切り分けたコメントを親 issue に残し、`loop:triage` ラベルを付ける

**質問のルーティング(docs/CONTRACTS.md)**：

- `task-question` → 子 issue にコメントで質問し、`loop:triage` を付けて回答待ちにする。回答が来たら issue 本文へ反映してから再判定する
- `axis-question` → 契約ファイル(`.claude/loop/profile.yaml`)への変更 PR を起票する。軸の欠落(待ち位置未定義)ならブロッキング、改善提案なら進めながら非同期で起票する

PASS したら `gate:g2-passed` ラベルを付け、`gate:g2-returned` を外す。

### 1c. 実装(worker)

`tasuki-worker`(sonnet、worktree 分離)へ委譲する。
渡すのは子 issue 本文のみ。
worker の義務は worktree 上での実装、self-verify、Conventional Commits、draft PR 作成、loop-report 形式の報告、掃除。

差し戻し再実行は **必ず新規の worker セッション** で行う(観点 #16)。
前セッションを継続せず、渡すのは子 issue 本文+差し戻し verdict(または CI findings、verifier の未達項目)のみ。

### 1d. GM(CI)

worker の draft PR に対する check-runs を `gh api` で読む(`loop-gates.yml` の判定が正)。

- 全 job 成功 → GM PASS。verifier(1e)へ
- 失敗 → findings(失敗 job と要点)を抽出し、新規 worker セッションに差し戻す。反復回数は `max_iterations_per_gate` で管理する

### 1e. 内側ループの出口(verifier)

`tasuki-verifier` へ委譲する。
渡すのは実行結果(PR、CI 結果、worker のレポート)と、子 issue の成功基準・打ち切り条件のみ。

- `met` → PR を ready 化し、子 issue に完了コメントを残す(フェーズ2で G3 が入るまでレポート照合は人間に委ねる)
- `continue` → 未達項目を新規 worker セッションへ。反復は `max_inner_loop` まで
- `abort` → 打ち切り。理由をコメントし `loop:triage` を付ける
- `drifting` → 作業が元要件からずれている。G2 相当の再照合(1b)に戻す(観点 #21)
- `waiting` → 長時間ジョブの進行中。停滞と区別し、ポーリング間隔を報告して待つ(観点 #14)

## 2. 停止装置(ブレーキとシートベルト)

停止条件の本体は G2 で事前定義された基準(verifier が判定)である。
以下は暴走時のバックストップであり、発火が常態化したら直すのは上限値ではなく契約(docs/OPERATIONS.md)。

- `max_iterations_per_gate` / `max_inner_loop` 超過 → `loop:triage`
- 停滞検知: 同一アクションの反復、2つの action-observation ペアの交互出現(ピンポン)、進捗のない連続報告を検知したら停止して報告する
- 発振検知: 同一箇所で TOO_ABSTRACT ⇄ TOO_CONCRETE が交互に出たら、worker へ再差し戻しせず axis-question に昇格する(観点 #25)

## 3. 終了報告

レイヤー(依存解決済みの子 issue 群)の処理が終わるごとに、親 issue に進行サマリ(通過 / 差し戻し中 / triage / 完了)をコメントする。
**マージは常に人間が実行する。** ready 化した PR の一覧と、`loop:triage` の一覧を最後に報告して終了する。
