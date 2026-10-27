---
description: tasuki ループの起動。親 issue を指定し、子 issue を着手ゲートと形式ゲート(CI)を通して自走させる。このコマンドを実行するメインセッションが orchestrator を務める
argument-hint: "<親 issue 番号>"
disable-model-invocation: true
allowed-tools: Agent, Skill, Read, Grep, Glob, Write, Bash(gh --version), Bash(gh issue:*), Bash(gh pr:*), Bash(gh label:*), Bash(gh api:*), Bash(gh repo view:*), Bash(gh run:*), Bash(git fetch:*), Bash(git worktree:*), Bash(git checkout:*), Bash(git merge:*), Bash(git merge-base:*), Bash(git commit:*), Bash(git push:*), Bash(git log:*), Bash(git show:*), Bash(git diff:*), Bash(git status:*), Bash(git rev-parse:*), Bash(ps:*), Bash(stat:*), Bash(tail:*), Bash(ls:*), Bash(date:*)
---

# /tasuki:loop

このセッションはループの orchestrator である。
この手順は、この入口と、入口が読み込む節ごとの skill でできている。
orchestrator の原則(コードを書かない、自律的に走る、報告を根拠に照らす等)も含めて、本体はすべて skill の側にある。

## 手順の読み込み(会話の要約に耐える構成)

このファイルは、どの節をどの skill が持つかと、読み込みの規則だけを置く。
手順を1枚に書かず節ごとの skill に分けてあるのは、会話が要約(compaction)された後に、起動済みの skill はそれぞれ先頭 5,000 トークンまでしか付け直されないからである(ROADMAP の実装時検証事項の項目16)。
各節の skill はこの上限に収まる大きさにしてあるが、付け直しの枠(合計 25,000 トークン)は新しく起動した skill から埋まり、run の最初に読んだ skill は丸ごと落ちうる。要約の後に手順を取り戻す本体は、下の規則3の読み込み直しである(skill は起動し直すと全文が戻る)。
読み込みの規則は、どの skill が付け直されても残るよう、各節の skill の冒頭にも置いてある。

| 節 | skill |
|---|---|
| orchestrator の原則と、ゲート共通の規則(ラベル、冪等、被判定物、権限、ゲート判定の委譲とエスカレーション) | `tasuki:loop-rules` |
| §0(前提と状態復元) | `tasuki:loop-restore` |
| §1(分割と実行計画) | `tasuki:loop-plan` |
| §2(子 issue ごとのゲート実行) | `tasuki:loop-child` |
| §3(レイヤーの合流と統合ゲート) | `tasuki:loop-merge` |
| §4(停止装置)と §5(終了報告) | `tasuki:loop-brake` |

いずれも利用者が直接起動するものではない(`/` のメニューにも出ない)。

**読み込みの規則**

1. run を始めたら、最初の操作の前に Skill ツールで `tasuki:loop-rules` と `tasuki:loop-brake` を読み込み、続けて `tasuki:loop-restore` を読み込んでから §0(前提と状態復元)を始める(§4(停止装置)の一時停止の確認は、§0(前提と状態復元)の状態復元の時点から必要になるため、最初に読む)
2. 別の節へ進むときは、**進む直前に**その節の skill を Skill ツールで読み込む。前に読み込んだ skill でも、別の節を挟んだ後なら読み込み直す
3. 会話が要約された後に再開したときは、次の操作の前に `tasuki:loop-rules` と `tasuki:loop-brake` と、作業中の節の skill を読み込み直す(付け直しの枠は新しく起動した skill から埋まるため、run の最初に読んだ skill ほど丸ごと落ちやすい)
4. 節の中の「§N(名前)」や「ゲート共通の規則」の参照先は、上の表の skill にある。参照先が手元に無ければ、その skill を読み込んでから従う
5. **手順を記憶から再構成しない。** 読み込んでいない節の操作は行わない(この入口だけでは、どの節の操作も完結しない)
6. skill の読み込みに失敗したら(Skill ツールが拒否された、skill が見つからない等)、その節の操作を行わず、読み込めなかった skill の名前とエラーを親 issue にコメントして run を終了する(黙って終わると、無人の run が止まった理由を人間が GitHub から知る手段が無い)

**この run の起動引数は「$ARGUMENTS」である。** §0(前提と状態復元)は、この値を正の整数であると検証してから親 issue 番号として使う(節の skill の中では引数が置換されないため、ここに書いた値を使う)。
