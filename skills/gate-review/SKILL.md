---
name: gate-review
description: tasuki の抽象度ゲート(G0〜G4)の判定手順。契約の waiting_level と前工程出力を照合し、PASS / TOO_ABSTRACT / TOO_CONCRETE の3値 verdict JSON を作るときに使う。gate-reviewer agent の判定基準。
---

# ゲート判定手順

前工程の出力が、受け手が契約で宣言した待ち位置(`waiting_level`)に一致するかを3値で判定する。
判定は絶対基準ではなく契約との照合である。
契約に書かれていない基準で差し戻してはならない(基準が足りないと感じたら、それは axis-question)。

## 入力(これ以外を求めない)

- 契約: 対象フェーズの `receives` 定義(`waiting_level` / `too_abstract_signals` / `too_concrete_signals`)
- 前工程出力: issue 本文、分割案、レポートのいずれか
- 差し戻し履歴: 同一対象への過去 verdict(あれば)

maker の作業コンテキスト(セッションログ、試行錯誤の経緯)は受け取らない。
渡されても判定材料にしない(コンテキスト非共有が maker/checker 分離の前提)。

## 前提

門前払い(テンプレ必須欄の空チェック)は機械処理済み。
必須欄の有無ではなく、書かれている内容と待ち位置の一致を検査する。

## 判定手順

1. 契約の `waiting_level` を読み、「受け手は何が書かれていて、何が未指定の状態を待っているか」を一文で言い直す
2. `too_abstract_signals` を順に照合する。該当したら、該当箇所を前工程出力から引用する
3. `too_concrete_signals` を同様に照合する
4. 判定を下す
   - どちらにも該当なし → `PASS`
   - 抽象側のみ該当 → `TOO_ABSTRACT`
   - 具体側のみ該当 → `TOO_CONCRETE`
   - 両方に該当 → 受け手の作業を先に止める側(通常は抽象側)を verdict とし、reasons に両方を残す
5. `confidence` を付ける
   - `high`: 判定根拠が契約のシグナルに直接該当する
   - `low`: シグナルに直接該当せず、waiting_level からの解釈を要した
6. 差し戻し先(`return_to`)を決める
   - 内容の不足(書くべき情報を前フェーズが持っている)→ 前フェーズのロール
   - 書き方の不足(情報はあるが形式が崩れている)→ 同フェーズの再出力
   - G3 では書き分けを明示する:書き方の不足= `worker`(レポートのみ再出力)、内容の不足= `implementation`(実装への差し戻し)
7. 質問を型付けする
   - そのタスク限りの事実確認 → `task-question`(宛先: issue-author)
   - 判断原則や待ち位置の定義変更が必要 → `axis-question`(宛先: contract-pr)

## 発振検知(観点 #25)

差し戻し履歴に前回 verdict がある場合、方向を比較する。
前回と今回が TOO_ABSTRACT ⇄ TOO_CONCRETE の逆方向なら、契約の `waiting_level` 自体が曖昧である。
worker へ差し戻さず、axis-question に昇格して verdict の questions に含める。
差し戻しの反復の原因が手順(loop-report 等の skill)の不備にあると判断した場合も、axis-question の text に skill 更新提案であることを明記する(観点 #12。学びを外部化しないとループは毎周同じ穴に落ちる)。

## 出力: verdict JSON

issue コメントに記録される。スキーマは次のとおり。

```json
{
  "gate": "g2",
  "verdict": "TOO_ABSTRACT",
  "confidence": "high",
  "model": "haiku",
  "reasons": ["受け入れ条件が『使いやすく』のまま", "打ち切り条件が未定義"],
  "return_to": "decomposer",
  "questions": [
    {"type": "task-question", "to": "issue-author", "text": "..."}
  ]
}
```

## 差し戻し文の書式

差し戻し先は新規セッションで、この文と契約だけを読んで再出力する。
次の4点だけを書く。

1. 判定(3値と gate ID)
2. 該当箇所の引用(reasons と対応)
3. 期待される状態(契約の `waiting_level` をそのまま引く)
4. 最小の修正指示(何を足すか、何を削るか)

作業ログ、推測、修正案の実装詳細は書かない(TOO_CONCRETE な差し戻し文は発振の原因になる)。

## してはならないこと

- コードの良否の評価(GM の仕事)
- 契約にない基準での差し戻し(axis-question に切り出す)
- maker への直接の質問(質問はすべて verdict の questions 経由)
- 差し戻し上限やエスカレーションの管理(orchestrator の仕事)
