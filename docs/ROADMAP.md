# 導入戦略

## スコープ(v1)

### 含む

| 項目 | 内容 |
|---|---|
| ゲート機構 | abstraction ゲート(受理から統合までの全ゲート)+ mechanical ゲート(CI 実行) |
| ロール | orchestrator / decomposer / gate-reviewer(降と昇) / worker / verifier |
| 契約 | プロファイル YAML(フェーズ、待ち位置、ゲート、予算) |
| ブートストラップ | `/tasuki:loop-init`(言語検出から契約、テンプレ、CI の生成まで) |
| CI | plugin が生成する前提。既存 CI は前提にしない |
| 質問ルーティング | task-question / axis-question の型付けと宛先分離 |
| 橋渡し | 外部の subagent、skill、検査ツールを接続するインターフェース |
| language pack | python(uv / ruff / black / basedpyright / pytest) |

### 含まない

- python 以外の language pack(インターフェースだけ切っておく)
- タスク複雑度によるモデル自動選択(将来のコスト最適化候補)
- worker セッション内の常駐セキュリティガード(security-guidance 等はユーザー任意導入)
- 外部 issue を受け付けるリポジトリでの運用(信頼境界のハードニングは v2。[SECURITY.md](SECURITY.md))
- 複数リポジトリ横断のループ

## 段階導入

抽象と具体の往復にはコストがあり、ゲート全部入りで始めるとオーバーヘッドでループ自体が回らない。
IE(工程分析)の「検査、運搬、停滞は付加価値を生まない」という原則に従い、ゲート(=検査)は必要最小限から始めて差し戻しの質で増減を判断する。
段階導入を標準とする。

### フェーズ1: 着手ゲート+ 形式ゲート

門前払いと契約照合の効果を差し戻しの質で確認する。

**フェーズ1の受け入れ条件(完了の定義)**：

- `/tasuki:loop-init` が素の Python リポジトリ(pyproject.toml のみ)に対して、契約雛形、issue / PR テンプレ、`loop-gates.yml`、ラベルを生成できる
- 必須欄が空の子 issue が門前払いで差し戻される(LLM 呼び出しなし)
- 手書き fixture 5件に対し、gate-reviewer(haiku)の判定が人間の正解ラベルと5件中4件以上一致する
- 差し戻し verdict が issue コメントに verdict スキーマ([GATES.md](GATES.md))の JSON で記録される
- 着手ゲート通過の子 issue を worker が worktree 上で実装し、draft PR 作成、形式ゲート(CI)実行まで到達する
- 差し戻し2連続で sonnet へのエスカレーションが発火する

### フェーズ1の E2E 実施結果(tasuki-e2e リポジトリで headless 実行)

| 受け入れ条件 | 結果 |
|---|---|
| loop-init が素の Python リポジトリに契約雛形、テンプレ、`loop-gates.yml`、ラベルを生成 | 達成(uv.lock 生成、security オプトアウト構成を含む) |
| 必須欄が空の子 issue が門前払いで差し戻される(LLM なし) | 達成(親 issue の門前払いも動作) |
| 手書き fixture 5件で gate-reviewer(haiku)が4件以上一致 | 達成(5/5、confidence すべて high) |
| 差し戻し verdict が issue コメントに JSON で記録 | 達成 |
| 着手ゲート通過の子 issue を worker が実装し draft PR 作成、形式ゲートの実行到達 | 達成(形式ゲートが緑 → verifier met → PR ready 化まで完走) |
| 差し戻し2連続で sonnet エスカレーション発火 | 達成(verdict 履歴 haiku → haiku → sonnet。昇格後の判定で PASS し、worker が issue 予算内で完走) |

E2E で発見し修正した不具合:workflow scope 前提の過剰要求(SSH では不要)、`.claude/loop/` の機密ファイルガード衝突(`.tasuki/` へ移設)、CI テンプレートの YAML 不正(notify の `: ` )、SARIF アップロードの GHAS 依存(best-effort 化)。
check-run ゼロ件の fail-closed が YAML 不正を設計どおり捕捉したことも確認した。
追加の運用ギャップ2件(差し戻し再入の編集検知は timeline ではなく GraphQL の lastEditedAt を使う、変更済み worker worktree は自動掃除されないため orchestrator が終了時に削除する)も E2E で発見して修正した。
形式ゲートのハイブリッド(checks-local / checks-ci)、task-question の回答反映と再入、worker による前提不在の検出(実在しない関数を前提とした issue への task-question)も実地で動作確認済み。

### フェーズ2: 成果ゲートを追加

昇る側の対応表検証を回す。

**フェーズ2の受け入れ条件(完了の定義)**：

- `enabled_gates` に `outcome` を含む契約で、verifier の met 後に worker のレポートが成果ゲート(sonnet)で照合される
- 成果ゲートの判定例 fixture 3件(PASS / TOO_ABSTRACT / TOO_CONCRETE)で、sonnet で呼んだ gate-reviewer の判定が人間の正解ラベルと3件中3件一致する(目盛り合わせ)
- 対応表または結論を欠くレポートが TOO_ABSTRACT、生ログ貼り付けが TOO_CONCRETE で差し戻される
- 書き方の不足の差し戻しでは、worker が実装に触れずレポートのみを新規セッションで再出力する
- 成果ゲートの PASS 後にのみ ready 化される(checks-ci と併せて)

### フェーズ2の E2E 実施結果(tasuki-e2e リポジトリ)

| 受け入れ条件 | 結果 |
|---|---|
| verifier met 後に成果ゲート(sonnet)がレポートを照合 | 達成(実 E2E の子 issue 1件の実レポートを PASS / high 判定。対応表の N対1 と孤児なしを reasons で確認) |
| 成果ゲートの fixture 3件で3件一致 | 達成(較正の往復2回を経て4 fixture 全一致。不一致2回はいずれも fixture 側の欠陥で、reviewer は孤児検出と「両シグナル該当時は抽象側優先」規則を正しく適用していた) |
| 対応表、結論の欠如が TOO_ABSTRACT、生ログ貼り付けが TOO_CONCRETE | 達成(fixture 検証) |
| 書き方の不足はレポートのみ再出力 | 達成(悪いレポートを仕込んだ実走で検証。成果ゲートの門前払いが欠落4欄を LLM なしで検出し、worker が実装に触れずレポートのみ再出力、2f 再判定で PASS) |
| 成果ゲートの差し戻し状態からの run 境界の再入 | 達成(差し戻し直後のセッション死亡を模擬。次の run が起票者待ちにせず、2a と着手ゲートをやり直さず、再出力 worker を自力起動して 2f から復旧) |
| 成果ゲートの PASS 後にのみ ready 化 | 達成(gate:outcome-passed → checks-ci → ready の順序を確認) |

副次の実地確認:WIP 制限(観点「スループット管理」)が ready PR 3件の滞留で発火し、worker 起動を正しく保留した。親 issue の予算欄(子3件)と実子4件の不一致も orchestrator が人間に指摘した。
成果ゲートのレビュー(3観点、確定16件)後の再実走では、拡充した契約 signals(要件 ID の採番一致、期待値の根拠の仕様由来、secrets 不在)が verdict の reasons にそのまま現れることも確認した。
実ループ未発火のまま残る経路は、`return_to: implementation`(内容の不足による実装差し戻し)と 2g の CI 失敗分岐の2つ(手順、fixture、テストでの検証のみ)。

### フェーズ3: 受理 / 分割 / 統合ゲートとレイヤー並列実行

フルループへ移行する。

**フェーズ3の受け入れ条件(完了の定義)**：

- `enabled_gates` に全 abstraction ゲートを含む契約で、親 issue が受理ゲート(opus)の受理判定を受ける
- 子 issue が無い親に対し、decomposer の分割案が分割ゲート(opus)で照合され、PASS 後に orchestrator が子 issue を起票して紐付ける(必須欄、AC-n / SC-n 採番、依存設定、`via tasuki-decomposer` 記載)
- 依存の循環がエラーとして検出され、実行せずに停止する
- 依存グラフからレイヤーが構成され、レイヤー内の子 issue が並行処理される。次レイヤーへは前レイヤーの ready PR がすべて人間にマージされるまで進まない(フェーズ3当時の規則。v1.1 で「統合ブランチへの取り込みで前進(人間のマージは親 PR の1回)」に変更)
- 全子 issue のマージ後に統合ゲートが親要件へのロールアップを照合し、孤児の親要件があれば差し戻して追加分割を提案する
- 受理 / 分割 / 統合ゲートの判定例 fixture(各2件以上)で人間ラベルと全一致する(目盛り合わせ)

### フェーズ3の E2E 実施結果(tasuki-e2e リポジトリ)

| 受け入れ条件 | 結果 |
|---|---|
| 受理ゲート(opus)の受理判定 | 達成(実 E2E の親 issue 1件が PASS。gate:intake-passed) |
| decomposer 分割 → 分割ゲート → 子 issue 起票 | 達成(子なし親から2子を自動分割、起票。必須欄、AC-n 採番、直列依存の設定、via 記載。実装方式を子タイトルに持ち込まない粒度を維持) |
| 依存の循環をエラーとして停止 | 達成(実走で GitHub がネイティブ依存の循環を API 拒否すると判明。§1c は二重の安全網とし、実効防衛は分割ゲートの set_signals=opus が分割案の循環を検出。fixture split-003 で PASS→TOO_ABSTRACT を実証) |
| レイヤー構成と前進規則 | 達成(当時の規則で L1→合流→人間マージ→L2、マージ済み子を除く再構成も動作)。1レイヤー複数子の並行も別シナリオで実証(独立子2件が同一 L1 で処理され両 PR ready) |
| 統合ゲートの親要件ロールアップ照合 | 達成(integration フェーズの契約で opus が PASS / ロールアップ表を親にコメント。孤児差し戻し側は fixture integration-002 で検証) |
| 受理 / 分割 / 統合ゲートの fixture 較正 | 達成(6/6 全一致、初回) |

フェーズ3レビュー(3観点、確定16件)の修正のうち、クラッシュ復旧系(部分起票の突合、g0-returned 再入、分割案の verdict 添付からの復旧等)は手順、テスト検証のみで実走未発火。実運用で自然発火した際が実地検証になる。

claude-security スキャン(7観点)を実施し、信頼境界の設計上の弱点を確定した([SECURITY.md](SECURITY.md))。
未検証の issue / コメント本文が Bash を持つ worker / verifier に流れる点が根本原因で、指示レベルの緩和を全 agent に入れたうえで、v1 の適用範囲を信頼できる issue のリポジトリに限定すると明記した。
作者認証と worker/verifier の sandbox は v2 のハードニングとする。

## v1.1: 統合ブランチと親 PR への集約

フェーズ3完了後、実運用レビューを受けて人間の関与を再設計した。

- 子 PR は統合ブランチ `loop/parent-<N>` に向け、ゲート通過後にループが取り込む。**人間の判断は親 PR の1回に集約**(default branch への反映点はここだけ)
- 親 PR は承認の道具として設計する:本文=大観、承認材料(裁量判断の出どころと検証点つき)は check-runs 全緑後に**新規コメント**で投稿
- 実装方針コメント(worker の第1手)、出荷前レビュー(5観点)、loop:pause、loop:review、実験プロファイルの契約解決(gates[].phase)、tasuki:accepted(外部起票の opt-in)、tasuki:child と取り込み時クローズ
- テスト基盤: claude plugin validate(CI)+ LLM fixture runner(RUN_LLM_TESTS=1)

### v1.1 の E2E 実施結果(tasuki-e2e-v2 リポジトリ)

複数モジュールの経費精算アプリを種に、Decimal 移行(5子、3レイヤー、分岐と合流あり)で検証した。

| 検証 | 結果 |
|---|---|
| 統合ブランチ+親 PR、子 PR の自動取り込み | 達成(子5件、人間のマージ0回) |
| レイヤー並列 | 達成(L2 を worker subagent 3体の並行実行) |
| 分割欠陥の自己修復 | 達成(型移行のモジュール別分割が checks-local 失敗→task-question→分割ゲート差し戻し→改訂の経路で修正された) |
| checks-local/ci の食い違い | 達成(生成 workflow の欠陥を fail-closed が検出) |
| pause / 二重実行 / 承認コメント | 達成 |
| リポジトリ由来 agent と plugin agent の呼び出し | 達成(headless で双方向を実機確認) |

## v1.2: 走行中の変化への追従

アジャイル運用の難所分析で特定した2つのギャップを閉じた。

- **再計画(loop:replan)**:走行中の親要件変更の正式経路。人間が親本文を編集して `loop:replan` を付けると、実行中の worker を走り切らせてから、受理ゲート再判定と decomposer の差分分割(維持 / 改訂 / 追加 / 撤回、取り込み済みへの波及は追い子)で計画を作り直す(loop.md §1d)
- **default branch の定点取り込み**:ループ外の開発(hotfix 等)との共存。run 開始時(任意)、レイヤー合流時、3c 入場前(必須)の3定点で default branch を統合ブランチへ merge し、conflict と赤は解消専用 worker で 2d 相当に通す。3c は merge-base が default 先端と一致するまで入れない(承認する差分とマージ結果を一致させる)。多親並走(v2)の前提部品でもある
- 3c の承認コメントに「やらなかったこと」の親 issue 下書きを添える(起票は人間)
- 出荷前レビューを人間起動から orchestrator の subagent 自動実行へ変更し、規模は契約の preship_review(full / scaled / manual)で制御する
- レポート必須欄に「参照した skill と委譲した subagent」を追加(成果の前提を辿る)
- loop:triage の子には着手しない。人間の手動 assign(着手コメントの無い assignee)には触れない
- **起票支援(/tasuki:draft)**:生の要望からの対話式起票。背景はリポジトリの裏取りで書き、コードから導けない欄(価値、予算、完了の定義)だけを質問し、受理ゲートと同じ契約定義で事前審査してから起票する(粒度のシフトレフト。実装方式は本文に入れず参考メモコメントへ分離)

### v1.2 の E2E 実施結果(tasuki-e2e-nlp と tasuki-e2e-v2)

experiment プロファイル2走行(NLP ベースライン確立、データセット難化と再評価)と development プロファイル1走行(定期経費機能、4子3レイヤー)で検証した。

| 検証 | 結果 |
|---|---|
| experiment プロファイルのフル自走(受理〜統合、実験の分離規律) | 達成(2親、計8子。test 単回評価と dev 選定を verifier がコード読解で毎回確認) |
| /tasuki:draft の起票(裏取り+事前審査) | 達成(事前審査 opus PASS → 正式受理ゲートも PASS) |
| replan(要件変更の正式経路) | 達成(親本文編集+ loop:replan →受理再判定→差分分割(維持3、改訂1、追い子1)→適用。取り込み済みは巻き戻さず追い子で適応) |
| default branch の定点取り込み(hotfix 共存) | 達成(main への hotfix を定点1で merge、checks 緑。定点2の merge-base 一致も両走行で確認) |
| 成果ゲートの差し戻し→レポートのみ再出力→再判定 PASS | 達成(対応表の SC 行欠落を TOO_ABSTRACT で検出、実装に触れず解消) |
| 受理ゲート low-confidence の Fable 裁定 | 達成(CSV の独立価値の疑義を裁定し、分割条件として decomposer に伝播) |
| 承認コメント(判断表+ issue 下書き添付)と ready 化 | 達成(3親 PR すべて) |
| 契約の但し書き(統制条件は要件側)の効果 | 達成(追加後の受理ゲートが但し書きを引用して confidence high で判定) |

E2E で発見して修正した設計欠陥: 先行親の未マージ成果に依存する後続親の起動(worker が成果を複製する事故。起動条件を「先行親のマージ後」に強化)、2g の ready 化の欠落、親 PR 作成に空コミットが要ること、orchestrator が計画コメントの skill を読み込まず依存矢印だけの図を描いた事故。

### v1.2 の実地レビュー(外部リポジトリでの実運用)で確定した修正

実運用1件の走行レポートから、次を loop.md と agent 定義に反映した。

- 被判定物はゲート起動直前に取得し直しインラインで渡す(中間ファイルの揮発と INPUT_UNAVAILABLE の再発防止)
- 長時間ジョブの公式プロトコル(worker は PID とログを報告して終了、orchestrator が監視して回収モードの新セッションへ)
- 分割案の機械処理は1子1ファイルで行う(shell ワンライナー起票の1ズレ事故)
- loop-init の棚卸しに既存 PR/push ゲートの検出と、外部レビューツールの導入案内を追加
- 2g の取り込みに ready 化を明記、§1c の親 PR に空コミットを明記
- 成果物の置き場規約(git 管理が既定、gitignore 成果物の受け渡しは前提に明記)
- 契約の too_concrete_signals に「検証の統制条件は要件側」の但し書き
- worker 停止時の即時再入手順(assignee を外す)と、予算執行の機械記録

## v1.3: 調査プロファイル(research)

開発と実験に続く第3のプロファイル。思想(ゲート、契約、統合ブランチ、親 PR 集約)は共通で、契約の中身と maker、pack だけが変わる。

- 分割の単位は「独立に答えが閉じる部分問い」(体系的レビューと orchestrator-worker 型 deep research の先行例に依る)
- CI 相当は決定的検査のみ(必須節の存在= schema、出典 URL の到達性= links。docs pack)。主張⇔出典の整合は決定的に検査できないため、verifier の調査モード(出典を開いて支持を確認する引用検証)が担う
- timebox を打ち切り条件の一級市民にする(調査には完了の自然な下限が無い。到達時は現時点の結論+残課題で設計された終了)
- バイアス対策を構造で入れる: 結論の先取りを too_concrete シグナルに、反証と対立仮説の節と除外の記録を必須欄に
- 出典: PRISMA(https://pmc.ncbi.nlm.nih.gov/articles/PMC8005925/)、Kitchenham の SLR ガイドライン、agile spike、ADR、Anthropic のマルチエージェント調査(https://claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them)、引用検証の実証研究(https://arxiv.org/html/2605.06635v1: リンク有効性 94% に対し事実整合 39〜77%)

### v1.3 の E2E 実施結果(tasuki-e2e-research リポジトリ)

実リポジトリの実論点(計画データの受け渡し形式と機械処理方式)を親1件、子4件(並行調査3+まとめ子1)で完走した。

| 検証項目 | 結果 |
|---|---|
| 受理ゲート(opus)と分割ゲート(opus)の research 判定 | 達成。分割ゲートは分割案の予算欄の混同(検索回数を反復数に記入)を、契約の min 規則で無害と明示判断して PASS を維持(契約に無い基準で差し戻さない原則の実働記録) |
| researcher の調査戦略コメント→調査→文書→self-verify→draft PR→報告 | 達成(3体並行。反証探索の痕跡と timebox 残量の編集更新を含む) |
| checks-local / checks-ci(schema と links) | 達成(default branch 版スクリプトで実行) |
| verifier の引用検証(出典を開いて支持を確認) | 達成。1子で FAIL→差し戻し→修正→再照合 PASS(成功基準のコマンド例欠落と実行記録の集計不整合を検出。リンク生存と主張支持の分離が機能) |
| まとめ子(新規調査禁止の統合)と統合照合 | 達成(トレーサビリティの抜き取り照合、新規出典の混入なし、確信度引き上げの論拠明示) |
| 統合ゲート(opus)→出荷前レビュー(scaled、5観点)→承認材料→ready 化 | 達成。レビューが実在所見5件を検出し、worker が反映して CI 再緑化 |

E2E で発見して修正した欠陥: 契約の必須欄と schema 検査の既定節の対応漏れ(報告コメント専用欄の地位を明文化し、一致をテストで固定)。
E2E 後の出荷前レビュー(5観点+手順のトレース)でさらに欠陥を検出して修正した。
主なもの: レポート skill に research の読み替えが無く成果ゲートの門前払いを必ず落ちる、schema 検査の部分一致が打ち消し見出しとコードブロック内見出しを必須節として数える、links 検査の main が未テスト(revert しても緑)、research 契約が汎用の契約整合性テスト群から素通り、docs_dir とコマンド内パスの二重管理、統合ブランチの初期状態(文書0件)で検査が必ず赤、verifier の research 経路に被検査物の取得手順が無い、AC / SC 採番の無条件指示が research と矛盾、docs pack で CI の設定改変検知 job が生成されない。
E2E で得た運用知見: 報道サイトの URL は CI ランナー(データセンター IP)からボット遮断で系統的に到達不能になり、links 検査が環境依存で赤くなる(researcher は到達性の安定した一次情報を優先し、報道出典は除外記録に理由を残して外すのが実務解)。

### v1.3 の E2E 実施結果 2本目(tasuki-e2e-research-v2 リポジトリ。多層依存と差し戻し経路の複雑走行)

出荷前レビューの所見18件を反映した後の手順書で、リグ生成からやり直して2本目を完走した(親1件、子4件、3層依存)。

| 検証項目 | 結果 |
|---|---|
| 修正後の loop-init 手順の実走 | 達成(プロファイル先行確定、docs pack、`<docs_dir>` 展開、独立 config-tampering job、文書0件の初期状態が緑) |
| 受理ゲートの差し戻し経路 | 達成。仕込んだ「結論の先取り」を opus が正確に検出(TOO_CONCRETE)し、補強箇所まで指摘。修正後に再受理 PASS |
| 3層依存(証拠収集2子並行→条件切り分け→まとめ子) | 達成。分割ゲートは L2 を「別の問い」と判定し重複と誤認しなかった |
| timebox の一級市民化 | 達成。verifier が回数超過(単位の混同)と「超過を婉曲に回避する記述」を検出して差し戻し、実行記録の正直な是正で再照合 PASS(発見は削除せず注記で監査可能化) |
| loop-report の research 読み替え(コメントと文書の欄分担) | 達成。まとめ子の報告が対応表を欠いた際、成果ゲートの門前払い相当が捕捉→レポート再出力のみで解消 |
| クラッシュ後の再入 | 達成。まとめ子セッションが中断→同一セッション再開で、済んだ手順(戦略コメント)を繰り返さず残りだけを実行 |
| 矛盾する証拠の統合 | 達成。「詳細さの効果」対「長さによる劣化」を単一の説明変数(指示密度)で条件つき両立とし、確信度の引き上げに論拠を明示 |

E2E 後の出荷前レビューが検出した主な欠陥と恒久対策: 「結論には不採用」と実行記録に明記した出典が対応表と結論の根拠に使われ後続文書へ伝播していた(抜き取り式の引用検証の盲点。verifier の照合項目に「除外の整合」の全件突き合わせを追加)。説明なしに逆方向の数値を「整合」と記載(閾値の判定不能を明示して是正)。
機構側の修正2件: links 検査が 3xx リダイレクトを環境依存で赤にする(3xx を到達扱いに)、timebox の「検索 N 回」の単位が未定義(WebSearch と WebFetch の合計と明文化)。

## v1.4 候補(未着手)

1. 分割案 YAML から冪等に起票と依存設定まで行う同梱スクリプト(shell 手作業の廃止。導入先に Python が無い場合の代替が論点)
2. 子 PR の自動マージを CI に移す(`gh pr merge` が組織の permission ポリシーで ask になる環境向け。loop:pr ラベル+ checks 緑+ base が `loop/*` の PR だけを対象にした automerge job を loop-init が生成する)
3. 起票支援(/tasuki:draft)の事前審査に、蓄積した判定例(fixture)を目盛りとして渡す

## 未決事項

1. ~~受理ゲートのコスト見積もりを誰が書くか~~ **決着**：起票者(人間)がテンプレ必須欄として記入する(門前払いと整合する最小構成)。decomposer による見積もり案と人間承認のフローは v2 予約
2. ~~`/tasuki:loop` の起動形態~~ **決着**：v1 は手動起動のみ。スケジュール実行(automations)は v2 予約
3. experiment プロファイルの成果物置き場。実験ログや生成モデル等の大容量成果物の保存先規約(GitHub 外ストレージとの接続)

## 実装時検証事項(着手前に公式ドキュメントで確認)

本設計は Claude Code の機能仕様に依存する記述を含む。
以下は策定時点の理解であり、**実装着手時に必ず docs.claude.com の現行ドキュメントで確認し、差異があれば docs を先に修正する**(思い込みでの実装開始を門前払いする)。

1. subagent frontmatter の `model:` フィールド。指定可能な値と、Fable 5 のモデル名文字列。指定不可の場合はメインセッション= orchestrator とする代替構成(レート構造は維持可能、[DESIGN.md](DESIGN.md) 参照)
2. subagent の `isolation: worktree` 設定。記法と挙動(worktree の自動作成と掃除の範囲)
3. plugin.json のスキーマ。commands / agents / skills / hooks の配置規約とマニフェスト書式
4. subagent からの `gh` CLI 利用。allowed-tools の指定方法と、Bash 許可の粒度(`Bash(gh *)` 等)
5. 組み込みスラッシュコマンドの headless 実行可否。不可なら形式ゲートの security は GitHub Action 側([OPERATIONS.md](OPERATIONS.md))のみを使う
6. GitHub sub-issues / issue dependencies。`gh` CLI と REST API の対応範囲。未対応操作は GraphQL API へフォールバック
7. plugin からの CI workflow ファイル生成。GitHub Apps / Actions の権限(`workflows` 書き込み権限が必要な点)

### 検証結果(公式ドキュメントで確認済み)

1. `model:` は `haiku` / `sonnet` / `opus` / `fable` を受け付け、省略時は `inherit`(メイン会話と同モデル)。plugin agent でも同じ。**さらに Agent の起動引数で `model` を渡すと、agent 定義の `model` より優先される**(追認済み。これによりモデル固定の変種を分ける必要は無い)
2. `isolation: worktree` は有効。worktree は自動作成され、変更がなければ自動で掃除される。agent 種別の制約なし
3. plugin.json は `name` のみ必須。commands / agents / skills は規約ディレクトリから自動発見される(マニフェストへの列挙は不要)
4. **差異あり**：agent frontmatter の `tools:` はツール名のみで、`Bash(gh *)` の粒度は書けない。粒度制御は permissions 設定か hooks 側。ただしコマンド(commands/*.md)の `allowed-tools:` は粒度指定可。対応として gate-reviewer には Bash を渡さず(orchestrator が issue 本文を渡す)、コマンド側は `allowed-tools: Bash(gh *)` で絞る
5. **差異あり**：組み込みスラッシュコマンドは `claude -p` から呼べない。対応として形式ゲートの security は GitHub Action(`anthropics/claude-code-security-review`)のみを使う。同 Action は SARIF 非出力(PR コメント+ JSON 成果物)、`claude-api-key` が必須
6. sub-issues と issue dependencies は REST / GraphQL とも GA。`gh` CLI はどちらも v2.94.0 からネイティブ対応(`--parent` / `--blocked-by` 等)。それ未満は `gh api` フォールバック
7. `.github/workflows/` への push には classic PAT で `workflow` scope、fine-grained / Apps で `workflows: write` が必要。Actions の `GITHUB_TOKEN` では不可。`gh auth refresh -s workflow` で付与できる。**E2E での追記**：この制約は OAuth token による HTTPS push に対するもので、SSH 鍵での push には適用されない(実地確認済み)。前提チェックは protocol が https のときのみ scope を要求する

**設計への反映**：subagent は既定で別の subagent を起動できない(`Agent` ツールが除去される)ことも確認した。
このため orchestrator は agent ではなく、`/tasuki:loop` を実行するメインセッションが務める([DESIGN.md](DESIGN.md))。
ゲート別モデルは、gate-reviewer を1つの agent とし、Agent の起動引数で `model` を指定して実現する。
エスカレーションは同じ agent を上位モデルで呼び直すことである。
(**訂正**:当初は「agent frontmatter の `model:` が静的なためモデル固定3変種にする」としていたが、起動ごとの `model` 指定が可能であることを確認したため統合した。起動引数の `model` は agent 定義の `model` より優先される。)
worker からプロジェクト subagent への委譲は、導入先の `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` 設定によるオプトインで可能にする([DESIGN.md](DESIGN.md))。
