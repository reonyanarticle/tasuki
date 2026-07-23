---
name: baton-contract
description: tasuki の契約(プロファイル YAML の waiting_level / too_*_signals)の書き方と読み方。契約の新規作成、repo override の調整、初期 fixture の手書き、axis-question による契約変更 PR の作成時に使う。
---

# 契約の書き方と読み方

契約はフェーズ間の受け渡し仕様であり、ゲート判定の唯一の基準である。
判定者(gate-reviewer)は契約に書かれていない基準で差し戻せないため、契約の質がループの質を決める。

## waiting_level の書き方

受け手基準で「何が記載され、何が未指定の状態を待つか」を対で書く。

- 良い例: 「受け入れ条件つきで単独マージ可能な単位。実装方式は未指定」
- 悪い例: 「十分に具体的なタスク」(絶対基準はゲートで照合できない)

「何が未指定か」を省くと TOO_CONCRETE を検出できなくなる。
渡し手が書きすぎる失敗(実装方式の指定、生ログ貼り付け)も受け渡しの失敗である。

## too_*_signals の書き方

観測可能な文言で書く。
判定者が前工程出力から該当箇所を引用できる粒度が目安になる。

- 良い例: 「受け入れ条件の欠落」「特定ライブラリ・実装方式の指定」
- 悪い例: 「曖昧」「詳細すぎる」(何を見れば該当と分かるかが書かれていない)

シグナルは網羅ではなく頻出パターンの列挙でよい。
シグナルにない不一致を gate-reviewer が検知した場合は `confidence: low` になり、上位モデルで再判定される。
同じ low 判定が繰り返されるなら、そのパターンをシグナルに追加する契約 PR を出す(観点 #12 知識還流)。

## 予算欄

親 issue にはコスト上限、子 issue には `max_iterations` を必須で書く。
予算はゲートの照合対象であると同時に、watchdog と orchestrator の停止判断の入力になる。

## 初期 fixture の手書き(運用開始前に必須)

`waiting_level` は自然言語の抽象であり、書いた人間と読む gate-reviewer の目盛りは最初必ずズレている。
運用開始前に判定例を5件程度手書きし、契約と同じリポジトリの `.tasuki/fixtures/` に置く。

構成の目安は PASS 2件、TOO_ABSTRACT 2件、TOO_CONCRETE 1件。
各 fixture は次の形式で書く。

```yaml
# .tasuki/fixtures/g2-001.yaml
gate: g2
input: |
  (子 issue 本文をそのまま貼る)
expected_verdict: TOO_ABSTRACT
expected_reasons: ["受け入れ条件が『使いやすく』のまま"]
labeled_by: (人間の名前)
model: (判定に使ったモデル。回帰テストと bandit 化の入力)
```

gate-reviewer に fixture を判定させ、人間ラベルと4/5件以上一致するまで契約(シグナル)側を直す。
fixture は回帰テストの初期データを兼ねる。

## repo override(.tasuki/)

プロジェクト固有の上書きは対象リポジトリの `.tasuki/` に置き、plugin の profiles/ は編集しない。
上書きできるのはコマンド、閾値、待ち位置定義、reviewer / criteria_skills の割り当てのみ。
名前解決は project > repo override > language pack > plugin デフォルトの順。

## 契約変更(axis-question)の手順

判断原則や待ち位置の定義変更は、issue コメントで即答させず、契約ファイルへの変更 PR として起票する。

1. 変更対象のキー(`waiting_level` / シグナル / 予算)と変更理由(差し戻し履歴の引用)を PR 本文に書く
2. 影響する fixture を同じ PR で更新する(契約と fixture の不整合は回帰テストで検出される)
3. 人間の承認後にマージされて初めて、次の判定に反映される
