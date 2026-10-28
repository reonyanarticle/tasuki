---
name: loop-brake
description: tasuki ループ手順のうち§4(停止装置)と §5(終了報告)。/tasuki:loop の実行中に、手順の入口(commands/loop.md)の指示でだけ読み込む。単独では使わない。
user-invocable: false
---

# tasuki ループ手順: §4(停止装置)と §5(終了報告)

この skill は `/tasuki:loop` の手順の一部である。
入口と読み込みの規則は commands/loop.md にあり、他の節は入口の表が示す skill にある。
`/tasuki:loop` の実行中でなければ、ここに従って操作しない。
次の節へ進むときは、進む直前にその節の skill を読み込む。
会話が要約された後に再開したときは、次の操作の前に `tasuki:loop-rules` と `tasuki:loop-brake` と、作業中の節の skill を読み込み直す(手順を記憶から再構成しない)。

## 4. 停止装置(ブレーキとシートベルト)

### 人間による一時停止(loop:pause)

人間はいつでも、親 issue に `loop:pause` ラベルを付けてループを止められる。
暴走の検知を機械に任せるだけでなく、**人間が理由を問わず引けるブレーキ**を用意する(アンドンの紐)。

- orchestrator は §0(前提と状態復元)の状態復元時と、worker を起動する直前のたびに `loop:pause` を確認する(`loop:replan` も同じ確認点で見るが、こちらは run を終了せず、新規起動だけを止めて §1d(再計画)の発効点まで進む)
- 付いていたら、新しい委譲を行わず、現在の状態を親 issue に報告して run を終了する(実行中の worker は完了まで走り切ってよい。強制中断はしない)
- 外すのも人間である。外れた後の run は通常どおり §0(前提と状態復元)から再開する(状態は GitHub にあるので、続きから走る)
- `loop:pause` は stale assignee の回収(§2(子ごとのゲート実行))を**抑止しない**。止まっている間も残骸の回収は行ってよい
- **実行中の worker を人間が止めた(セッションを落とした)場合**は、`loop:pause` に加えて子 issue の assignee を手で外すと、次の run が即座に再入できる(外さない場合は stale 回収の経過時間(既定60分)まで、ループはその子を担当中とみなして待つ)


停止条件の本体は着手ゲートで事前定義された基準(verifier が判定)である。
以下は暴走時のバックストップであり、発火が常態化したら直すのは上限値ではなく契約。

- `max_iterations_per_gate` / 内側ループ有効上限(issue 予算)の超過 → `loop:triage`
- 停滞検知:orchestrator が観測できる事象に限って検知する。同一 issue への差し戻しの反復、verdict のピンポン(同一内容の往復)、進捗のない再委譲を検知したら停止して報告する(agent セッション内部の反復は observable でないため、worker 側は打ち切り条件と wall-clock で守る)
- 発振検知:同一箇所で TOO_ABSTRACT ⇄ TOO_CONCRETE が交互に出たら、worker へ再差し戻しせず axis-question に昇格する(観点「ゲートの発振検知」)

## 5. 終了報告

レイヤーの処理が終わるごとに、親 issue に進行サマリ(通過 / 差し戻し中 / triage / 完了)をコメントする(§3a(レイヤーの合流)の合流報告を兼ねる)。
終了前に、完了(met / abort)した worker の worktree が残っていれば `git worktree remove --force` で削除する(isolation の自動掃除は変更が無い worktree だけを対象とするため、実装を行った worktree は残留する。生成物が残っていると `--force` 無しでは削除が拒否される)。
**default branch への反映は親 PR の人間マージのみである。** レビュー待ちの親 PR(`loop:review`)と、`loop:triage` の一覧を最後に報告して終了する。
