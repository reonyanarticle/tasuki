---
description: tasuki のブートストラップ。言語検出、プロジェクト資産の棚卸し、契約プロファイル配置、issue / PR テンプレ生成、CI workflow 生成、ラベル作成を行う
argument-hint: "[development | experiment]"
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Write, Edit, Bash(gh *), Bash(git *), Bash(uv *)
---

# /tasuki:loop-init

対象リポジトリに tasuki ループの前提をすべて生成する。
providers.yaml と契約プロファイルが単一ソースであり、以下で生成するテンプレートと CI はその射影である(手で二重管理しない)。

## 前提チェック(失敗したら中断して報告)

1. git リポジトリであり、GitHub リモート(origin)があること
2. `gh auth status` が通ること。Git operations protocol を確認し、**https の場合のみ** token の `workflow` scope を必須とする(OAuth token での HTTPS push は scope が無いと `.github/workflows/` を拒否される。SSH 鍵での push には不要。https で scope が無ければ `gh auth refresh -s workflow` を案内)
3. `gh --version` を確認する。2.94.0 未満なら sub-issues / issue dependencies は `gh api` フォールバックになる旨を記録する

## 手順

### 1. 言語検出と依存の整備

`pyproject.toml` があれば python pack(`packs/python/providers.yaml`)を選択する。
検出できない言語の場合は、v1 は python のみ対応であることを伝えて中断する。
pack の前提ツール(ruff / black / basedpyright / pytest)が dev 依存にあるか確認し、なければ `uv add --dev` での追加を提案する。
`uv.lock` が無ければ `uv lock` で生成し、コミット対象に含める(CI の `uv sync --frozen` は lockfile が無いと全 job が即失敗するため必須)。

### 2. プロジェクト資産の棚卸し

`.claude/agents/`、`.claude/skills/`、CLAUDE.md、導入済み plugin を走査する。

- レビュアー系 agent があれば、契約 YAML の `reviewer:` への割り当て候補として提案する(orchestrator はメインセッションなので、導入先プロジェクトの agent をそのまま呼べる)
- ゲート判定基準に使えそうな skill があれば、契約 YAML の `criteria_skills:` への登録候補として提案する
- lint / typecheck / test / security 系のコマンドを提供する plugin があれば、provider 登録候補として提案する
- **Stop hook でセッションを回すループ系 plugin(ralph-wiggum 等)を検出したら、二重ループになるため併用禁止と警告する**
- **worker からプロジェクト agent への委譲(任意)**：導入先の `.claude/settings.json` の `env` に `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=2` を設定すると、worker セッションからプロジェクトの subagent を呼べるようになる。既定では subagent は別の subagent を起動できないため、この設定はユーザーの明示承認を得てから書き込む(未設定でもループは動作する。その場合プロジェクト agent を使えるのは orchestrator だけ)

採用結果は手順3の repo override に書き込む。

### 3. 契約プロファイルの配置

引数(`$ARGUMENTS`)または対話で development / experiment を選び、plugin の `profiles/<選択>.yaml` を `.tasuki/profile.yaml` にコピーする。
以後このリポジトリでの契約の正は `.tasuki/profile.yaml` であり、上書きできるのはコマンド、閾値、待ち位置定義、reviewer / criteria_skills の割り当てのみ。
あわせて pack の normalizer を `.tasuki/normalizers/` にコピーする(CI から実行するため)。

### 4. issue / PR テンプレートの生成

`.tasuki/profile.yaml` の `templates:` セクションから生成する(プロファイルの必須欄と一字一句対応させる)。

- `.github/ISSUE_TEMPLATE/loop-parent.md`：`parent_issue_required_fields` の各項目を `## 見出し` にする
- `.github/ISSUE_TEMPLATE/loop-child.md`：`child_issue_required_fields` の各項目を `## 見出し` にする
- `.github/pull_request_template.md`：`pr_required_fields` の各項目を `## 見出し` にする

見出し直下が空のままの issue は門前払いで差し戻される(親 issue はループ起動時、子 issue は G2 前。この空チェックが機能するよう、見出し文字列を profile と一致させること)。

### 5. CI workflow の生成

security job は **オプトイン(既定では生成しない)**。
ユーザーに導入するか確認してから生成する。
security job(`anthropics/claude-code-security-review` Action)は Anthropic API キー(`CLAUDE_API_KEY` secret)で Claude API を直接呼ぶため、**Claude Code の契約とは別の API 課金**が発生する(ループ本体の orchestrator / reviewer / worker はユーザーの Claude Code セッションで動き、API キーを使わない)。

- **既定(オプトインしない)**：security job を生成しない。GM は lint / format / typecheck / test の4ゲート。`notify-success` の `needs` にも入れない
- **オプトインした場合**：security job を含めて生成し、`gh secret set CLAUDE_API_KEY` を案内し、`.tasuki/profile.yaml` の `enabled_gates` に `gm-security` を追加する

job を残して条件スキップする形は使わない(スキップは成功に見え、素通りが緑になるため)。

providers.yaml の各 provider から `.github/workflows/loop-gates.yml` を生成する。
次のテンプレートを基に、コマンド部分を providers.yaml の値で埋める。

```yaml
name: loop-gates
on:
  pull_request:
concurrency:
  group: loop-gates-${{ github.head_ref }}
  cancel-in-progress: true
permissions: {}                    # 既定は無権限。job ごとに最小権限を付与する
jobs:
  lint:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write       # SARIF アップロードのみ
    steps:
      - uses: actions/checkout@v4
        with: { persist-credentials: false }
      - uses: astral-sh/setup-uv@v5
        with: { enable-cache: true }
      - run: uv sync --frozen
      - run: <providers.lint.command>
      - if: always()
        uses: github/codeql-action/upload-sarif@v3
        with: { sarif_file: <providers.lint.output_file>, category: lint }
  format:
    runs-on: ubuntu-latest
    permissions: { contents: read }
    steps:
      - uses: actions/checkout@v4
        with: { persist-credentials: false }
      - uses: astral-sh/setup-uv@v5
        with: { enable-cache: true }
      - run: uv sync --frozen
      - run: <providers.format.command>
  typecheck:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
    steps:
      - uses: actions/checkout@v4
        with: { persist-credentials: false }
      - uses: astral-sh/setup-uv@v5
        with: { enable-cache: true }
      - run: uv sync --frozen
      - run: <providers.typecheck.command>
        continue-on-error: true    # 失敗の判定は下の gate ステップが行う
      - run: python .tasuki/normalizers/basedpyright_json_to_sarif.py <providers.typecheck.output_file> basedpyright.sarif
      - if: always()
        uses: github/codeql-action/upload-sarif@v3
        with: { sarif_file: basedpyright.sarif, category: typecheck }
      - name: typecheck gate
        # jq -e により、summary が欠けた JSON・空ファイル・欠損ファイルはすべて job 失敗になる(fail-closed)
        run: |
          errors="$(jq -er '.summary.errorCount' <providers.typecheck.output_file>)"
          test "$errors" -eq 0
  test:
    runs-on: ubuntu-latest
    permissions: { contents: read }
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0, persist-credentials: false }
      - uses: astral-sh/setup-uv@v5
        with: { enable-cache: true }
      - run: uv sync --frozen
      - run: <providers.test.command>
      - name: test-tampering check   # 観点 #18。機械検知できる範囲: 削除・skip/xfail・設定による除外
        run: |
          base="origin/${{ github.base_ref }}"
          git diff "$base"...HEAD -- 'tests/' '**/test_*.py' '**/*_test.py' > /tmp/test.diff
          if grep -E '^\-.*def test_' /tmp/test.diff; then
            echo '::error::既存テストの削除を検出。仕様と矛盾する場合は task-question にすること'; exit 1
          fi
          if grep -E '^\+.*(pytest\.mark\.(skip|xfail)|unittest\.skip|importorskip)' /tmp/test.diff; then
            echo '::error::テストの skip / xfail 追加を検出'; exit 1
          fi
          git diff "$base"...HEAD -- pyproject.toml pytest.ini setup.cfg conftest.py > /tmp/conf.diff
          if grep -E '^\+.*(addopts|--deselect|--ignore|collect_ignore|\[tool\.basedpyright\]|typeCheckingMode)' /tmp/conf.diff; then
            echo '::error::テスト・型チェック設定の変更を検出。設定変更は機能開発と分離した PR で人間承認を得ること'; exit 1
          fi
      - name: lockfile-diff check    # 依存追加の検知(警告のみ・非ブロック)
        run: |
          if ! git diff --quiet "origin/${{ github.base_ref }}"...HEAD -- uv.lock; then
            echo '::warning::依存の変更を検出(uv.lock)。PR 本文の変更点に理由があるか確認'
          fi
  security:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write         # PR コメント形式の結果出力に必要。この job は PR のコードを実行しない
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 2, persist-credentials: false }
      # 生成時に最新リリースのコミット SHA を解決して固定する(@main 等の可変参照は使わない)
      - uses: anthropics/claude-code-security-review@<コミット SHA>
        with:
          claude-api-key: ${{ secrets.CLAUDE_API_KEY }}
          comment-pr: true
  notify-success:                  # 沈黙と故障を区別するため成功も通知する(観点 #17)
    needs: [lint, format, typecheck, test, security]
    runs-on: ubuntu-latest
    permissions: { pull-requests: write }
    steps:
      - env:
          GH_TOKEN: ${{ github.token }}
        run: gh pr comment ${{ github.event.pull_request.number }} --repo ${{ github.repository }} --body "loop-gates: all green ✅"
```

生成時の注意:

- **paths-ignore は使わない**。ドキュメントのみの PR でも全 job を走らせる。job を丸ごとスキップすると check-run が1件も作られず、orchestrator の GM 判定が「失敗なし=通過」に倒れる fail-open になるため(速度は依存キャッシュと並列 job で確保する。観点 #17)
- **checkout は全 job で `persist-credentials: false`**。既定値 true は GITHUB_TOKEN を .git/config に残し、PR 由来のコード(ビルドフック、conftest.py)から読めてしまう
- **permissions は workflow 既定を `{}` にし、job ごとに最小付与**。PR のコードを実行する job(lint / format / typecheck / test)には `pull-requests: write` を与えない。`security-events: write` は SARIF アップロードに必要な最小権限として lint / typecheck にのみ与える
- **security Action はコミット SHA に固定**する(生成時に `gh api` でリリースの SHA を解決)。ブランチ・タグ参照は差し替え可能で supply-chain リスクになる
- `CLAUDE_API_KEY` secret が未設定なら、設定手順を伝える(secrets は CI 環境にのみ置く、観点 #15)
- security-review Action はプロンプトインジェクション対策がないため、信頼できる PR(自リポジトリの worker 生成 PR)のみを対象とする。fork からの PR には secrets が渡らず security job は失敗する。外部コントリビューションを受けるリポジトリでは workflow 実行に承認を必須とするよう案内する
- **branch protection の提案**：required status checks を default branch に設定するかユーザーに確認する。対象は実際に生成した job に合わせる(既定は lint / format / typecheck / test。security はオプトイン時のみ加える。生成していない job を required にすると check が永遠に報告されず全 PR がマージ不能になる)。未設定の場合、CI の判定はマージを強制しない(orchestrator の読み取りと人間の目視だけになる)

### 6. ラベル作成

`gh label create` で作成する(既存なら skip、冪等)。

- `gate:g0-passed` 〜 `gate:g4-passed`(通過)
- `gate:g0-returned` 〜 `gate:g4-returned`(差し戻し中)
- `loop:in-progress`(worker 割り当て済み)
- `loop:pr`(ループ由来 PR の識別。WIP 制限の集計対象)
- `loop:triage`(人間の裁定待ち)

### 7. バジェット確認と fixture の案内

`.tasuki/profile.yaml` の budgets(`max_iterations_per_gate` / `max_inner_loop` / `wip_limit_prs`)をユーザーに提示し、必要なら調整する。
最後に、運用開始前の必須手順として初期 fixture 5件の手書きを案内する(`tasuki:baton-contract` skill が手順。置き場所は `.tasuki/fixtures/`)。

## 完了報告

生成・変更したファイルの一覧と、未完了の手動作業(secret 設定、branch protection、fixture 手書き、spawn depth 設定)を分けて報告する。
