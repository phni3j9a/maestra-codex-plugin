# Maestra v0.3 Troubleshooting

## 通常の依頼でMaestraが起動しない

正常です。Maestraは完全opt-inで、全Skillが`allow_implicit_invocation: false`です。通常のCodex workflowへ介入させたい場合はありません。Maestraを使う開発フローだけ、最初に`$maestra:using-maestra`を明示してください。

## Doctor後にSpecが始まらない

正常です。Doctorはworkflow外の独立診断で、単独実行はMaestra lifecycleをactivateしません。診断後にMaestraを使う場合は`$maestra:using-maestra`を明示してください。

## Doctorがrouting proofを拒否する

Routing proofはCodex versionとMaestra versionにbindされています。CodexまたはMaestraを更新したら`$maestra:doctor`を再実行してください。Doctorは`${CODEX_HOME:-~/.codex}/sessions`のrolloutから、親子thread、記録済みspawn引数、子の`turn_context.model` / `effort`を照合します。rolloutが見つからない・一意に結び付かない場合は`unverified`、実値の不一致を確認した場合は`fail`です。model自己申告や`list_agents`だけでPASSにはしません。

## `PLAN_GAP`でRunが止まった

これはfailureではなくv0.3の設計境界です。Terraが以下のような未承認判断を必要とすると発生します。

- architecture選択
- unplanned component / schema / migration追加
- responsibility layer変更
- public API変更
- Planにないtest strategy

Mainでapproved Spec/Planと`plan-gap.json`を読み、Planを補完してください。必要ならユーザー判断を取り、Planを再承認します。その後`/compact`を再度行って新しいRunを開始します。Terraへ「適当に決めて続けて」とは指示しないでください。

## RunPacketが`open_questions`で拒否される

Execution前にMain Planが未完成です。各Taskの実装上のopen questionをMainで解消し、`open_questions: []`にして再承認してください。

## RunPacketがtarget/steps/verification不足で拒否される

v0.3ではMain Detailed Planに以下が必須です: target files/modules、implementation steps、design decisions、verification plan、review focus、expected evidence。Terraへ詳細化を依頼せずMain Planを補完してください。

## working treeがdirtyでRunを開始できない

Maestraはuser workを自動stash/resetしません。既存変更を意図的にcommit/stashするか、現在のRunへ正式に含めるようPlanを改訂してください。

## `.maestra/`が見つからない

v0.3では正常です。runtime stateはworking tree外です。場所は:

```bash
git rev-parse --git-path maestra
```

で確認できます。linked worktreeではcheckout固有のmetadata pathになります。

## Task ReviewはPASSなのにcommitできない

Verification、Review、現在のstaged indexが同じ`candidate_tree`である必要があります。Review後にcandidateが変わった場合は再verification + fresh reviewが必要です。

## Runをcompleteできない

全Task PASSに加えて、Run-level deterministic verificationとfresh Sol Integration Reviewが同じfinal Run treeへbindされ、両方PASSしている必要があります。

## Integration Reviewで設計上の問題が出た

既承認Planの範囲内で局所的に修正できる場合だけbounded remediation可能です。新しいarchitecture/implementation decisionが必要ならMainへ戻してREPLANしてください。Terraがintegration fix planを新規設計してはいけません。

## `$maestra:gate`をいつ呼ぶ？

通常は不要です。active `using-maestra` workflowではRun protocol完了後、Mainが独立Gate Skillをexact pathで読み、同じinteraction内でhandoffします。`$maestra:gate`は中断復帰や明示的な再評価に使いますが、単独ではworkflowをactivateしません。

## `wait`復帰や`list_agents`が何度も表示される

正常なRunはMain→TerraとTerra→Luna/Reviewerの両境界で`wait_agent(timeout_ms: 3600000)`を使います。完了・mailbox更新では60分を待たずに復帰するため、短周期pollingは不要です。正常実行中に`list_agents`を繰り返すと、完了済み子agentの最終payloadが親contextへ重複して入ることがあります。

本当に60分timeoutした場合、Mainはまず`maestra.py status --repo <repository-root> --json`、TerraはTask-local stateと長時間command evidenceを確認します。それでもlivenessが不明な場合だけ、現在のRunまたは直接の子pathに絞って`list_agents`を1回実行してください。1回のtimeoutだけでfailureとは判定しません。

## 全pytestが一括で長い

環境によってGit-heavy runtime testsが時間を使います。CI/検証ではtest群を分けて実行しても構いません。重要なのは全群がPASSすることです。
