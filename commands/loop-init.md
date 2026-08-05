---
description: tasuki のブートストラップ。言語検出、プロジェクト資産の棚卸し、契約プロファイル配置、issue / PR テンプレ生成、CI workflow 生成、ラベル作成を行う
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Write, Edit, Bash(gh --version), Bash(gh auth status:*), Bash(gh label:*), Bash(gh repo view:*), Bash(gh api:*), Bash(gh pr create:*), Bash(git rev-parse:*), Bash(git remote:*), Bash(git status:*), Bash(git log:*), Bash(git config:*), Bash(python3:*), Bash(git checkout:*), Bash(git add:*), Bash(git commit:*), Bash(git push:*), Bash(uv *)
---

# /tasuki:loop-init

対象リポジトリに tasuki ループの前提をすべて生成する。
providers.yaml と契約プロファイルが単一ソースであり、以下で生成するテンプレートと CI はその射影である(手で二重管理しない)。

## 前提チェック(失敗したら中断して報告)

0. **信頼境界の確認(必須)**:tasuki v1 は issue、PR、コメントの内容をすべて信頼できるリポジトリでのみ使う。対象リポジトリが外部からの issue を受け付ける場合(public リポジトリ等)は、未検証テキストが Bash を持つ worker/verifier に流れるため、v2 のハードニング(作者認証、sandbox)が入るまで導入しないよう警告し、ユーザーの明示確認を得てから続行する
1. git リポジトリであり、GitHub リモート(origin)があること
2. `gh auth status` が通ること。Git operations protocol を確認し、**https の場合のみ** token の `workflow` scope を必須とする(OAuth token での HTTPS push は scope が無いと `.github/workflows/` を拒否される。SSH 鍵での push には不要。https で scope が無ければ `gh auth refresh -s workflow` を案内)
3. `gh --version` を確認する。能力ごとに閾値が違うので両方を記録する: **sub-issues と issue dependencies の作成**(`--parent` / `--blocked-by` 等)は 2.94.0 以上、**`--json subIssues` での読み取り**は 2.95.0 以上。満たさない側は `gh api` の GraphQL フォールバックになる(ただし `/tasuki:loop-status` は読み取り専用を保つためフォールバックを持たない)

## 手順

### 1. 言語検出と依存の整備

契約プロファイルは `development` の1つである(仕事の型ごとに雛形を分けない。実験や評価を伴う仕事も同じ契約で回し、必要なら手順3で必須欄を足す)。
**plugin 側のファイル(`profiles/`、`packs/`)は必ず `${CLAUDE_PLUGIN_ROOT}` からの絶対パスで読む**(カレントは導入先リポジトリであり、そこにこれらは存在しない)。
まず、各 pack の `detect` に挙がったファイルが存在すれば、その pack を選択する(v1 の言語 pack は python のみ同梱)。
検出できない言語の場合は、v1 は python のみ対応であることを伝えて中断する。
pack の `providers` が使うツールが dev 依存にあるか確認し、なければ pack の流儀で追加を提案する。
pack の `ci.lockfile` が非 null で、そのファイルが無ければ生成してコミット対象に含める(`ci.setup` の依存解決は lockfile が無いと全 job が即失敗するため必須。`lockfile: null` の pack では何もしない)。

### 2. プロジェクト資産の棚卸し

`.claude/agents/`、`.claude/skills/`、CLAUDE.md、導入済み plugin を走査する。

- レビュアー系 agent があれば、契約 YAML の `reviewer:` への割り当て候補として提案する(orchestrator はメインセッションなので、導入先プロジェクトの agent をそのまま呼べる)
- ゲート判定基準に使えそうな skill があれば、契約 YAML の `criteria_skills:` への登録候補として提案する
- lint / typecheck / test / security 系のコマンドを提供する plugin があれば、provider 登録候補として提案する
- **毎回テンプレが問いかけたい欄があるかをユーザーに確認する**(例: 実験を常時行うリポジトリの「実験条件(データ、環境、パラメータ、seed)」と「評価データの分離(dev/test)」)。挙がった欄は手順3で `templates` に足す。既定の欄で足りるなら足さない
- **Stop hook でセッションを回すループ系 plugin(ralph-wiggum 等)を検出したら、二重ループになるため併用禁止と警告する**
- **worker からプロジェクト agent への委譲**：既定のネスト上限(メインセッションの3階層下まで)の範囲で、worker はプロジェクトの subagent を呼べる。導入先が `.claude/settings.json` の `env` で `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` を `1` にしている場合はネストが無効なので、その旨を伝える(ループは動作する。プロジェクト agent を使えるのが orchestrator だけになる)

採用結果は手順3の repo override に書き込む。

### 3. 契約プロファイルの配置

**既に `.tasuki/` がある場合は、上書きの前に次の4つを行う**(このコマンドは初期化であり、既存の調整を黙って捨てない)。

1. 既存契約の repo override(必須欄の追加、コマンド、閾値、待ち位置定義、reviewer / criteria_skills の割り当て、`enabled_gates`)を**採取して控える**(新しい契約はこの後のコピーで生まれるため、この時点では書き込み先が無い。**コピーの後で控えを再適用する**)
2. 新しい pack に無い `.tasuki/` 配下の旧 pack 生成物を削除する(残すと改変検知の対象からも外れた無監視の残置物になる)
3. 生成し直す workflow から消える job が branch protection の required checks に残っていれば、除去を提案する(残ると check が永遠に報告されず全 PR がマージ不能になる)
4. 走行中(open)の親 issue があれば、完走または close まで待つよう案内する(run は開始時に読んだ契約で最後まで走るため、途中で必須欄が増えると次の run で現在レイヤーの子が一斉に差し戻される)

`${CLAUDE_PLUGIN_ROOT}/profiles/development.yaml` を `.tasuki/profile.yaml` にコピーする(契約プロファイルは1つであり、選択は無い)。
以後このリポジトリでの契約の正は `.tasuki/profile.yaml` である。**上書きしてよい範囲の正は、契約ファイル冒頭のコメントが定める**(必須欄(`templates`)の追加を含む。規則が契約と一緒に導入先へ運ばれる形にしてある)。
**必須欄を足すのは、その仕事の型を毎回テンプレが問いかける形にしたいときに使う**(例: 実験を常時行うリポジトリが子の必須欄に「実験条件(データ、環境、パラメータ、seed)」と「評価データの分離(dev/test)」を足す)。足した欄は門前払いの対象になり、issue テンプレにも現れる。**足した欄には意味を1行の欄コメントとして書く**(ゲートと decomposer は欄の意味をそこから引く。コメントが無いと欄名だけが渡り、空チェックにしか効かない)。
欄を減らすことはしない(ゲートの判定材料が消える)。
あわせて pack に `normalizers/` があれば `${CLAUDE_PLUGIN_ROOT}/packs/<pack>/normalizers/` から `.tasuki/normalizers/` にコピーする(CI から実行するため。checks-local は exit code で判定し、normalizer を実行しない)。
**選んだ pack の `${CLAUDE_PLUGIN_ROOT}/packs/<pack>/providers.yaml` を丸ごと `.tasuki/providers.yaml` へ書き出す**(`providers` だけでなく `ci`(改変検知の pathspec と added_line_pattern、setup、lockfile 等)と `artifacts` を含む。plugin の `packs/<pack>/providers.yaml` は導入先リポジトリに存在しないため、checks-local が「default branch の信頼された版から読む」対象をここに作る。checks-local の改変検知はこのファイルの `ci` から pathspec を引く)。

**最後に、上の手順1で控えた repo override を `.tasuki/profile.yaml` と `.tasuki/providers.yaml` へ再適用する**(採取 → コピー → 再適用の3段目。テンプレート生成より前に行う。後回しにすると、導入先が足した必須欄がテンプレから抜けたまま生成され、次の run の門前払いで全子が差し戻される)。

### 4. issue / PR テンプレートの生成

`.tasuki/profile.yaml` の `templates:` セクションから生成する(プロファイルの必須欄と一字一句対応させる)。

- `.github/ISSUE_TEMPLATE/loop-parent.md`：`parent_issue_required_fields` の各項目を `## 見出し` にする
- `.github/ISSUE_TEMPLATE/loop-child.md`：`child_issue_required_fields` の各項目を `## 見出し` にする。受け入れ条件と成功基準の欄が契約にある場合、その見出し下に AC-1 / SC-1 形式で採番した箇条書きを促すプレースホルダを含める(レポートの対応表と差し戻し履歴を同じ ID で追跡するため。片方の欄しか無い契約では、ある欄だけに適用する)
- `.github/pull_request_template.md`：`pr_required_fields` の各項目を `## 見出し` にする

見出し直下が空のままの issue は門前払いで差し戻される(親 issue はループ起動時、子 issue は着手ゲートの前。この空チェックが機能するよう、見出し文字列を profile と一致させること)。

### 5. CI workflow の生成

security job は **オプトイン(既定では生成しない)**。
ユーザーに導入するか確認してから生成する。
security job(`anthropics/claude-code-security-review` Action)は Anthropic API キー(`CLAUDE_API_KEY` secret)で Claude API を直接呼ぶため、**Claude Code の契約とは別の API 課金**が発生する(ループ本体の orchestrator / reviewer / worker はユーザーの Claude Code セッションで動き、API キーを使わない)。

- **既定(オプトインしない)**：security job を生成しない。形式ゲートは pack の providers が定める(言語 pack なら lint / format / typecheck / test の4ゲート)。`notify-success` の `needs` にも入れない
- **オプトインした場合**：security job を含めて生成し、`gh secret set CLAUDE_API_KEY` を案内し、`.tasuki/profile.yaml` の `enabled_gates` に `checks-security` を追加する

job を残して条件スキップする形は使わない(スキップは成功に見え、素通りが緑になるため)。

providers.yaml の各 provider から `.github/workflows/loop-gates.yml` を生成する。
**pack の providers に存在する provider の job だけを生成する**(テンプレートにある lint / typecheck 等の job は、その provider が無ければ出力しない)。
`notify-success` の `needs` は**実際に生成した job の一覧**から作る(存在しない job を参照すると workflow 全体が invalid になり、0 job のまま緑にも赤にもならない)。
`output: exit-code` の provider は最小の job(checkout → setup → command 実行)として生成する(SARIF や normalizer のステップを持たない)。
**改変検知(`tampering` job)は provider の有無にかかわらず必ず生成し、`notify-success` の `needs` に含める。** pack が持つキーだけを埋める(`test_tampering` を持たない pack では設定改変検知の部分だけを残す)。**値が空リストのキー、またはキー自体を持たないブロックは出力しない**(`git diff -- ` は pathspec が空だと全ファイルを対象にするため、空リストをそのまま展開すると新規ファイルを追加した PR がすべて検知に該当して恒久的に赤になる)。この job は PR のコードを実行しない(checkout と diff のみ)。**検知を provider の job のステップとして埋め込まない**(コードを実行してから検知すると、実行されたコードが base ref や PATH を書き換えて検知を無効化できる)。
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
      - uses: <pack.ci.setup.uses>
        with: <pack.ci.setup.with>
      - run: <pack.ci.setup.install>
      - run: <providers.lint.command>
      - if: always()
        continue-on-error: true    # SARIF 可視化は best-effort(private リポジトリは GHAS なしだと失敗する)。ゲート判定は上の lint コマンドの exit code
        uses: github/codeql-action/upload-sarif@v3
        with: { sarif_file: <providers.lint.output_file>, category: lint }
  format:
    runs-on: ubuntu-latest
    permissions: { contents: read }
    steps:
      - uses: actions/checkout@v4
        with: { persist-credentials: false }
      - uses: <pack.ci.setup.uses>
        with: <pack.ci.setup.with>
      - run: <pack.ci.setup.install>
      - run: <providers.format.command>
  typecheck:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
    steps:
      - uses: actions/checkout@v4
        with: { persist-credentials: false }
      - uses: <pack.ci.setup.uses>
        with: <pack.ci.setup.with>
      - run: <pack.ci.setup.install>
      - run: <providers.typecheck.command>
        continue-on-error: true    # 失敗の判定は下の gate ステップが行う
      - run: <pack.ci.normalizer_runtime> .tasuki/<providers.typecheck.normalizer> <providers.typecheck.output_file> <pack.ci.sarif_file.typecheck>
      - if: always()
        continue-on-error: true    # 同上。ゲート判定は下の typecheck gate ステップ
        uses: github/codeql-action/upload-sarif@v3
        with: { sarif_file: <pack.ci.sarif_file.typecheck>, category: typecheck }
      - name: typecheck gate
        # jq -e により、summary が欠けた JSON・空ファイル・欠損ファイルはすべて job 失敗になる(fail-closed)
        run: |
          errors="$(<pack.ci.blocking_count.typecheck> <providers.typecheck.output_file>)"
          test "$errors" -eq 0
  tampering:                         # 改変検知は PR のコードを一切実行しない独立 job で行う
    # 同じ job でリポジトリのコードを実行してから検知すると、実行されたコード(テストランナーが
    # 収集時に読み込む設定ファイル等)が base ref や PATH を書き換えて検知自体を無効化できる。
    # checkout と diff だけの job にする。base はこの job 自身の checkout(fetch-depth: 0)が
    # 取得した origin/<base> を使う(runner は使い捨てで、この ref は checkout 由来の新鮮な値である。
    # 追加の git fetch を書いてはならない: persist-credentials: false のため checkout 後の
    # 認証は無く、private リポジトリでは fetch が必ず失敗して全 PR がマージ不能になる)。
    runs-on: ubuntu-latest
    permissions: { contents: read }
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0, persist-credentials: false }
      # 生成時: pack が値を持たないキー(空リストや欠落)のブロックは**出力しない**。
      # `git diff -- ` は pathspec が空だと全ファイルを対象にするため、空リストのまま
      # 出力すると「ファイルを1つでも追加した PR」がすべて検知に該当して恒久的に赤になる。
      - name: tampering check        # 観点「テストの信頼性」。機械検知できる範囲: 削除・skip/xfail・設定による除外
        env:
          BASE_REF: ${{ github.base_ref }}   # ${{ }} を run に直接展開しない(スクリプト注入対策)
        run: |
          base="origin/$BASE_REF"
          git diff "$base"...HEAD -- <pack.ci.test_tampering.paths> > /tmp/test.diff
          if grep -E '^\-.*def test_' /tmp/test.diff; then
            echo '::error::既存テストの削除を検出。仕様と矛盾する場合は task-question にすること'; exit 1
          fi
          if grep -E "^\+.*(<pack.ci.test_tampering.added_line_pattern>)" /tmp/test.diff; then
            echo '::error::テストの skip / xfail 追加を検出'; exit 1
          fi
          # 検査設定ファイルの新規追加は一律で差し戻す(対象は pack が持つ)
          if git diff --name-status "$base"...HEAD -- <pack.ci.new_config_files> | grep -qE '^A'; then
            echo '::error::検査設定ファイルの新規追加を検出。設定変更は機能開発と分離した PR で人間承認を得ること'; exit 1
          fi
          # 既存の設定ソースのうち、チェックを無効化する変更のみ検出する(依存追加など無害な変更は通す)。
          # --diff-filter=M で「既存ファイルの改変」に限る。新規追加を含めると、ガバナンス
          # ファイルを作るブートストラップ PR 自身がこの検知に一致して赤になる。
          git diff --diff-filter=M "$base"...HEAD -- <pack.ci.config_tampering.paths> > /tmp/conf.diff
          if grep -E "^\+.*(<pack.ci.config_tampering.added_line_pattern>)" /tmp/conf.diff; then
            echo '::error::lint / 型 / テストの無効化につながる設定変更を検出。設定変更は機能開発と分離した PR で人間承認を得ること'; exit 1
          fi
  test:
    runs-on: ubuntu-latest
    permissions: { contents: read }
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0, persist-credentials: false }
      - uses: <pack.ci.setup.uses>
        with: <pack.ci.setup.with>
      - run: <pack.ci.setup.install>
      - run: <providers.test.command>
      # 生成時: pack の ci.lockfile が null の場合、この lockfile-diff check ステップは出力しない
      # (空の pathspec は git が全ファイルを対象にするため、差分のある全 PR で警告が出続ける)
      - name: lockfile-diff check    # 依存追加の検知(警告のみ・非ブロック)
        env:
          BASE_REF: ${{ github.base_ref }}
        run: |
          if ! git diff --quiet "origin/$BASE_REF"...HEAD -- <pack.ci.lockfile>; then
            echo '::warning::依存の変更を検出(lockfile)。PR 本文の変更点に理由があるか確認'
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
      - id: review
        uses: anthropics/claude-code-security-review@<コミット SHA>
        with:
          claude-api-key: ${{ secrets.CLAUDE_API_KEY }}
          comment-pr: true
      - name: security gate      # 閾値以上の findings で job を落とす(コメントを出すだけにしない)
        env:
          # 契約の gates.checks-security.blocking_threshold 以上の重大度に絞った件数を渡す
          FINDINGS: ${{ steps.review.outputs.<blocking_threshold 以上の findings 件数の output 名> }}
        run: |
          if [ -z "${FINDINGS}" ]; then
            echo "::error::security-review の findings 件数を取得できなかった"
            exit 1
          fi
          if [ "${FINDINGS}" -gt 0 ]; then
            echo "::error::閾値以上の findings が ${FINDINGS} 件ある"
            exit 1
          fi
  notify-success:                  # 沈黙と故障を区別するため成功も通知する(観点「フィードバック速度」)
    needs: [lint, format, typecheck, test, tampering, security]
    runs-on: ubuntu-latest
    permissions: { pull-requests: write }
    steps:
      - env:
          GH_TOKEN: ${{ github.token }}
          PR_NUMBER: ${{ github.event.pull_request.number }}   # ${{ }} を run に直接展開しない(テンプレ全体の規則)
          REPO: ${{ github.repository }}
        run: |
          gh pr comment "$PR_NUMBER" --repo "$REPO" --body "loop-gates: all green"
```

生成時の注意:

- **pathspec のリストは各要素をシングルクォートで囲んで展開する。** 囲まないとシェルが glob 展開し、削除済みファイルが pathspec から落ちてテスト削除の検知が静かに効かなくなる
- **`<...>` は生成時に展開するプレースホルダである。** `<providers.*>` は pack の `providers`、`<pack.ci.*>` は pack の `ci` から読む。テンプレートに言語固有のコマンドを直接書かない(core を言語非依存に保ち、2言語目を pack の追加だけで通すため)

- **生成後に必ず YAML パースで検証する**(`python3 -c "import yaml; yaml.safe_load(open('.github/workflows/loop-gates.yml'))"`)。パースに失敗した workflow は GitHub 上で 0 job の failure になり、原因が分かりにくい(E2E で実例あり。`run:` の1行スカラーに `: ` を含めると壊れるため、コロンを含むコマンドはブロックスカラー `|` で書く)
- **paths-ignore は使わない**。ドキュメントのみの PR でも全 job を走らせる。job を丸ごとスキップすると check-run が1件も作られず、orchestrator の形式ゲート判定が「失敗なし=通過」に倒れる fail-open になるため(速度は依存キャッシュと並列 job で確保する。観点「フィードバック速度」)
- **checkout は全 job で `persist-credentials: false`**。既定値 true は GITHUB_TOKEN を .git/config に残し、PR 由来のコード(ビルドフックや、import 時に実行されるテスト設定)から読めてしまう
- **permissions は workflow 既定を `{}` にし、job ごとに最小付与**。PR のコードを実行する job(lint / format / typecheck / test)には `pull-requests: write` を与えない。`security-events: write` は SARIF アップロードに必要な最小権限として lint / typecheck にのみ与える
- **security job を生成するなら、契約の `gates.checks-security.blocking_threshold` 以上の重大度に絞った findings 件数の output 名を、固定した SHA の `action.yml` から解決して埋める**。重大度で絞れない(総件数しか出ない)場合は、閾値を強制できないため security job を生成しない。総件数で `> 0` を判定すると、契約が `high` を指定していても low の指摘でマージが止まり、契約と実装が食い違う。Action は PR コメントを出すだけで exit code を落とさない場合があり、gate step を挟まないと契約の `blocking_threshold` はどこにも強制されず、`notify-success` が緑を報告してしまう(fail-open)。output 名を解決できない場合は security job を生成しない(強制できないゲートを有効化しない)
- **security Action はコミット SHA に固定**する(生成時に `gh api` でリリースの SHA を解決)。ブランチ、タグ参照は差し替え可能で supply-chain リスクになる。**解決した参照が 40 桁の hex SHA でなければ workflow を生成せず中断する**(`@main` 等のプレースホルダのまま出荷しない)
- `CLAUDE_API_KEY` secret が未設定なら、設定手順を伝える(secrets は CI 環境にのみ置く、観点「実行環境の隔離と権限最小化」)
- security-review Action はプロンプトインジェクション対策がないため、信頼できる PR(自リポジトリの worker 生成 PR)のみを対象とする。fork からの PR には secrets が渡らず security job は失敗する。外部コントリビューションを受けるリポジトリでは workflow 実行に承認を必須とするよう案内する
- **branch protection の提案**：required status checks を default branch に設定するかユーザーに確認する。対象は実際に生成した job に合わせる(言語 pack の既定は lint / format / typecheck / test に tampering を加えたもの。security はオプトイン時のみ加える。生成していない job を required にすると check が永遠に報告されず全 PR がマージ不能になる)。未設定の場合、CI の判定はマージを強制しない(orchestrator の読み取りと人間の目視だけになる)

### 5b. 既存ゲートと外部レビューツールの棚卸し

- **導入先の hooks と branch protection を検出する**(pre-push、PR 作成を検査する hook 等)。ループの PR 作成とマージがそれらに塞がれないかを確かめ、通し方(必要な事前コマンドや marker の更新)を契約の近くに記録する(親 PR 作成が導入先の PR ゲートに塞がれる事故が実地で起きた。hook はコマンド実行前に検査するため、「marker 更新+ PR 作成」を1コマンドに書くと通らない)
- **出荷前レビューに使う外部 plugin(/code-review、claude-security 等)の導入状況を検出する**。未導入なら導入コマンド(marketplace add)を案内する(未導入でもループは動くが、3c の出荷前レビューの網羅が下がることを伝える)

### 6. ラベル作成

`gh label create` で作成する(既存なら skip、冪等)。

- 通過:`gate:intake-passed`、`gate:split-passed`、`gate:start-passed`、`gate:outcome-passed`、`gate:integration-passed`
- 差し戻し中:`gate:intake-returned`、`gate:split-returned`、`gate:start-returned`、`gate:outcome-returned`、`gate:integration-returned`

ラベル名は契約の `gates[].id` から作る。**範囲表記で省略せず、使うものをすべて作る**(作り漏れると `gh issue edit --add-label` が「ラベルが無い」で失敗し、ゲートの通過状態が保存されないまま毎回やり直しになる)。
- `loop:in-progress`(worker 割り当て済み)
- `loop:pr`(ループ由来 PR の識別。子 PR に付く)
- `loop:review`(出荷前レビューの実行中または結果反映中。親 issue に付く。契約が `preship_review.mode: manual` のときだけ人間がレビューを起動する)
- `loop:pause`(人間による一時停止。親 issue に付けると新しい委譲を止める)
- `loop:replan`(要件変更の再計画要求。親本文を編集してから付けると、合流点で計画を作り直す)
- `tasuki:accepted`(外部起票の親 issue をループ対象にする opt-in。maintainer が本文を読んでから付ける)
- `tasuki:child`(ループが起票した子 issue の明示。一覧のフィルタ用)
- `loop:triage`(人間の裁定待ち)

### 7. バジェット確認と fixture の案内

**判定例(fixture)の下書きを自動生成してよい。**
導入先に設計文書(docs/、DESIGN.md、ADR 等)があれば、そこから「この親 issue は PASS のはず」「これは差し戻しのはず」の判定例の下書きを生成し、人間のレビューに出す(手書きより網羅が安定する。採用の判断は人間。手順の正は `tasuki:baton-contract` skill)。

`.tasuki/profile.yaml` の budgets(`max_iterations_per_gate` / `max_inner_loop` / `wip_limit_prs`)をユーザーに提示し、必要なら調整する。
**生成物が .gitignore で除外されているか検査する。** pack の `artifacts`(python なら `__pycache__/` と `*.pyc` 等)が対象リポジトリの `.gitignore` に無ければ、追加を提案する。無いまま進むと、worker のコミットが生成物を巻き込み、ブランチ間で生成物どうしが競合する(E2E で2連続で発生した実害)。

**checks-local の実行権限を提案する。** orchestrator は反復判定で pack の providers コマンドをローカル実行するため、そのコマンドに対応する権限を導入先の設定に追加するよう提案する(権限の文字列は pack の providers のコマンドから作る)。それ以外の実行許可は提案しない(checks-local は providers の宣言済みコマンドだけを実行し、リポジトリ内のスクリプトを直接実行する検査を持たない)。広い `Bash` を丸ごと許可しない(必要なコマンドだけに絞る)。

**一覧の見え方を案内する。** 子 issue と子 PR は機械の作業単位であり、数が増える。issue 一覧は `is:open no:parent-issue` で親だけを表示でき、`-label:tasuki:child` でも子を除外できる。この検索例を README などに書いておくよう提案する。

最後に、運用開始前の必須手順として初期 fixture 5件の用意を案内する(上の自動下書きを使ってよいが、採用の判断は人間。手順は `tasuki:baton-contract` skill。置き場所は `.tasuki/fixtures/`)。

## 完了報告

**生成物はブートストラップ用ブランチ(`tasuki/init`)にコミットして push し、default branch への PR を1件開く。**
default branch へ直接 push しない。
生成物(契約、CI workflow、テンプレート)はガバナンスの制定であり、人間承認を経て default branch に入る。承認の形はループ本体と同型である(機械はコミットと push と PR 作成まで、反映は人間のマージだけ)。
最後に、PR の URL と、未完了の手動作業(**ブートストラップ PR のレビューとマージ**、secret 設定、branch protection、fixture の採用)を分けて報告する。
