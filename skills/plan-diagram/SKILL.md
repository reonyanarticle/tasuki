---
name: plan-diagram
description: 実装計画と進行を mermaid で可視化する手順。親 issue の分割・依存・レイヤーを flowchart で、ゲート進行の流れを stateDiagram-v2 で描き、GitHub issue に貼って人間が全体を俯瞰できるようにする。用途別の図種選択を含む。
---

# 実装計画と進行の可視化(mermaid)

人間が親 issue を作ったあと、ループが分割した実装計画と、各 issue がゲートを通る流れを mermaid で見せる。
図は GitHub の issue コメントに ```` ```mermaid ```` フェンスで貼る(GitHub がネイティブに描画する)。

## 図種の選び方

用途で型を選ぶ。
迷ったらこの表に従う。

| 見せたいもの | 型 | 理由 |
|---|---|---|
| 実装計画(子 issue の分割、依存、レイヤー、状態) | `flowchart LR` | 依存の合流(fan-in)、レイヤーの grouping、状態色を1枚で同時に出せる |
| 過程の説明(1 issue がゲートを通る流れと差し戻し) | `stateDiagram-v2` | ゲート列は状態機械そのもので、始点・終点と差し戻しの戻り辺が自然に書ける |
| レイヤーの並びだけの軽い一覧 | `timeline`(任意) | 依存の辺や状態色は出せないが、段の並びを一目で見せられる |

使わない型とその理由。

- `gantt`:各タスクに日付か期間が必須。tasuki は反復予算(max_iterations)で管理し時間を持たないため、日付を捏造することになる
- `mindmap`:単一ルートの木で、2つの兄弟に依存する子(fan-in)を表せない。辺ラベルも状態色も無い
- `block-beta`:beta 型で、GitHub の描画は pin されたバージョン依存で不確実

## GitHub の制約(設計上の前提)

- classDef と class による状態色は描画される
- `click` とノード内リンクは strict security で無効化される。**issue へのリンクは図の外の markdown に置く**(図はラベルに issue 番号を書くだけにする)
- 上限は maxEdges 500、maxTextSize 50000 文字。大きい分割は、完了レイヤーを1ノードに畳むか、レイヤー帯ごとに分割して投稿する
- 構文エラーは図全体がエラー表示になる。貼る前に構文を確認する

## エスケープ(壊さないための規則)

- ノードのラベルは必ずダブルクォートで囲む(`#`、`/`、`()` を含むため)。例:`I13["#13 API を追加"]`
- 日本語はそのまま使えるが、ASCII の記号を含む場合はクォートする
- `end` をノード ID にしない(subgraph を閉じる予約語)
- クォートしても `#` が壊れる場合は `#35;` に置き換える

## 計画図(flowchart)

親 issue の分割が決まったら(G1 PASS 後、または人間起票の子が揃ったら)、依存グラフとレイヤーを flowchart で描く。

手順。

1. 子 issue を `blocked_by` の依存でレイヤー(L0、L1、…)に分ける(loop.md の §1c と同じ区分)
2. レイヤーごとに `subgraph` にまとめ、`blocker --> blocked` の辺を引く
3. 各子の状態を `gate:*` / `loop:*` ラベルから決め、`classDef` の色を当てる

状態とラベルの対応。

| 状態 | 判定 | class |
|---|---|---|
| 完了(ready 化) | PR が ready | `done` |
| 進行中 | `loop:in-progress` または `gate:g2-passed` 以降 | `inprogress` |
| 差し戻し中 | `gate:*-returned` | `returned` |
| 裁定待ち | `loop:triage` | `triage` |
| 未着手(依存待ち) | 上記いずれでもない | `pending` |

テンプレート(コマンド部分の値は実データで埋める)。

```mermaid
flowchart LR
    classDef done       fill:#2da44e,stroke:#1a7f37,color:#fff
    classDef inprogress fill:#bf8700,stroke:#9a6700,color:#fff
    classDef returned   fill:#cf222e,stroke:#a40e26,color:#fff
    classDef triage     fill:#8250df,stroke:#6639ba,color:#fff
    classDef pending    fill:#6e7781,stroke:#57606a,color:#fff

    subgraph L0["レイヤー0"]
        direction TB
        I12["#12 スキーマ変更"]:::done
    end
    subgraph L1["レイヤー1"]
        direction TB
        I13["#13 API を追加"]:::inprogress
        I14["#14 認可ガード"]:::returned
    end
    subgraph L2["レイヤー2"]
        direction TB
        I15["#15 UI 配線"]:::pending
    end

    I12 --> I13
    I12 --> I14
    I13 --> I15
    I14 --> I15
```

凡例は小さな独立 subgraph として、状態色つきのノードを並べて添える。
PR へのリンクや各 issue の verdict は、図の下の markdown に箇条書きで置く(図の中に入れない)。

## 過程図(stateDiagram-v2)

1つの子 issue がゲートを通る流れの説明。
計画とは別に、運用を理解するための静的な図として1回貼れば足りる(進行のたびに更新しない)。

```mermaid
stateDiagram-v2
    [*] --> G2: 門前払い通過
    G2 --> GM: 実装され self-verify 済み
    GM --> G3: GM-local と CI が緑
    G3 --> ready: レポート照合 PASS
    ready --> [*]: 人間がマージ
    G2 --> G2: 差し戻し(書き方の再出力)
    GM --> GM: CI 赤で実装差し戻し
    G3 --> G2: 内容の不足で実装へ戻す
```

有効なゲートは契約の `enabled_gates` で変わる。
G0 / G1 / G4 を含むフルループでは、親 issue 側の受理と分割と統合を別の stateDiagram で説明してもよい(親の流れと子の流れを分ける)。

## 更新の冪等性

計画図は親 issue の「レイヤー計画」コメントに含め、進行に応じて**同じコメントを編集して更新する**(新しいコメントを毎回増やさない)。
状態色だけを差し替えれば、人間はいつでも最新の俯瞰を1コメントで見られる。
