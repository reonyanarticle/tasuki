# 契約スキーマとテンプレート

契約(プロファイル YAML)は単一ソースであり、issue / PR テンプレートと CI workflow はその射影である(二重管理をしない)。

## プロファイル YAML

```yaml
# profiles/development.yaml
profile: development
budgets:
  max_iterations_per_gate: 3      # 超過で人間にエスカレーション
  max_inner_loop: 5               # verifier の打ち切り上限デフォルト
  wip_limit_prs: 3                # 未レビュー PR の上限(#24)。超過で新規 worker 起動を停止

# モデルは agent 定義に固定されている(worker/verifier = sonnet、gate-reviewer は haiku/sonnet/opus の3変種)。
# reviewer の差し替えは gates[].reviewer に導入先プロジェクトの agent 名を指定する。

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

templates:                        # issue テンプレの必須欄(G2 門前払いの機械チェック対象)
  parent_issue_required_fields: [背景, 目的, 価値, 予算(コスト上限), 完了の定義]
  child_issue_required_fields: [対応する親要件, 目的, 受け入れ条件, 成功基準, 打ち切り条件, 予算(max_iterations)]
  report_required_fields: [要件⇔結果の対応表, 結論, 再現手順, 生データへのリンク]
  pr_required_fields: [概要, 変更点, 影響範囲と revert 可否, 対応 issue, 検証方法]

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
    criteria_skills: []           # 判定基準に加える導入先プロジェクトの skill 名(任意)
  - id: gm-lint
    kind: mechanical
    provider: lint                # pack の providers.yaml を参照
    blocking_threshold: error     # SARIF level
  - id: gm-format
    kind: mechanical
    provider: format              # exit-code 判定(black --check)
  - id: gm-typecheck
    kind: mechanical
    provider: typecheck
    blocking_threshold: error
  - id: gm-test
    kind: mechanical
    provider: test                # JUnit XML: failures == 0
  - id: gm-security
    kind: mechanical
    provider: security            # providers.yaml のキーと一致させる
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

# 段階導入(ROADMAP.md)。フェーズ1では g2 と gm-* のみ有効化する
enabled_gates: [g2, gm-lint, gm-format, gm-typecheck, gm-test, gm-security]

model_selection: static           # v2 で bandit(タスク複雑度ベースの動的選択)を予約

question_routing:
  task-question: issue-comment    # 起票者へ。回答で issue 本文を更新
  axis-question: contract-pr      # 契約ファイル変更 PR として起票。人間が承認
```

### experiment プロファイルとの差分

experiment.yaml と development.yaml の差分は次の3点のみで、ゲート機構、verdict、ルーティングは共通である。

- phases の名称(課題定義→実験計画→実行→分析→報告)
- `exit_criteria_required` の中身(評価指標、データセット、seed)
- G2 必須欄(実験条件、データ版数)

### language pack の providers.yaml

デフォルトのツール選定は lint = Ruff、整形 = Black、型 = basedpyright、テスト = pytest とする。
対象リポジトリは repo override でコマンドを変更できる。

```yaml
# packs/python/providers.yaml
detect: ["pyproject.toml"]
providers:
  lint:
    command: "uv run ruff check --output-format sarif --output-file ruff.sarif ."
    output: sarif
    output_file: ruff.sarif
  format:
    command: "uv run black --check ."
    output: exit-code
  typecheck:
    command: "uv run basedpyright --outputjson > basedpyright.json"
    output: json
    output_file: basedpyright.json
    normalizer: normalizers/basedpyright_json_to_sarif.py   # pyright JSON → SARIF 変換
  test:
    command: "uv run pytest --junitxml=pytest-junit.xml"
    output: junit
    output_file: pytest-junit.xml
  security:
    action: "anthropics/claude-code-security-review"  # GitHub Action(OPERATIONS.md)
    output: pr-comment
```

契約スキーマのうち `templates:`、`enabled_gates:`、`exit_criteria_fields:`、`criteria_skills:` の4キーは実装時の追加である。
`templates:` は必須欄をテンプレ生成と門前払いの両方から参照させるため(単一ソース原則の実装)、`enabled_gates:` は段階導入のため、`exit_criteria_fields:` は experiment の打ち切り基準欄を機械チェックするため、`criteria_skills:` はゲート判定基準に導入先プロジェクトの skill を加えるために足した。

## issue テンプレート仕様

契約 YAML から `/tasuki:loop-init` が生成する。

| テンプレ | 必須欄 |
|---|---|
| 親 issue | 背景 / 目的 / 価値 / 予算(コスト上限) / 完了の定義 |
| 子 issue | 対応する親要件 / 目的 / 受け入れ条件 / 成功基準 / 打ち切り条件 / 予算(max_iterations) / 実験条件(experiment のみ。データ、環境、パラメータ、seed) |
| レポート | 要件 ID ⇔結果の対応表 / 結論 / 再現手順(コマンドと環境) / 生データへのリンク |
| PR 本文 | 概要 / 変更点 / 影響範囲と revert 可否 / 対応 issue / 検証方法 |

必須欄の空チェックが G2 の門前払いに直結する。

## 質問ルーティング

質問には寿命があり、寿命が宛先を決める。

| 型 | 寿命 | 例 | 宛先 | 動作 |
|---|---|---|---|---|
| `task-question` | タスクと共に終わる | 再現手順、仕様の細部 | issue 起票者 | issue コメントで質問し、回答を issue 本文に反映して再開 |
| `axis-question` | タスク後も生きる | 判断原則、設計方針、待ち位置の定義変更 | 契約ファイル | 契約 YAML への変更 PR として起票。人間の承認後に反映 |

起票者の回答でプロジェクトの原則が書き換わることは権限昇格であり、一人運用でも axis-question を issue コメントで即答させない。
原則の変更は必ずバージョン管理された契約 PR を経由する。
軸の欠落(待ち位置が未定義)はブロッキング、原則の改善提案は非ブロッキング(進めつつ PR を非同期起票)とする。

## 初期 fixture の手書き(必須)

契約の `waiting_level` や `too_*_signals` は自然言語の抽象であり、書いた人間と読む gate-reviewer の「目盛り」は最初必ずズレている。
抽象的な基準は具体例とセットでないと伝わらない。
そこで `/tasuki:loop-init` の推奨手順として、運用開始前に判定例 fixture を5件程度手書きする(「この子 issue は PASS のはず」「これは TOO_ABSTRACT のはず」)。
これは回帰テスト([OPERATIONS.md](OPERATIONS.md))の初期データであると同時に、契約作成者とレビュアーの目盛り合わせそのものである。
