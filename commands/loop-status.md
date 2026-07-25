---
description: tasuki ループの進行状況、triage inbox(人間の裁定待ち)、メトリクスを表示する。読み取り専用
argument-hint: "[親 issue 番号]"
disable-model-invocation: true
allowed-tools: Skill, Read, Grep, Glob, Bash(gh *)
---

# /tasuki:loop-status

ループの状態はすべて GitHub 上(ラベル、issue コメント、PR)にあるため、そこから集計して表示する。
書き込みは一切しない。

`$ARGUMENTS` に親 issue 番号があればその配下に限定し、なければリポジトリ全体を対象とする。

## 1. triage inbox(最優先で表示)

人間の判断待ちを一覧化する(アンドン)。

- `loop:pause` ラベルの親 issue(一時停止中。外せば次の run が再開する)
- `loop:review` ラベルの issue(出荷前レビュー待ち。人間が `/code-review` を回す番)
- `loop:triage` ラベルの issue(エスカレーション。Fable 裁定の3分類コメントがあれば要約を併記)
- 未回答の task-question(質問コメントに回答が付いていない issue)
- 承認待ちの axis-question(契約ファイル変更 PR で open のもの)
- ready 化済みで未マージの PR(マージは常に人間)

## 2. 進行状況

子 issue ごとに1行で表示する。

```
#123 [gate:start-passed] [loop:in-progress] PR #45 (draft, CI: running) タイトル
```

- `gate:*` ラベルからゲート通過状況
- assignee と `loop:in-progress` から worker 割り当て
- 関連 PR の状態(draft / ready / CI 結果)を `gh pr list` と check-runs から

`$ARGUMENTS` に親 issue を指定した場合は、`tasuki:plan-comment` skill に従って全体像(冒頭の要約と子の一覧表、条件を満たす場合のみ依存の図)を出力する。表示のみで、issue への書き込みはしない。

## 3. メトリクス

issue コメントの verdict JSON を集計して表示する。

| 表示 | 集計方法 |
|---|---|
| ゲート別差し戻し率 | verdict コメントの gate × verdict 集計 |
| 差し戻し理由の分布 | reasons の頻出項目(契約の too_*_signals チューニング材料) |
| 差し戻し→通過までの反復回数 | 同一 issue の verdict 時系列 |
| サイクルタイム | 子 issue 起票→マージ。加工時間(worker と CI の実行)と待ち時間(キュー滞留と人間待ち)に分解できる範囲で分解する |
| axis-question 発生数 | 契約変更 PR の件数(減っていけば原則が安定) |
| モデル別判定回数 | verdict の model フィールド集計(worker レート比率の代理指標。escalation 多発は契約精度低下のシグナル) |

## 4. WIP 状態

`loop:pr` ラベルの付いた open PR 数と契約の `wip_limit_prs` を並べて表示し、超過している場合は「新規 worker は起動されない。ボトルネックは人間レビュー帯域」と明示する(観点 #24)。
