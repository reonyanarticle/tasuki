# 契約スキーマとテンプレート

契約(プロファイル YAML)は単一ソースであり、issue / PR テンプレートと CI workflow はその射影である(二重管理をしない)。

## プロファイル YAML

```yaml
# profiles/development.yaml
profile: development
budgets:
  max_iterations_per_gate: 3      # 超過で人間にエスカレーション
  max_inner_loop: 5               # verifier の打ち切り上限デフォルト
  wip_limit_prs: 3                # 人間のマージ待ちの ready 親 PR の上限(観点「スループット管理」)。超過で新規 worker 起動を停止
  stale_assignment_minutes: 60    # 停止した実行が残した assignee の回収までの経過時間(観点「並行整合性」)

# モデルは agent 定義に固定されている(worker と verifier と decomposer = sonnet)。gate-reviewer のモデルは orchestrator が起動ごとに指定する。
# reviewer の差し替えは gates[].reviewer に導入先プロジェクトの agent 名を指定する。

worker_agent: tasuki-worker       # maker の差し替えキー

phases:
  - name: requirements            # 親 issue
    hands_off:
      to: decomposition
  - name: decomposition
    receives:
      from: requirements
      waiting_level: "背景・目的・価値・予算が記載され、解き方は未指定"
      too_abstract_signals: ["価値の記載なし", "予算欄が空", "実現可能性の前提(必要なデータ、環境、権限)が読み取れない", "完了の定義が1回のレビューで判断できる範囲を超えている(項目過多、独立な価値の同居)"]
      too_concrete_signals: ["子タスクの実装方式まで指定"]
    hands_off:
      to: implementation
  - name: implementation
    receives:
      from: decomposition
      waiting_level: "受け入れ条件つきで単独マージ可能な単位。実装方式は未指定"
      too_abstract_signals: ["曖昧語(適切に・柔軟に等)", "受け入れ条件の欠落", "打ち切り条件の欠落", "『常に分ける』組み合わせの同居(リファクタリングと機能追加等)", "前提(必要なデータ、環境、権限)の記載なし", "非機能要件(性能・速度・実行コスト等)が該当するのに測定可能な基準として書かれていない", "評価や測定を伴う子で、評価データの分離(dev/test)と統制条件(seed、データ版数、環境)が該当するのに測定可能な形で書かれていない"]
      too_concrete_signals: ["特定ライブラリ・実装方式の指定(検証の統制条件(対象の固定、比較条件、コマンドのフラグ等)は要件でありここに含めない)"]
    hands_off:
      to: report
      exit_criteria_required: true
  - name: report
    receives:
      from: implementation
      waiting_level: "要件⇔結果の対応表と結論。生データは添付リンクのみ"
      too_abstract_signals: ["対応表なし", "結論なし", "再現手順の欠落", "期待値の根拠(仕様由来)の記載なし", "評価の数字を報告しているのに由来セット(dev/test)が不明"]
      too_concrete_signals: ["生ログ・生データの本文貼り付け", "secrets・個人情報の掲載"]
    hands_off:
      to: integration
  - name: integration             # 全子完了→親。統合ゲートが照合する昇りの最終待ち位置
    receives:
      from: report
      waiting_level: "全親要件⇔子成果の対応が明示され、孤児の親要件が無い"
      too_abstract_signals: ["親要件の孤児(対応する子成果なし)", "対応の明示なし"]
      too_concrete_signals: ["子レポートの生転載"]

templates:                        # issue テンプレの必須欄(着手ゲートの門前払いの機械チェック対象)
  # 各欄の意味は実プロファイルの欄コメントが定める(loop-report skill と gate-reviewer はそこから引く。
  # 欄の解釈を skill や agent 定義に写さない)
  parent_issue_required_fields: [背景, 目的, 価値, 予算(コスト上限), 完了の定義]
  child_issue_required_fields: [対応する親要件, 目的, 受け入れ条件, 成功基準, 打ち切り条件, 予算(max_iterations)]
  report_required_fields: [要件⇔結果の対応表, 結論, 期待値の根拠, 再現手順, 生データへのリンク, 参照した skill と委譲した subagent]
  pr_required_fields: [概要, 対応する親要件, 受け入れ条件の充足, 変更点, 影響範囲と revert 可否, 対応 issue, 検証方法]
  parent_pr_required_fields: [何が変わるか, 承認してほしい判断, やらなかったこと, リスクと戻し方, 対応 issue]

# 分割基準(decomposer と分割ゲートが従う。プロファイルごとの基準の違いを契約が持ち、手順書と agent 定義に写さない)
split_criteria:
  good_task_conditions: [単独でマージして壊れない, テストを同梱できる, 単独で revert できる, 一読で理解できる]
  always_separate: [リファクタリングと機能追加, 測定と測定対象の変更(実験と基盤変更), ライブラリ更新と機能開発, 性能改善と機能開発, データ移行と機能開発, feature flag の各段階(add → enable → remove), 相互に依存しない機能同士]

gates:
  - id: intake
    kind: abstraction
    phase: decomposition      # 親 issue をどのフェーズへ渡すかを検める
    reviewer: gate-reviewer       # 外部 subagent 名に差し替え可能
    model: opus                   # 低頻度・高レバレッジ
  - id: split
    kind: abstraction
    phase: implementation
    reviewer: gate-reviewer
    model: opus
    set_signals:                  # 分割の集合レベル基準(分割ゲート固有)
      - 依存の循環
      - 親要件の孤児(どの子 issue にも対応しない)
      - 親予算(コスト上限)との不整合(子件数・反復数の合計超過)
  - id: start
    kind: abstraction
    phase: implementation
    reviewer: gate-reviewer
    model: haiku                  # 高頻度・照合型
    escalate_to: sonnet           # low-confidence PASS / 差し戻し2連続で昇格
    preflight: template-fields    # 門前払い(機械チェック)
    criteria_skills: []           # 判定基準に加える導入先プロジェクトの skill 名(任意)
  - id: checks-lint
    kind: mechanical
    provider: lint                # pack の providers.yaml を参照
    blocking_threshold: error     # SARIF level
  - id: checks-format
    kind: mechanical
    provider: format              # exit-code 判定(black --check)
  - id: checks-typecheck
    kind: mechanical
    provider: typecheck
    blocking_threshold: error
  - id: checks-test
    kind: mechanical
    provider: test                # JUnit XML: failures == 0
  - id: checks-security
    kind: mechanical
    provider: security            # providers.yaml のキーと一致させる
    blocking_threshold: high
  - id: outcome
    kind: abstraction
    phase: report
    reviewer: gate-reviewer
    model: sonnet
    escalate_to: opus
    preflight: report-fields      # 門前払い(report_required_fields の機械チェック)
    criteria_skills: []
  - id: integration
    kind: abstraction
    phase: integration
    reviewer: gate-reviewer
    model: opus

# 有効にするゲート。ここに無いゲートは判定しない(段階導入の履歴は ROADMAP.md)
# checks-security はオプトイン(/tasuki:loop-init で選択時に追加。API キー課金が別途発生)
enabled_gates: [intake, split, start, outcome, integration, checks-lint, checks-format, checks-typecheck, checks-test]

preship_review:                   # 出荷前レビュー(loop.md 3c)のコスト制御
  mode: scaled                    # full = 常に観点別5セッション / scaled = diff 規模で自動選択 / manual = 人間が起動
  fanout_threshold_lines: 200     # scaled のとき、観点別に分ける diff 行数の閾値

model_selection: static           # v2 で bandit(タスク複雑度ベースの動的選択)を予約

question_routing:
  task-question: issue-comment    # 起票者へ。回答で issue 本文を更新
  axis-question: contract-pr      # 契約ファイル変更 PR として起票。人間が承認
```

`worker_agent:` は maker の差し替えキーである(既定 `tasuki-worker`。INTEGRATION.md の worker 差し替えはこのキーで行う)。

### language pack の providers.yaml

デフォルトのツール選定は lint = Ruff、整形 = Black、型 = basedpyright、テスト = pytest とする。
対象リポジトリは repo override でコマンドを変更できる。

repo override(`.tasuki/profile.yaml`)で変えてよいのは、コマンド、閾値、待ち位置定義、reviewer / criteria_skills の割り当て、そして**必須欄(`templates`)の追加**である。
必須欄の追加は、その導入先で毎回問いかけたい欄をテンプレと門前払いに持ち込む手段である(実験を常時行うリポジトリが「実験条件(データ、環境、パラメータ、seed)」と「評価データの分離(dev/test)」を子の必須欄に足す、など)。
欄の削除は行わない(ゲートの判定材料が消える)。
**仕事の型ごとに plugin 側の雛形を増やさないのは、型がリポジトリ単位ではなく issue 単位の性質だからである**(経緯は [ROADMAP.md](ROADMAP.md) の experiment 廃止の記録)。

pack は `providers` のほかに、生成物の一覧(`artifacts`)と CI 生成に使う定義(`ci`: セットアップ手順、normalizer の実行系、lockfile、改変検知の対象パス)を持つ。
以下は `providers` 部分の抜粋である(全体は packs/python/providers.yaml が正)。

```yaml
# packs/python/providers.yaml(抜粋)
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

契約スキーマのうち `templates:`、`enabled_gates:`、`criteria_skills:`、`set_signals:`、`phase:`、`preship_review:`、`stale_assignment_minutes:`、`worker_agent:`、`split_criteria:` は実装時の追加である。
`templates:` は必須欄をテンプレ生成と門前払いの両方から参照させるため(単一ソース原則の実装)、`enabled_gates:` は段階導入のため、`criteria_skills:` はゲート判定基準に導入先プロジェクトの skill を加えるため、`set_signals:` は分割ゲートの集合レベル基準(循環、孤児、親予算整合)を契約由来にするために足した。`phase:` は各ゲートが検める受け渡し先を契約から引くために足した(フェーズ名を手順書に直接書くと、導入先がフェーズを言い換えたときに解決できなくなる)。
`split_criteria:` と欄コメントは、分割基準と欄の意味を契約由来にするために足した(3つ目のプロファイルを試作したとき、プロファイル固有の欄名と判定基準が skill と agent 定義に literal に書かれていたため、プロファイルを1つ足すたびに全レイヤーへ「読み替え節」を足す羽目になった。非契約レイヤーはプロファイル名で分岐せず、契約のキーの有無で分岐する。経緯は ROADMAP.md の撤回の記録に残す)。

## issue テンプレート仕様

契約 YAML から `/tasuki:loop-init` が生成する。

| テンプレ | 必須欄 |
|---|---|
| 親 issue | 背景 / 目的 / 価値 / 予算(コスト上限) / 完了の定義 |
| 子 issue | 対応する親要件 / 目的 / 受け入れ条件 / 成功基準 / 打ち切り条件 / 予算(max_iterations)(導入先が repo override で欄を足してよい) |
| レポート | 要件 ID ⇔結果の対応表 / 結論 / 期待値の根拠 / 再現手順(コマンドと環境) / 生データへのリンク / 参照した skill と委譲した subagent |
| 子 PR 本文 | 概要 / 対応する親要件 / 受け入れ条件の充足 / 変更点 / 影響範囲と revert 可否 / 対応 issue / 検証方法 |
| 親 PR の承認コメント | 何が変わるか / 承認してほしい判断 / やらなかったこと / リスクと戻し方 / 対応 issue(loop.md の 3c-2 が投稿する) |

必須欄の空チェックが着手ゲートの門前払いに直結する。

親の `予算(コスト上限)` と子の `予算(max_iterations)` は、**ループの反復、実行コストの上限**である(loop が暴走しないためのバックストップ)。
一方、その機能や検証そのものに必要な費用や、守るべき性能、速度などの制約(非機能要件)は、`価値` と `受け入れ条件` / `成功基準` に**測定可能な形**で書く。
前者は orchestrator と watchdog が、後者は verifier と着手 / 成果ゲートが照合する(責任の置き場所が異なる)。

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
