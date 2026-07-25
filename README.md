# tasuki(襷)

AI エージェント間の襷(タスクと契約)の受け渡しを中継所(ゲート)で検めながら、GitHub issue を自走で完走させる Claude Code plugin。

名前は駅伝に由来する。
区間をフェーズ、走者を agent、中継所をゲート、襷を契約、繰り上げスタートを打ち切り条件と読み替え、要件を具体化していく往路(降りるゲート)と、成果を報告へ束ねる復路(昇るゲート)をひとつのループとして走り切る。

## なぜゲートか

具体と抽象を往復する受け渡しでは、「この出力は、受け手が追加の解釈なしに受け取れる抽象度か」というズレがつなぎ目ごとに生じる。
抽象度に絶対の基準はなく、適切な粒度は受け手が誰か(次の分割役か、実装役か、人間か)で変わる。
人間がループの中にいれば都度直せるが、AI が実装からレビューまでを自律で回すループではそれができない。
そこで tasuki は、ズレの検知を仕組みとして各つなぎ目に埋め込む。
これがゲートであり、判定は絶対基準ではなく、受け手が契約で宣言した「待ち位置」との照合になる。
思想の全体は [docs/PHILOSOPHY.md](docs/PHILOSOPHY.md) にある。

## 何をするか

GitHub issue 駆動の自律ループ(実装と検証)の各フェーズのつなぎ目に抽象度ゲートを置き、出力を契約の待ち位置と照合して3値で判定する。

| 判定 | 意味 |
|---|---|
| `PASS` | 引き渡し位置が待ち位置と一致している |
| `TOO_ABSTRACT` | 曖昧すぎて、受け手が追加の解釈なしには受け取れない |
| `TOO_CONCRETE` | 詳しすぎて、受け手の判断余地を奪っている |

検証(実験)と開発の両方で使える汎用構成とし、まず Python を対象に実装している。

## 処理の流れ

人間が書くのは親 issue とマージだけで、あいだのレビューと実装はゲートと agent が回す。
差し戻しは triage として人間に返る。

```mermaid
flowchart TD
    accTitle: tasuki の処理の流れ
    accDescr: 人間が親 issue を書くと、G0 受理と G1 分割を経て子 issue に分かれる。各子は G2 着手、実装、GM 形式検査、G3 成果照合を通り、draft PR が ready になる。人間がマージした後、G4 統合を経て人間が親 issue を close する。各ゲートの差し戻しは triage として人間に戻る。
    classDef human fill:#0969da,stroke:#0a4c9e,color:#fff
    classDef gate fill:#8250df,stroke:#6639ba,color:#fff
    classDef work fill:#bf8700,stroke:#9a6700,color:#fff

    H0["人間: 親 issue を書く"]:::human --> L["/tasuki:loop"]
    L --> G0{"G0 受理"}:::gate
    G0 -->|"曖昧"| T["人間: triage で issue を直す"]:::human
    T --> L
    G0 -->|"OK"| D["decomposer が分割"]:::work
    D --> G1{"G1 分割"}:::gate
    G1 -->|"NG"| T
    G1 -->|"OK"| C["子 issue を起票しレイヤー化"]:::work

    subgraph CHILD["各子 issue(レイヤー内は並行)"]
        direction TB
        G2{"G2 着手"}:::gate -->|"曖昧/詳しすぎ"| TT["人間へ差し戻し"]:::human
        G2 -->|"OK"| W["worker が実装"]:::work
        W --> GM{"GM 形式(lint/型/テスト)"}:::gate
        GM -->|"NG"| W
        GM -->|"OK"| V["verifier が成功基準を照合"]:::work
        V --> G3{"G3 成果(レポート照合)"}:::gate
        G3 -->|"NG"| W
        G3 -->|"OK"| R["draft PR を ready 化"]:::work
    end

    C --> G2
    R --> HM["人間: PR をマージ"]:::human
    HM --> G4{"G4 統合"}:::gate
    G4 -->|"孤児要件あり"| T
    G4 -->|"OK"| HC["人間: 親 issue を close"]:::human
```

## 前提

- git リポジトリと GitHub リモート
- `gh` CLI(sub-issues / issue dependencies を使うため v2.94.0 以上を推奨。未満は `gh api` フォールバック)
- Python プロジェクト(`pyproject.toml`)と `uv`
- CI は plugin が生成する(既存 CI は前提にしない)

## 導入

Claude Code に plugin として読み込む。
開発や試用は `--plugin-dir` で直接読む。

```bash
claude --plugin-dir /path/to/tasuki
```

常用する場合は `.claude-plugin/marketplace.json` を用意し、`/plugin marketplace add <パス>` で登録する。
読み込めたら `/plugin` の一覧に tasuki が出る。

## 使い方

1. plugin を導入し、対象リポジトリで `/tasuki:loop-init` を実行する。契約プロファイル、issue と PR のテンプレート、CI workflow、ラベルが生成される
2. やりたいことを **親 issue に1つ書く**(テンプレの必須欄=背景、目的、価値、予算、完了の定義を埋める)。子 issue は自分で書かない
3. `/tasuki:loop <親 issue 番号>` を実行する。**ループがまず issue をレビューする**:受理(G0)→分割(G1)→着手(G2)の順にゲートを通し、通ったものだけ実装に進む。issue が曖昧なら triage で差し戻すので、指摘に沿って issue を直して再実行する
4. `/tasuki:loop-status <親番号>` で進行状況と裁定待ち(triage)を確認する。親 issue を指定すると、子ごとの一覧表で全体を俯瞰できる(依存に分岐や合流があるときは mermaid の図も添う)
5. **マージは常に人間が実行する**。ゲートが行うのはレビューまでで、最終判断は人間に残る

レビューは loop の中で gate が行い、ダメなときだけ triage であなたに返る。
issue を書く前に別途レビューさせる工程は要らない。

補足(任意だが推奨):ゲートのレビュアーは契約の「待ち位置」という自然言語で判定するため、最初は人間の感覚とズレる。
「この issue は PASS のはず」「これは差し戻しのはず」という判定例を数件書いて目盛りを合わせると、初回から判定が安定する。
手順は `tasuki:baton-contract` skill が案内する。

## 安全に使える範囲

v1 は issue、PR、コメントの内容を信頼できるリポジトリ専用である(maintainer が issue を書く前提)。
外部からの issue を受け付けるリポジトリでは、未検証テキストが agent に流れるため使わない。
詳細と v2 のハードニングは [docs/SECURITY.md](docs/SECURITY.md) にある。

## ドキュメント

設計文書は [docs/](docs/README.md) にまとまっており、読む順序と索引は [docs/README.md](docs/README.md) が案内する。
実装の到達状況(段階導入と E2E 結果)は [docs/ROADMAP.md](docs/ROADMAP.md) にある。

## License

[MIT](LICENSE)
