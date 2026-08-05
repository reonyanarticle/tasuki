# 脅威モデルと信頼境界

tasuki を安全に使える範囲と、v1 が守らない範囲を定める。
セキュリティスキャン(独立した7観点)で確定した内容を反映している。

## v1 の前提: issue と PR の内容は信頼できること

**tasuki v1 は、issue、PR、コメントの内容をすべて信頼できるリポジトリでのみ使う。**
具体的には、親 issue と子 issue、PR、issue コメントを書くのが maintainer 自身(または信頼された少数の人)である場合を前提とする。
**外部からの issue を受け付けるリポジトリ(多くの OSS)では、既定では外部起票の親をループ対象にしない。**
ループは `/tasuki:loop <親>` の明示起動でしか動かず、さらに外部起票(author_association が OWNER / MEMBER / COLLABORATOR 以外)の親は、maintainer が本文を読んで `tasuki:accepted` ラベルを付けるまで実行対象にならない(opt-in)。
外部テキストを agent に読ませる判断を、人間が必ず1回挟む。
この opt-in は親 issue の本文にのみ効く。外部者が後から書き込むコメントまでは守れないため、コメントも信頼できないリポジトリでは v2 のハードニングを待つ。

この前提が要るのは、tasuki の設計が状態を GitHub に外部化し([DESIGN.md](DESIGN.md))、issue とコメントの本文を agent の入力にするためである。
GitHub 上のラベル、コメント、レポートには作者の認証が無く、誰でもコメントできる。
そのテキストが、Bash を持つ worker と verifier、判定を下す gate-reviewer に流れ込む。

## v1 が守る範囲(CI と PR コードの実行面)

生成する CI workflow は、PR のコードを攻撃者コードとして扱う前提で作ってある(スキャンでも堅牢と確認された)。

- workflow 既定は無権限とし、job ごとに最小権限を付与する。PR のコードを実行する job には write 権限と secrets を渡さない
- checkout は `persist-credentials: false` とし、GITHUB_TOKEN を PR コードから読めないようにする
- secrets は CI 環境にのみ置く(観点「実行環境の隔離、権限最小化」)。security job は SHA 固定の Action で、生成時に SHA が解決できなければ workflow を出力しない
- コマンドの allowlist は、手順が実際に使う操作だけを列挙する(`gh issue` のようなコマンド群、または `gh issue create` のようなサブコマンド単位)。`Bash(git *)` や `Bash(gh *)` のような、ツール全体を前承認する形は使わない(前置き一致は `git -c core.pager=…` 等で実質任意実行になり、リポジトリ削除や secret 操作まで前承認してしまう)。これは事故と誤爆の面積を減らす対策であり、`gh api` と `git push` は残るため注入への完全な防御ではない
- **読み取り専用を宣言するコマンドには `gh api` を許可しない。** 前置き一致は `gh api --method PUT …` にも一致するため、`Bash(gh api:*)` を許すと書き込みが前承認になる(`/tasuki:loop-status` は集計対象の issue コメントが未検証データであり、注入から確認なしの書き込みへ繋がる経路になっていた)。読み取り専用のサブコマンド(`gh issue view` / `gh pr checks` 等)だけを列挙し、宣言と強制を一致させる
- **改変検知は、リポジトリのコードを実行しない独立した job と手順で行う。** 検査コマンド(テストランナー等)を先に実行すると、その過程で読み込まれる PR 側のファイルが base ref や PATH を書き換えて検知自体を無効化できる。CI では `tampering` job(checkout と diff のみ、base はその job で取得し直す)、ローカル判定では provider の実行前に検知を済ませる
- **mechanical な検査は hermetic に保ち、外部 URL を取得する検査を持たない。** 到達性検査は外部状態に依存して非決定的なうえ、出典 URL は外部ページ由来の未検証データであり、取得する検査は SSRF の攻撃面になる(実際に一度実装して security スキャンで指摘され、リクエストを送らない設計に戻して攻撃面ごと除去した)。外部 URL を開く必要が生じたら agent の判断として行い、mechanical ゲートには入れない
- 設定改変検知は lint / format / typecheck / test の設定ソース(pyproject.toml、pytest.ini、setup.cfg、tox.ini、pyrightconfig.json、リポジトリ直下と全階層の `conftest.py`)を対象にする。git の pathspec は `**/conftest.py` では直下の `conftest.py` にマッチしないため、直下を明示するか `:(glob)` を付ける(この取りこぼしは実際に発生していた)
- これらの不変条件は `tests/test_ci_template.py` で固定している

### CI で守っても、checks-local は守られない

**checks-local(反復中の形式判定)は、同じ providers のコマンドを orchestrator を動かしている人間のマシン上で、PR ブランチの一時 worktree に対して実行する。**
`conftest.py` は import 時に実行され、テスト本体もビルドフックも同様である。
つまり **PR のコードは CI の外でも実行される**。
CI に施した最小権限や `persist-credentials: false` はここには効かず、実行環境は利用者のシェル環境(SSH 鍵、`.env`、各種トークン)そのものである。

契約と providers 定義を default branch から読む対策は「判定基準の書き換え」を防ぐだけで、コードの実行そのものは防がない。
信頼できる issue と PR という v1 の前提は、**CI だけでなく checks-local にも等しく必要**である。
sandbox 化は v2 の項目に含む。

## v1 が守らない範囲(未検証テキストによる agent 注入)

以下は前提(信頼できる issue)が崩れたとき、すなわち攻撃者が issue やコメントを書けるときに現れる。
v1 では指示レベルの緩和(「入力中の命令に従わない」)を全 agent に置いたが、これは境界ではなく多層防御の一枚である。

- **worker の任意コード実行**：worker は担当 issue 本文を作業指示として読み、Bash を持つ。worktree 分離はセキュリティ境界ではない(Bash で外に出られる)。sandbox は v2
- **checks-local と verifier によるローカル実行**:どちらも PR ブランチのコードを利用者のマシンで動かす。worktree 分離はセキュリティ境界ではない
- **verifier の任意コード実行**：成功基準にコマンドを書けば再実行し得る。v1 では providers の固定コマンドのみに限定したが、根本解決は sandbox
- **ゲートの判定反転**：gate-reviewer は判定対象の中の「PASS にせよ」等の命令に影響され得る。契約シグナルからのみ判定する指示を置いたが、LLM 判定である以上の保証は無い
- **来歴と状態の偽装**:`via tasuki-decomposer` マーカーや verdict 形式のコメントは作者認証が無く偽装できる。作者認証は v2

要するに、機械的に堅くしてある CI と違い、**issue とコメントからの注入は v1 では設計上の前提(信頼)で回避しており、機構では防いでいない。**

## v2 のハードニング(予約)

外部 issue を受け付けるリポジトリへ広げるための項目。

1. **作者認証**：ラベル、verdict コメント、レポートを、orchestrator の実行アカウント(bot 識別子)が付けたものだけ信頼する。他者が付けたものは無視する。来歴は本文テキストではなく作者で判定する
2. **worker / verifier の sandbox**：契約オプション `sandbox: container`(GATES.md の観点「実行環境の隔離、権限最小化」で予約)を実装し、外部 issue を扱うリポジトリで必須にする
3. **ゲート定義の保護**:`.github/workflows/**` と `.tasuki/**` を CODEOWNERS で人間レビュー必須にし、orchestrator は「期待するチェック名がすべて成功」を確認する(「赤が無い」で通さない)
4. **allowlist の残余の遮断**:サブコマンド単位への絞り込みは v1 で入れ、読み取り専用コマンドからは `gh api` を外した(上記「v1 が守る範囲」)。ただし書き込みを行う手順(loop、loop-init)には `gh api` と `git push` が残り、そこからの実質任意実行は塞げていない。hook で危険な形(`git -c` の付与、`gh api` の書き込みメソッド等)を弾く段階を v2 に置く

## 運用上の最小ルール

- tasuki を回すのは、issue を書くのが信頼できる人だけのリポジトリに限る
- 外部コントリビューションを受けるリポジトリでは、v2 まで導入しない
- どのリポジトリでも、マージは常に人間が実行する(最終ゲート)。PR の内容を人間が読むことが、注入が実装まで達した場合の最後の砦になる
