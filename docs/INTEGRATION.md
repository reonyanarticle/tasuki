# 橋渡しインターフェース

plugin の成立条件は、外部の subagent、skill、検査ツールを接続できることである。
方針は「ペルソナは薄く、契約を厚く」。
外部 subagent の人格プロンプトには依存せず、入出力契約(verdict JSON / worker 義務)への適合のみを要求する。

## 4つの接続点

| 接続点 | インターフェース | 例 |
|---|---|---|
| gate reviewer 差し替え | 契約 YAML の `reviewer:` に subagent 名を指定。入力は前工程出力+契約、出力は verdict JSON([GATES.md](GATES.md)) | 外部コレクションのレビュアー系 agent を着手ゲートに割り当て |
| worker 差し替え | 契約 YAML の `worker_agent:` に subagent 名を指定(既定 tasuki-worker)。入力は子 issue 本文と統合ブランチ名。義務は実装方針コメント→統合ブランチ base の実装→ self-verify →統合ブランチ向け draft PR(loop:pr)→レポート(参照した skill と委譲した subagent の欄を含む)→掃除。長時間ジョブは PID とログを報告して終了する。出力は PR URL +レポート | 特化 worker(データ処理専用等)への置換 |
| mechanical provider 追加 | コマンド+ SARIF または JUnit XML 出力(非対応ツールは pack の normalizer を挟む) | 任意の linter やスキャナ |
| skill 参照 | ゲート判定基準は skill として外出し可能。worker は対象リポジトリの skill / CLAUDE.md を通常通り参照 | プロジェクト固有規約の注入 |

接続の実行主体は orchestrator(メインセッション)である。
worker からプロジェクト subagent への直接委譲は、既定のネスト上限の範囲でそのまま行える([DESIGN.md](DESIGN.md))。

## プロジェクト直下アセットとの統合

対象リポジトリに既にある `.claude/agents/`、`.claude/skills/`、CLAUDE.md、導入済み plugin との組み合わせを、次の4ルールで扱う。

### 1. 発見

`/tasuki:loop-init` がプロジェクト直下と導入済み plugin を棚卸しし、接続候補を提案する。
レビュアー系 agent はゲート reviewer / 形式ゲートへの割り当てを、コマンド提供 plugin は provider 登録を提案する。
採用結果は契約 YAML に書き込まれる。

### 2. 優先順位

名前解決は project > repo override(`.tasuki/`)> language pack > plugin デフォルトの順とする。
Claude Code のネイティブな衝突解決(プロジェクト定義がグローバルを上書き)に揃える。
plugin 側の agent は `name:` フィールドに `tasuki-` 接頭辞を付けて名前空間を切り(ファイル名ではなく `name:` が衝突判定の対象)、プロジェクトの既存 agent と衝突させない。
コマンドは plugin 名で自動的に名前空間化される(`/tasuki:loop-init`)。

### 3. コンテキスト境界

worker はプロジェクトの CLAUDE.md と skill を意図的に継承する(プロジェクト規約=ガードレール)。
gate-reviewer が継承するのは CLAUDE.md(共有知識)までで、maker の作業コンテキストは渡さない。
プロジェクト skill をゲート判定基準に加えたい場合は、契約 YAML の `criteria_skills:` に skill 名を列挙して gate-reviewer に参照させる。

### 4. 非互換の明記

Stop hook でセッションを回すループ系 plugin(ralph-wiggum 等)との併用は二重ループになるため禁止する。
issue のラベルや assignee を状態機械として使う他のオーケストレーションとの併用は、対象 issue 集合が重ならない場合に限る(WIP 上限と assignee の CAS が tasuki 単独の書き込みを前提とするため)。
`/tasuki:loop-init` の棚卸しで検出したら警告する。
編集時 lint 等の一般 hooks は worker セッション内で通常どおり発火してよい(干渉しない)。
