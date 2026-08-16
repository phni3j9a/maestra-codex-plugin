# Maestra — Codex Multi-Agent Orchestration Plugin

Maestraは、**重要な設計判断をMain Solに集約し、実行コンテキストだけを下位agentへ分離する**ためのCodex Agent Pluginです。

> **Installing Maestra does not change normal Codex behavior. Maestra is activated only by explicitly invoking `$maestra:using-maestra`.**

## 完全opt-in

Maestraの7 Skillはすべて`agents/openai.yaml`で`policy.allow_implicit_invocation: false`です。Pluginをインストールしただけ、または通常の開発依頼を入力しただけでは、MaestraのSpec/Plan、subagent、runtime state、artifact、Git protocol、review flowは一切開始されません。

```text
このバグを直してください
  ↓
通常のCodex（調査 → 実装 → test → 報告）
```

Maestra workflowの入口は次の明示呼び出しだけです。

```text
$maestra:using-maestra

OAuthログイン機能を追加したいです。
まず設計から相談したいです。
```

`$maestra:doctor`は独立診断です。単独で実行してもworkflowをactivateせず、結果報告後は通常のCodexへ戻ります。hooks、SessionStart instruction、persistent activation markerは使用しません。

v0.3の中心原則は明確です。

> **Main Solが考え、Terraが実行を統制し、Lunaが実装し、Sol Reviewerが検査する。**

Terraは詳細Planを作りません。Mainが承認済みのDetailed Planに実装判断が不足していれば、Terraは推測せず`PLAN_GAP`としてMainへ返します。

## モデル構成

| 役割 | モデル | 推論 | 主責務 |
|---|---|---:|---|
| Main | GPT-5.6 Sol | high | ユーザー対話、Spec、**詳細Plan全体**、Run間の本質判断、最終報告 |
| Orchestrator | GPT-5.6 Terra | xhigh | 1 Runの実行順管理、exact command解決、検証、レビュー裁定、Git管理 |
| Implementer | GPT-5.6 Luna | max | Main Planに沿った1 Taskの実装と受理済み修正 |
| Reviewer | GPT-5.6 Sol | xhigh | fresh contextでの独立レビュー |
| Final Reviewer | GPT-5.6 Sol | xhigh | 必要な場合だけwhole-branchの重大問題を確認 |

## opt-in workflow

```text
$maestra:using-maestra
          │
          ▼
User ↔ Main / Sol high
          │
          ├─ Brainstorm
          ├─ Spec → User Approval
          ├─ Detailed Plan → User Approval
          │      - architecture
          │      - Run / Task decomposition
          │      - target files/modules
          │      - implementation steps
          │      - design decisions
          │      - verification strategy
          │      - review focus
          │
          ├─ /compact 推奨
          │
          └─ approved Spec + Detailed Plan を再読込
                         │
                         ▼
                 fresh Terra / Run 1
                         │
                         ├─ fresh Luna implementation
                         ├─ Terra verification
                         ├─ fresh Sol review
                         ├─ Terra adjudication
                         ├─ accepted fixes → fresh Luna
                         ├─ one Task = one commit
                         └─ Run Integration Review
                         │
                         ▼
                      RunReport
                         │
                         ▼
                   Main Semantic Gate
                         │
                  ┌──────┴───────┐
                  │              │
              CONTINUE       REPLAN / USER_DECISION
                  │              ▲
                  ▼              │
            fresh Terra Run 2    └─ PLAN_GAPもここへ
                  │
                 ...
                  │
                  ▼
               Finish
```

すべてのexecution spawnは原則`fork_turns: "none"`です。Conversation transcriptではなくSpec、Plan、RunPacket、verification、review、RunReportがhandoffのSource of Truthです。

Main→TerraとTerra→Luna/Reviewerは、`wait_agent(timeout_ms: 3600000)`によるevent-driven待機を使います。完了・mailbox更新では即時復帰し、正常実行中の短周期pollingやroutine `list_agents`は行いません。実際に60分timeoutした場合だけ、Mainは軽量Run status、TerraはTask-local evidenceを先に確認し、必要なら対象pathへ絞った`list_agents`を1回だけ使います。

SpecとDetailed Planの承認はユーザーの明示承認が必須です。Plan承認後は、MainがRun → Gate → 次のRun → Finishを管理します。通常フローでユーザーがphase Skill名を毎回入力する必要はありません。`PLAN_GAP`、`REPLAN`、`USER_DECISION`、material remediation、failed precondition、ユーザーのpauseでは停止します。

## Plan ownership

### Main Solが決める

- Architectureと実装方針
- Run分割・Task分割・依存関係
- Taskごとの目的とAcceptance Criteria
- 主要な変更対象ファイル/モジュール
- 実装手順と重要なdesign decisions
- Verification strategyと追加すべきtestの意図
- Review focus
- Run Integration Verification Plan
- Main Gateで再確認する質問

### Terraが決めてよい

- package scripts等からexact shell commandを解決する
- 現在のline/pathなど機械的に一意な詳細を確認する
- approved orderでTaskを進行する
- Luna/Solのspawn、verification実行、finding adjudication、commitを行う

Terraが「どの抽象化を選ぶか」「どの層へ責務を置くか」「どんなmigrationを設計するか」「Planにないtest strategyを選ぶか」を判断する必要が出たら`PLAN_GAP`です。

## `/compact`の位置

推奨運用は次です。

```text
Brainstorm → Spec approval → Detailed Plan approval → /compact → Run
```

`/compact`後の要約はSource of Truthではありません。active workflowのMainがRun phaseへ進む際、Git metadata内のapproved Spec/Planを再読込してRunPacketを構築します。Planを改訂した場合は再承認後にもう一度`/compact`するのを推奨します。

## Skill構成

- `$maestra:using-maestra` — **唯一のworkflow入口**。activation、lifecycle、phase routingだけを担当
- `$maestra:doctor` — Codex/Git/model routingを事前確認
- `$maestra:spec` — Mainが承認可能なSpecを作成
- `$maestra:plan` — **Main Solが詳細実装Planを完成させる**
- `$maestra:run` — 承認済みDetailed Planから1 Runをfresh Terraへ委譲
- `$maestra:gate` — Run後のMain semantic gate。通常は`run`から同じinteraction内で自動handoff
- `$maestra:finish` — 最終確認。whole-branch Sol reviewはrisk-based

各Skillは独立directoryと`SKILL.md`を維持し、`agents/openai.yaml`で暗黙起動を無効化しています。`spec / plan / run / gate / finish`の直接呼び出しはrecovery/debugging用に残りますが、単独呼び出しはworkflow全体をactivateしません。

### phase遷移をどう実現するか

現行Codexには「Skill AからSkill Bをinvokeする」専用APIはありません。`using-maestra`が明示選択された後、Mainはphase境界でexact sibling path（例: `../spec/SKILL.md`）を完全に読み、その独立protocolへ処理を委譲します。これは通常promptとのdescription matchingではなく、明示activate済みrouterからのdeterministic progressive disclosureです。

`allow_implicit_invocation: false`は通常promptからの自動選択を禁止しますが、明示的な`$skill`呼び出しは引き続き有効です。この構成ではユーザーが明示するのは通常`using-maestra`だけで、Mainが以後のphase protocolをexact pathでloadします。

## Runtime Artifact

Maestra内部状態はproduct working treeへ置きません。

```bash
git rev-parse --git-path maestra
```

で解決されるGit metadata配下に保存します。通常repositoryなら概ね`.git/maestra/`、linked worktreeではそのcheckout専用metadata pathになります。

```text
<git-path maestra>/
├── config.json
├── routing-proof.json
├── spec.md
├── plan.md
└── runs/
    └── R001/
        ├── run-packet.json
        ├── state.json
        ├── plan-gap.json          # 必要な場合
        ├── tasks/
        │   └── T001/
        │       ├── verification.json
        │       ├── review-round-1.json
        │       └── ...
        ├── integration-verification.json
        ├── integration-review.json
        └── run-report.md
```

## Review convergenceとGit境界

- Reviewerはproposalのみ。Terraが`ACCEPT / DEFER / REJECT / ESCALATE`で裁定
- Reviewは最大2 round
- Round 1でFinding Freeze
- Round 2の新規Findingはfix起因の重大regressionだけ
- VerificationとReviewは同じstaged `candidate_tree`へ束縛
- TerraだけがTask commitを作成し、review済みtreeとcommit treeの一致をhelperが確認
- Run末尾にはRun-level verification + fresh Sol Integration Reviewが必須
- Integration Reviewで新しい設計判断が必要ならTerraは修正設計せずMainへ戻す

## インストール

Full Sourceを展開したrootで:

```bash
codex --enable plugins plugin marketplace add "$(pwd)" --json
codex --enable plugins plugin add maestra@maestra-local --json
```

新しいCodex sessionを開始後、対象Git repositoryでまず:

```text
$maestra:doctor
```

DoctorはCodex rolloutの親子thread chain、記録済み`spawn_agent`引数、子の`turn_context.model` / `turn_context.effort`を照合します。routing proofはCodex versionとMaestra versionにbindされ、どちらかを更新したら再Doctorが必要です。

## 推奨利用

```text
$maestra:doctor                  # optional / first-time verification
  ↓ PASS（workflowは未開始）
$maestra:using-maestra

新しい認証機能を追加したいです。
まず設計から相談したいです。
  ↓
Brainstorm
  ↓
Spec → User Approval
  ↓
Detailed Plan → User Approval
  ↓
/compact 推奨
  ↓
Run 1 → Main Gate
  ↓
Run 2 → Main Gate
  ↓ ...
Finish → User Report
```

## 既存repositoryへのside-by-side追加

```bash
python3 tools/install_into_existing_repo.py --target /path/to/existing/plugin-repository
```

既存Plugin entryは保持します。詳細は`MIGRATION_FROM_GATELEDGER.md`を参照してください。

## ローカル検証

```bash
python3 tools/validate_plugin.py
python3 -m pytest -q
python3 plugins/maestra/skills/run/scripts/maestra.py --help
python3 tools/package_release.py --output /tmp/maestra-release
```

認証済みCodexでの実model routingは`$maestra:doctor`のlive probeとローカルrollout metadataで確認します。model自己申告や`list_agents`の状態だけではPASSになりません。
