---
description: tasuki のブートストラップ。言語検出、プロジェクト資産の棚卸し、契約プロファイル配置、issue / PR テンプレ生成、CI workflow 生成、ラベル作成を行う
argument-hint: "[development | experiment]"
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Write, Edit, Bash(gh *), Bash(git *)
---

# /tasuki:loop-init

対象リポジトリに tasuki ループの前提をすべて生成する。
providers.yaml と契約プロファイルが単一ソースであり、以下で生成するテンプレートと CI はその射影である(手で二重管理しない)。

## 前提チェック(失敗したら中断して報告)

1. git リポジトリであり、GitHub リモート(origin)があること
2. `gh auth status` が通ること。token に `workflow` scope があること(`.github/workflows/` への push に必須。なければ `gh auth refresh -s workflow` を案内)
3. `gh --version` を確認する。2.94.0 未満なら sub-issues / issue dependencies は `gh api` フォールバックになる旨を記録する

## 手順

### 1. 言語検出

`pyproject.toml` があれば python pack(`packs/python/providers.yaml`)を選択する。
検出できない言語の場合は、v1 は python のみ対応であることを伝えて中断する。

### 2. プロジェクト資産の棚卸し

`.claude/agents/`、`.claude/skills/`、CLAUDE.md、導入済み plugin を走査する。

- レビュアー系 agent があれば、契約 YAML の `reviewer:` への割り当て候補として提案する
- lint / typecheck / test / security 系のコマンドを提供する plugin があれば、provider 登録候補として提案する
- **Stop hook でセッションを回すループ系 plugin(ralph-wiggum 等)を検出したら、二重ループになるため併用禁止と警告する**

採用結果は手順3の repo override に書き込む。

### 3. 契約プロファイルの配置

引数(`$ARGUMENTS`)または対話で development / experiment を選び、plugin の `profiles/<選択>.yaml` を `.claude/loop/profile.yaml` にコピーする。
以後このリポジトリでの契約の正は `.claude/loop/profile.yaml` であり、上書きできるのはコマンド、閾値、待ち位置定義のみ。
あわせて pack の normalizer を `.claude/loop/normalizers/` にコピーする(CI から実行するため)。

### 4. issue / PR テンプレートの生成

`.claude/loop/profile.yaml` の `templates:` セクションから生成する(プロファイルの必須欄と一字一句対応させる)。

- `.github/ISSUE_TEMPLATE/loop-parent.md`：`parent_issue_required_fields` の各項目を `## 見出し` にする
- `.github/ISSUE_TEMPLATE/loop-child.md`：`child_issue_required_fields` の各項目を `## 見出し` にする
- `.github/pull_request_template.md`：`pr_required_fields` の各項目を `## 見出し` にする

見出し直下が空のままの issue は G2 の門前払いで差し戻される(この空チェックが機能するよう、見出し文字列を profile と一致させること)。

### 5. CI workflow の生成

providers.yaml の各 provider から `.github/workflows/loop-gates.yml` を生成する。
次のテンプレートを基に、コマンド部分を providers.yaml の値で埋める。

```yaml
name: loop-gates
on:
  pull_request:
    paths-ignore: ["docs/**", "**.md"]
concurrency:
  group: loop-gates-${{ github.head_ref }}
  cancel-in-progress: true
permissions:
  contents: read
  pull-requests: write
  security-events: write
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with: { enable-cache: true }
      - run: uv sync --frozen
      - run: <providers.lint.command>
      - if: always()
        uses: github/codeql-action/upload-sarif@v3
        with: { sarif_file: <providers.lint.output_file>, category: lint }
  typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with: { enable-cache: true }
      - run: uv sync --frozen
      - run: <providers.typecheck.command>
        continue-on-error: true
      - run: python .claude/loop/normalizers/mypy_junit_to_sarif.py <providers.typecheck.output_file> mypy.sarif
      - if: always()
        uses: github/codeql-action/upload-sarif@v3
        with: { sarif_file: mypy.sarif, category: typecheck }
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: astral-sh/setup-uv@v5
        with: { enable-cache: true }
      - run: uv sync --frozen
      - run: <providers.test.command>
      - name: test-tampering check   # 観点 #18
        run: |
          git diff origin/${{ github.base_ref }}...HEAD -- 'tests/' '**/test_*.py' '**/*_test.py' > /tmp/test.diff
          if grep -E '^\-.*def test_' /tmp/test.diff; then
            echo '::error::既存テストの削除を検出。仕様と矛盾する場合は task-question にすること'; exit 1
          fi
          if grep -E '^\+.*(pytest\.mark\.skip|unittest\.skip)' /tmp/test.diff; then
            echo '::error::テストの skip 追加を検出'; exit 1
          fi
      - name: lockfile-diff check    # 依存追加の検知
        run: |
          if ! git diff --quiet origin/${{ github.base_ref }}...HEAD -- uv.lock; then
            echo '::warning::依存の変更を検出(uv.lock)。PR 本文の変更点に理由があるか確認'
          fi
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 2 }
      - uses: anthropics/claude-code-security-review@main
        with:
          claude-api-key: ${{ secrets.CLAUDE_API_KEY }}
          comment-pr: true
  notify-success:                    # 沈黙と故障を区別するため成功も通知する(観点 #17)
    needs: [lint, typecheck, test, security]
    runs-on: ubuntu-latest
    steps:
      - env:
          GH_TOKEN: ${{ github.token }}
        run: gh pr comment ${{ github.event.pull_request.number }} --repo ${{ github.repository }} --body "loop-gates: all green ✅"
```

生成時の注意:

- 依存キャッシュ、並列 job、paths-ignore は削らない(PR ゲートを5〜10分以内に保つ、観点 #17)
- `CLAUDE_API_KEY` secret が未設定なら、設定手順を伝える(secrets は CI 環境にのみ置く、観点 #15)
- security-review Action はプロンプトインジェクション対策がないため、信頼できる PR(自リポジトリの worker 生成 PR)のみを対象とする。外部コントリビューションを受けるリポジトリでは workflow 実行に承認を必須とするよう案内する

### 6. ラベル作成

`gh label create` で作成する(既存なら skip、冪等)。

- `gate:g0-passed` 〜 `gate:g4-passed`(通過)
- `gate:g0-returned` 〜 `gate:g4-returned`(差し戻し中)
- `loop:in-progress`(worker 割り当て済み)
- `loop:triage`(人間の裁定待ち)

### 7. バジェット確認と fixture の案内

`.claude/loop/profile.yaml` の budgets(`max_iterations_per_gate` / `max_inner_loop` / `wip_limit_prs`)をユーザーに提示し、必要なら調整する。
最後に、運用開始前の必須手順として初期 fixture 5件の手書きを案内する(`tasuki:baton-contract` skill の手順、置き場所は `.claude/loop/fixtures/`)。

## 完了報告

生成・変更したファイルの一覧と、未完了の手動作業(secret 設定、fixture 手書き)を分けて報告する。
