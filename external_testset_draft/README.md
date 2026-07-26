# External family-level test set - FROZEN v1.0

> ## ✅ FROZEN v1.0 - LOCKED 2026-07-25
> **Reviewed by a professional PLC programmer / industrial-automation engineer** (review
> captured in `REVIEW_SHEET.xlsx`). Every MUST-FIX correction from that review has been
> applied, the reference solutions have been **re-verified under the local dual-oracle
> harness (12/12 pass** - MATIEC compile + nuXmv all-properties + all interpreter
> scenarios, no TON `Q`-before-call, no `T#1s`), and the set is now **frozen**. The
> one-way **LOCK PROTOCOL (below) is IN FORCE**: no further edits to tasks, references,
> properties, or scenarios; a single confirmatory evaluation per system; any post-lock
> change requires a NEW version id.
>
> **What the review changed** (summary; full per-task log in
> `docs/16_EXTERNAL_TESTSET_FREEZE.md`): reference-code corrections to **X05** (a held
> Reset must not defeat the position-timeout jam latch) and to **X06** and **X11** (a
> held StartCmd must not restart the machine straight through a trip/lockout reset);
> added safety properties and confirming scenarios across most tasks; the X10 one-hot
> wording tightened from "exactly one" to "at most one" pulse valve; and
> documentation-only clarifications (units, illustrative setpoints, brake-coil polarity,
> scope notes). Reviewer options recorded as **declined-for-v1** (output renames,
> converse/duplicate properties, NC-signal inversions, ELSE-recovery, a discrepancy
> latch) are enumerated in the freeze log. This directory is kept **out of `benchmark/`**
> so it cannot contaminate the released benchmark.

## Purpose
A candidate **external, family-level held-out test set**: 12 tasks whose control-logic
**families do not appear** in the 22-task benchmark (`benchmark/tasks/`) or in the SFT
training families. The intent is a *distribution-shift* probe - evaluate a
benchmark-tuned / SFT'd / RL'd model on control structures it has never been optimized
against, to separate genuine generalization from benchmark-family memorization.

"Family-level disjoint" is stricter than "task-level disjoint": it is not enough that
the surface story differs; the **primary control structure and the class of safety
property** must differ from every existing family.

## Explicitly avoided families (must NOT be the primary structure of any task)
multi-guard interlocks · e-stop buses · on-delay timing (as a start permissive) ·
override cutouts · bounded counters · two-output mutual exclusion · hysteresis ·
safety chains · two-speed drives · up/down counters · ordered start pairs.

(TON timers and an E-stop input still appear where physically unavoidable - they are
part of the required verification subset - but never as the *novel* structure. E.g.
several tasks use a TON, but for **fault confirmation / dwell / anti-cycle / reset-gating**,
never as an on-delay motor start.)

## The 12 tasks

| ID | Tier | Family | Structurally new element | Avoids (existing families) |
|----|------|--------|--------------------------|----------------------------|
| X01 | easy | Cooling-tower fan staging | Monotonic capacity-staging ladder; invariant `Fan2 -> Fan1` | not counters, not mutex (stages are nested, not exclusive), not hysteresis (pure rising thresholds) |
| X02 | easy | Hoist over-travel & slack-rope | **Directional/asymmetric** motion inhibits (upper limit blocks up only; slack rope blocks down only) + brake obligation | not a single-permissive multi-guard interlock; up/down mutex is only a *secondary* property, not the point |
| X03 | easy | Oven zone door interlock | One shared access interlock gating N independent process outputs; heat-demand obligation | not hysteresis (pure thresholds, unlike a bang-bang controller); not the existing latched overtemp trip |
| X04 | easy | Vacuum pump-down valve line-up | Pressure-region valve **line-up** with a physical cross-connection prohibition + vent isolation | not two-output mutex latch, not hysteresis; valves selected by disjoint pressure regions |
| X05 | med | Diverter-gate jam detection | TON measures **time-to-confirmed-position**, latching a jam (fault timer, not a start timer) | not on-delay start; not a counter |
| X06 | med | Screw-conveyor choke protection | Sustained-blockage confirm → **trip & lockout**; downstream-first is a single feedback **permissive input** | not an ordered-start *sequence* of outputs; not on-delay start |
| X07 | med | Paint-booth airflow purge | **Continuous** purge-dwell permissive (loss of airflow instantly revokes enable) + exhaust-run obligation | not the one-shot burner-purge *sequence* (CASE state machine); not on-delay motor start |
| X08 | med | Accumulator lead/lag + relief | Fixed-role lead/lag by pressure band + over-pressure **relief obligation** + critical-low obligation | not pump *alternation* (roles fixed, no start counter); not hysteresis |
| X09 | med | Compressor load/unload | **Minimum-run AND minimum-rest** anti-short-cycle via two TONs gating a run latch; single demand threshold | not on-delay start (two timers constrain both turn-off and turn-on); not hysteresis band |
| X10 | hard | Bag-filter pulse-jet sequencer | Cyclic **one-hot** momentary-pulse sequencer (at most one valve energized) via 2 TONs + 7-state CASE | not a one-shot ordered start of persistent outputs; the one-hot invariant is the novel class |
| X11 | hard | Centrifuge imbalance trip | Latched trip whose **CLEAR path** is gated by a coast-to-rest dwell (TON on the reset side) | not on-delay start, not a plain alarm latch; timer conditions the reset, not the set |
| X12 | hard | pH-window dosing | **Three-region** window control on a scaled INT (below/inside/above band) + out-of-safe-band fault | not hysteresis (region is a pure function of the reading, no deadband memory); acid/base mutex is secondary |

**Difficulty mix:** 4 easy · 5 medium · 3 hard.

## Safety-property design
- **67 properties total** across the 12 tasks (4-7 per task).
- Deliberately biased toward **positive-output obligations** (`G(P -> Output)` forcing an
  actuator ON), to counter the documented benchmark weakness (only 2 positive obligations
  in 71). This set has **13 positive-output obligations across 10 of the 12 tasks**
  (X01 lead-fan, X02 brake, X03 heat-demand, X04 vent, X05 conveyor-run, X07 exhaust-fan,
  X08 relief + lead-pump, X10 row-1/row-2/row-3 pulses, X11 trip-on-imbalance, X12 base-dose)
 - ~1 per task, far above the ~1-per-3 target. Counting rule (reproducible): a
  positive-output obligation is `G(cond -> Output+)` whose consequent forces an output
  TRUE and whose antecedent is not a single output's own guard. The remaining 54
  properties are prohibition-/guard-style (`G(P -> !Output)`, `G(Output -> precondition)`)
  or relational invariants (e.g. the monotonic-staging invariant `G(stageN -> stageN-1)`).
- Input polarity: normally-closed (NC) sensors are used where realistic (E-stops, limit /
  slack-rope / plug switches). Polarity is documented in each `nl_spec` and in the `.st`
  comments. **Reviewer must confirm each polarity against real field practice.**

## Verification status (local harness, frozen v1.0)
Run:
```
wsl bash toolchain/wsl_analysis.sh analysis/check_external_draft.py
```
The checker points the plcbench loader at THIS directory (`load_all(external_testset_draft/tasks)`)
and runs the full dual oracle on every reference, plus two subset audits.

**Result: 12/12 references pass all gates** - MATIEC compile OK, nuXmv all 67 properties hold,
all 45 interpreter scenarios pass, **none reads a TON's `Q` before its call**, and **none uses
`T#1s`** (all presets are whole-second `T#Ns`, N ≥ 2). This proves the references are
*self-consistent and tool-valid*; **industrial correctness has additionally been checked** in
the professional PLC review that produced this frozen v1.0 (must-fix corrections applied and
re-verified - see `docs/16_EXTERNAL_TESTSET_FREEZE.md`).

## Subset constraints honored (the verification subset)
- Scalar `BOOL` / `INT` only; every `INT` has a declared `[min,max]` range in the interface.
- Control flow: `IF/ELSIF/CASE`; operators `AND/OR/NOT`, comparisons, `+ - * MOD`.
- `TON` timers only, declared in `VAR`, each called **exactly once per scan, unconditionally,
  at top level**, gated via its `IN` expression; presets are whole-second `T#Ns` with N ≥ 2
  (deliberately never `T#1s`). `Q` is always read **after** the call.
- No other function blocks; no arrays, `REAL`, or strings.

## LOCK PROTOCOL (IN FORCE as of frozen v1.0, 2026-07-25)
> **STATUS: this set is FROZEN as v1.0 (2026-07-25). Steps 1-2 below are COMPLETE;
> steps 3-5 are now BINDING.** The set is a usable held-out test set exactly because it
> has been frozen - freezing is a one-way gate:

1. **Expert review & correction. [DONE]** A professional PLC programmer reviewed every
   `nl_spec`, `reference.st`, polarity, setpoint, timing, and every safety property;
   MUST-FIX corrections were applied (X05/X06/X11 reference logic, added properties and
   scenarios, X10 wording, doc-only clarifications) and the harness re-run to 12/12.
2. **Freeze. [DONE]** The frozen version is committed and hashed in
   `FREEZE_MANIFEST.sha256`. **After freezing: no further edits** to tasks, references,
   properties, or scenarios - not even "small" ones.
3. **No method development against it.** The frozen set must never be used to pick models,
   tune prompts, choose hyperparameters, select checkpoints, design new families, or debug
   the method. It is not a dev/validation set. If you look at per-task results and change
   the method, the set is burned and must be regenerated with new families.
4. **Single confirmatory evaluation.** Each reported system is evaluated **once** on the
   frozen set, and that number is reported as-is (including regressions). Report it
   separately from the in-distribution benchmark number; the gap *is* the finding.
5. **If the set must change** after freezing (e.g. a reviewer finds a latent bug post-lock),
   treat it as a **new** set with a new version id and disclose that any prior confirmatory
   numbers were on the superseded version.

## Open questions for the PLC-professional reviewer
General:
- Are the **NC polarities** correct and complete? Should more inputs (e.g. limit switches,
  choke/plug switch, zero-speed, lid) be NC fail-safe, and are the TRUE/FALSE meanings right?
- Are **setpoints, bands, and timings** plausible (they are illustrative placeholders)? The
  discrete-time abstraction is **1 scan tick = 1 s**; `T#2s`/`T#3s`/`T#4s` therefore mean
  2/3/4 scans, not wall-clock seconds on a real PLC. Is that abstraction acceptable, or
  should presets be re-scaled for realism?
- Are any safety properties **too weak, too strong, or missing** a hazard a real engineer
  would insist on?

Task-specific:
- **X02 hoist** - Should the brake logic be true fail-safe (brake set on power/comms loss),
  and should a raise+lower conflict be an alarmed fault rather than silent no-motion?
- **X04 vacuum** - Is stopping *all* valves on E-stop the right isolation policy, or should
  a specific safe line-up (e.g. controlled vent) be commanded? Is `Pressure <= P_CROSS`
  the correct crossover convention (mbar, 1000 = atm)?
- **X06 screw conveyor** - Is a downstream **running-feedback permissive** sufficient, or is
  a genuine timed downstream-first *start sequence* required (that would move it toward the
  avoided "ordered start pairs" family - flagged intentionally)?
- **X08 accumulator** - Is it acceptable that the relief valve is modeled as **E-stop-independent**
  (pressure-driven safety device)? Should pump inhibit use a distinct de-stage band?
- **X09 compressor** - From a **cold start** the min-rest timer imposes a `MIN_REST` delay
  before the first start (modeling artifact). Acceptable, or should the rest timer be
  pre-loaded / bypassed on first power-up?
- **X10 bag filter** - Should a cleaning cycle that finishes with DP still high **re-trigger**
  automatically, and should there be a max-cycles or inter-cycle lockout?
- **X11 centrifuge** - Is a fixed coast **dwell** an acceptable proxy for "coasted to rest",
  or must it be interlocked purely on the zero-speed switch (no timer)? Should imbalance also
  latch on a *rate* rather than an absolute level?
- **X12 pH** - Is treating an **over-range** reading as "stop dosing / manual intervention"
  correct, or should extreme-high pH still dose acid? Is the scaled-INT (pH×10) representation
  acceptable, and are `PH_MIN_SAFE`/`PH_MAX_SAFE` sensible sensor limits?

## Files
```
external_testset_draft/
  README.md                     <- this file
  tasks/
    easy/   X01..X04/  (meta.json + reference.st)
    medium/ X05..X09/
    hard/   X10..X12/
```
Verifier: `analysis/check_external_draft.py` (loads THIS dir, not `benchmark/`).
