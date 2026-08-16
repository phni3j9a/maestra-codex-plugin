# GateLedgerからMaestra v0.3への移行

## 目的

GateLedgerの実証で有効だったcontext isolationとreview convergenceは残し、workflow/state machineryの肥大化は戻しません。v0.3ではさらに、**planning qualityをTerraへ委譲せずMain Solへ集約**します。

## 維持するもの

- `fork_turns:none`によるfresh context
- Main → Terra → Luna / Solのnested execution
- Luna leaf implementer / independent Sol reviewer
- Reviewer → Terra adjudication → Luna FixPacket
- Finding Freeze + max 2 review rounds
- 1 Task = 1 normal Git commit
- Run-level Integration Review
- RunReport → Main semantic gate
- fail-closed exact model routing

## 外したままのもの

- BrainstormからFinalまでを支配する巨大router
- Spec/Plan/Executionの3重独自approval
- approval digest chain
- repository lease / fsync / CAS transaction state machine
- temporary-index + exact-tree `commit-tree` transaction
- full crash-atomic recovery protocol

## v0.2以前からの重要変更

従来はMainが比較的軽いPlanを書き、TerraがTaskPacketで詳細化する余地がありました。v0.3ではこの境界を変更します。

```text
旧: Main coarse plan → Terra detailed execution planning → Luna
新: Main detailed plan → Terra mechanical execution control → Luna
```

Main Planに実装判断が足りなければ、Terraは`PLAN_GAP`で停止します。MainがPlanを改訂し、ユーザー承認後に再実行します。

## Artifact移行

Maestra runtime stateはworking treeの`.maestra/`ではなくGit metadataへ置きます。

```bash
git rev-parse --git-path maestra
```

主要Artifact:

```text
<git-path maestra>/spec.md
<git-path maestra>/plan.md
<git-path maestra>/routing-proof.json
<git-path maestra>/runs/R###/...
```

旧`.maestra/`をv0.3へ自動importはしません。必要なSpec/PlanをMainで確認し、v0.3形式として再承認する方が安全です。

## side-by-side installer

旧GateLedgerなど既存Pluginを消さずにMaestraを追加できます。

```bash
python3 tools/install_into_existing_repo.py \
  --target /path/to/existing/plugin-repository
```

marketplaceの既存entryは保持されます。

## 推奨切替手順

1. Maestra v0.3をside-by-sideで追加する。
2. `$maestra:doctor`を実行してexact routingを確認する。
3. `$maestra:using-maestra`を明示し、小さな実projectでBrainstorm → Spec approval → Detailed Plan approval → `/compact` → 1 Runを通す。
4. PLAN_GAP、Task review、Run Integration Review、Main Gateが期待どおり動くことを確認する。
5. 問題がなければ旧Pluginを通常運用から外す。

Maestra v0.3.1以降は完全opt-inです。通常prompt、Doctor、またはstandalone phase Skillだけではworkflow全体をactivateしません。
