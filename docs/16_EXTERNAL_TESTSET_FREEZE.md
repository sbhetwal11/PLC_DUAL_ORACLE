# 16 - External family-level test set: FREEZE v1.0

**Frozen:** 2026-07-25
**Reviewer:** professional PLC programmer / industrial-automation engineer (review captured in `external_testset_draft/REVIEW_SHEET.xlsx`).
**Scope of this document:** records exactly what the review changed, what it declined, the family-disjointness (freeze condition G4) audit, the final counts, the harness 12/12 evidence, and the one-way lock statement. This supersedes the DRAFT status of `external_testset_draft/`.

The set: `external_testset_draft/tasks/{easy,medium,hard}/X01..X12/` (each task = `meta.json` + `reference.st`), 12 tasks (4 easy / 5 medium / 3 hard).

---

## 1. MUST-FIX corrections applied (per task)

Legend: **[CODE]** = reference.st logic change; **[PROP]** = added safety property; **[SCEN]** = added scenario; **[NL]** = nl_spec / wording; **[DOC]** = documentation-only note.

| Task | Applied |
|------|---------|
| **X01** cooling-tower fan staging | **[SCEN]** S4: boundary sweep WaterTemp 24 → 25 → 31 → 32 (Enable/EStop healthy throughout), asserting Fan1 engages at `>= 25` and Fan2 at `>= 32` at each boundary. (No new properties - converse properties declined.) |
| **X02** hoist over-travel & slack-rope | **[PROP]** P6 `G(!LowerLimitOK -> !HoistDown)` (lower over-travel inhibits lowering); **[PROP]** P7 `G((RaiseCmd & LowerCmd) -> (!HoistUp & !HoistDown))` (simultaneous request → no motion). **[DOC]** nl_spec sentence: physical brake coil is the inverse of the logical `BrakeSet` (real hoist brakes are spring-applied / power-released). |
| **X03** oven zone door interlock | **[PROP]** P6 `G(!Enable -> (!Heater1 & !Heater2))`; **[SCEN]** S4: Enable FALSE with both zones below setpoint → both heaters FALSE. **[DOC]** stated deg C on Temp1/Temp2 and on both setpoints (SET1 = 200 deg C, SET2 = 250 deg C). |
| **X04** vacuum pump-down valve line-up | **[DOC]** (minimum option chosen) P_CROSS comment in `meta.json` and `reference.st` now reads "crossover pressure (illustrative; real systems are pump-specific, often 1-10 mbar)"; **[NL]** one nl_spec line that a real high-vacuum readiness interlock is out of scope for this easy task. Value, LTL and scenarios unchanged. (P6 declined.) |
| **X05** diverter-gate jam | **[CODE]** jam-clear branch conditioned on confirmed position so a **held Reset cannot defeat the latch**: `IF Reset AND EStop AND ((DivertCmd AND AtDivert AND NOT AtStraight) OR (NOT DivertCmd AND AtStraight AND NOT AtDivert)) THEN Jam := FALSE;`. **[SCEN]** S4: jam latched, position not confirmed, Reset held several scans → Jam stays TRUE / conveyor stays off. (Discrepancy latch declined.) |
| **X06** screw-conveyor choke | **[CODE]** trip-reset condition gains `AND NOT StartCmd`: `IF Reset AND EStop AND NOT ChokeSwitch AND NOT StartCmd THEN ChokeTrip := FALSE;` (no restart straight through a reset). **[SCEN]** S4: Reset with StartCmd held leaves the trip in; StartCmd off + Reset clears it. |
| **X07** paint-booth airflow purge | **[PROP]** P5 `G(SprayEnable -> SprayRequest)`; **[SCEN]** S4: reach the purge dwell, then drop SprayRequest → SprayEnable FALSE while ExhaustFan stays TRUE. **[DOC]** PURGE_TIME = 4 means 4 verification ticks (1 scan tick = 1 s); the E-stop-drops-fan policy is a deliberate simplification. |
| **X08** accumulator lead/lag + relief | **[PROP]** P6 `G(!Enable -> (!LeadPump & !LagPump))`; **[SCEN]** S4: Enable FALSE at low pressure → both pumps FALSE. **[DOC]** nl_spec: a direct-acting mechanical relief valve protects the accumulator independently of the PLC; `ReliefValve` here is a supplementary PLC-commanded dump/unload output. |
| **X09** compressor load/unload | **[PROP]** P5 `G(Motor -> LoadValve)`. **[DOC]** cold-start MIN_REST artifact documented in `meta.json` notes and the `reference.st` header; noted the scheme is start/stop anti-short-cycle, not a true continuous-run load/unload valve scheme. |
| **X10** bag-filter pulse-jet sequencer | **[NL]** one-hot wording "Exactly one pulse valve..." → "At most one pulse valve...". **[PROP]** P5 `G(State = 3 -> Valve2)`, P6 `G(State = 5 -> Valve3)` (each pulse row's valve obliged in its pulse state). **[SCEN]** S4: full cleaning cycle driving the sequencer through all six active states (1→6) and back to Idle, per-step expected valve outputs. (ELSE-recovery declined.) |
| **X11** centrifuge imbalance trip | **[CODE]** trip-clear condition gains `AND NOT StartCmd` (same restart-defect class as X06): `IF Reset AND ZeroSpeed AND Tcoast.Q AND (Imbalance < VIB_MAX) AND EStop AND NOT StartCmd THEN Trip := FALSE;`. **[SCEN]** S4: Reset with StartCmd held does not clear; releasing StartCmd then Reset clears. **[PROP]** P6 `G(LockedOut -> Trip)`, P7 `G(Trip -> LockedOut)`. Reference `LockedOut := Trip` is exactly biconditional with `Trip`, so P6/P7 both hold (no STOP raised). |
| **X12** pH-window dosing | **[PROP]** P6 `G((pH < 20 | pH > 120) -> (!AcidValve & !BaseValve))`, P7 `G(!Enable -> (!AcidValve & !BaseValve))`; **[SCEN]** S4: Enable FALSE → both valves FALSE. **[DOC]** nl_spec: the 2.0-12.0 auto-dosing band is a plant policy choice, not a probe limitation. (P8 converse declined.) |

**Reference-code fixes (X05, X06, X11)** were part of this review brief (they make the references consistent with the corrected reset semantics). After each fix the full harness was re-run; all pre-existing properties and scenarios continue to hold, and no newly-added property failed on any reference. **No STOP conflicts were encountered.**

---

## 2. Reviewer options DECLINED for v1 (recorded, not applied)

These are owner-decision items the mentor declined for v1; they are recorded here so the decision is auditable and so a future v2 can revisit them.

| Task | Declined option |
|------|-----------------|
| X01 | Converse (positive-staging) properties. |
| X02 | `BrakeSet` → `BrakeRelease` rename. |
| X04 | Extra property P6; the minimum documentation option was chosen instead. High-vac readiness interlock kept out of scope (noted). |
| X05 | Command/position **discrepancy latch**. |
| X06 | Inverting the choke switch to NC `ChokeOK` sense - recorded as a **recommendation** for a real deployment, not applied. |
| X07 | (none beyond the documented E-stop-simplification note.) |
| X08 | `ReliefValve` → `DumpValve` rename. |
| X09 | Retitle; explicit X-operator (`next`) timing properties. |
| X10 | ELSE-branch state-recovery logic. |
| X11 | Output renames. |
| X12 | Converse property P8. |

Cross-cutting: all output/variable **renames** were declined for v1 (stability of the frozen interface), as were **converse/duplicate** properties beyond those explicitly added above.

Note: the per-task `reference.st` header comments and the `"draft"` tag/notes prefixes were **left as-authored** (the authoritative edit list did not request scrubbing them); freeze status is asserted at the set level via this document, the README banner, and `FREEZE_MANIFEST.sha256`.

---

## 3. Family-disjointness audit (freeze condition G4)

Comparison corpus:
- **22 benchmark tasks** (`benchmark/tasks/**`): E01-E07 (easy), M01-M11 (medium), H01-H04 (hard).
- **11 SFT procedural families** (`finetune/datagen.py`): `multi_guard`, `estop_bus`, `ondelay`, `override_cutout`, `bounded_counter`, `exclusive_two`, `hysteresis`, `safety_chain`, `bounded_updown`, `ordered_pair`, `two_speed`.

For each X-task: its **primary control structure** and **primary property class**, the nearest existing family, and why it is disjoint (primary structure **and** property class must both differ - a mere secondary-property shape overlap is not a violation).

| X | Primary control structure | Primary property class | Nearest benchmark / SFT family | Disjoint because |
|---|---------------------------|------------------------|--------------------------------|------------------|
| X01 | Monotonic capacity-**staging ladder** on an analog input (nested rising thresholds, combinational) | Staging invariant `G(Fan2 -> Fan1)` + lead positive obligation | `ordered_pair` (`G(B->A)`); E02 hysteresis | ordered_pair is a **latched** start-sequence (Start buttons, memory); X01 is combinational threshold selection, no latch. Not hysteresis: pure rising thresholds, no deadband memory. |
| X02 | Combinational **asymmetric directional inhibit** (upper limit → up only; lower/slack → down only) + brake obligation | Direction-specific inhibits + positive brake obligation `G((!Up & !Down) -> BrakeSet)` | `multi_guard`/`safety_chain` (symmetric permissive AND); H02 limit props | multi_guard/safety_chain gate ONE output with ALL guards (symmetric). X02's guards are direction-specific and it adds a brake positive obligation. H02 is an elevator CASE state machine; X02 is combinational. |
| X03 | One **shared access interlock** gating N independent threshold outputs | Interlock → all-off + per-zone threshold + heat-demand positive obligation | E06 heater over-temp (`override_cutout`) | E06/override_cutout gate a SINGLE output; X03 shares one interlock across two independent thermostats and adds a positive heat-demand obligation. Pure thresholds, not hysteresis. |
| X04 | Pressure-region **valve line-up** with cross-connection prohibition + vent isolation | Cross-connection mutex `G(!(Rough & HiVac))` + vent isolation + vent positive obligation | `exclusive_two`; E03 airlock | exclusive_two / airlock is a plain two-output latch mutex. X04 selects three valves by disjoint pressure REGIONS with a physical cross-connection + vent-isolation prohibition; no latch. |
| X05 | **Position-confirmation timeout** (TON times how long a commanded position is unconfirmed → latch jam) | Jam → line-stopped prohibitions + conveyor positive obligation | `ondelay`; M01 | ondelay/M01 use the TON as a START permissive. X05's TON is a FAULT-confirmation timer; no benchmark/SFT family times a fault-to-confirm. |
| X06 | **Sustained-blockage trip & lockout** (TON confirms a persistent choke) + single downstream feedback permissive | Trip → motor-off lockout + downstream-first permissive `G(Screw -> Downstream)` | `ondelay`; M05/M10 ordered start | The downstream-first gate is a single running-feedback INPUT, not a timed ordered-START sequence of outputs (M05/M10). The sustained-fault trip-lockout via TON is new. |
| X07 | **Continuous prove-airflow purge dwell** (TON permissive re-satisfied every scan; instant revoke) + exhaust obligation | Spray-permit guards + exhaust-fan positive obligation | M06 burner purge (CASE sequence); `ondelay` | M06 is a one-shot ignition SEQUENCE (latched CASE). X07's purge is a continuous permissive (losing airflow instantly revokes enable), not a latched state; adds a fan positive obligation. |
| X08 | **Fixed-role lead/lag** pressure staging by band + over-pressure relief | Over-pressure → pumps-off + relief & lead positive obligations + staging invariant | M08 pump alternation; X01 (within-set) | M08 ALTERNATES roles via edge-detect toggle; X08 has FIXED roles by pressure band, no start counter. Shares the nested rising-threshold staging skeleton with X01 (diversity note, §5). |
| X09 | **Min-run AND min-rest** anti-short-cycle via TWO TONs gating a run latch; single demand threshold | E-stop/disable → off + load-tracks-motor coupling | `ondelay`; M01 | ondelay/M01 is ONE timer permitting a start. X09 uses two timers to constrain BOTH turn-off (min-run) and turn-on (min-rest). No hysteresis band. |
| X10 | **Cyclic one-hot momentary-pulse sequencer** (2 TONs + 7-state CASE) | One-hot header-protection `G(!(Vi & Vj))` + per-state positive pulse obligations | H01/M02/M03 (CASE + mutex); M06 | H01/M02/M03/M06 sequence PERSISTENT outputs (phase greens, contactors, ordered starts). X10's outputs are MOMENTARY, mutually-exclusive PULSES in a repeating cycle; the at-most-one one-hot invariant is the novel class. |
| X11 | Latched trip whose **CLEAR path is gated by a coast-to-rest dwell** (TON on the reset side) | Trip/lid/estop → drive-off + trip positive obligation + lockout mirror | E05 alarm latch; `ondelay` | E05 is a set-dominant latch with no timer on clear; ondelay times the SET path. X11's TON conditions the CLEAR/reset path - inverse placement. |
| X12 | **Three-region window control** on a scaled INT (below/inside/above band) + out-of-safe-band fault | Over-range/disable → dosing-off + region prohibitions + base positive obligation (acid/base mutex secondary) | `hysteresis`; `exclusive_two` | hysteresis is two-point with latched deadband MEMORY; X12's region is a pure function of the current reading (no memory), three regions, plus an over-range fault. Mutex is secondary. |

**Result: PASS.** Every X-task's primary control structure and primary property class is disjoint from all 22 benchmark tasks and all 11 SFT families. Where a *secondary* property shape recurs elsewhere (e.g. the `G(B -> A)` implication shape in X01/X08 vs `ordered_pair`; directional limit props in X02 vs H02; the one-hot/mutex shape in X10 vs H01/M02), the **primary structure still differs**, so the disjointness condition holds.

### Diversity note (not a disjointness violation)
Per the reviewer's internal observation, **X01 and X08 share a nested rising-threshold capacity-staging skeleton** (stage-N-implies-stage-N-1). This is an intra-set diversity observation, not a family-disjointness violation against the benchmark or SFT corpus: both remain disjoint from every existing family, and they differ from each other in process, I/O, and the relief/critical-low obligations that X08 adds.

---

## 4. Final counts (recounted from the frozen files)

Recounted directly from the 12 `meta.json` files (not from arithmetic).

| Task | Properties | Scenarios |
|------|-----------:|----------:|
| X01 | 4 | 4 |
| X02 | 7 | 3 |
| X03 | 6 | 4 |
| X04 | 5 | 3 |
| X05 | 5 | 4 |
| X06 | 4 | 4 |
| X07 | 5 | 4 |
| X08 | 6 | 4 |
| X09 | 5 | 3 |
| X10 | 6 | 4 |
| X11 | 7 | 4 |
| X12 | 7 | 4 |
| **Total** | **67** | **45** |

- **Properties: 67** (was 55 in draft; +12 added: X02 +2, X03 +1, X07 +1, X08 +1, X09 +1, X10 +2, X11 +2, X12 +2).
- **Scenarios: 45** (was 36; +9 added: one S4 each on X01, X03, X05, X06, X07, X08, X10, X11, X12).
- **Positive-output obligations: 13** across **10 of the 12 tasks** (X01, X02, X03, X04, X05, X07, X08, X10, X11, X12; X06 and X09 have none). Counting rule (reproducible): a positive-output obligation is `G(cond -> Output+)` whose consequent forces an output TRUE and whose antecedent is not a single output's own guard. This excludes monotonic-staging invariants (`G(Fan2 -> Fan1)`, `G(LagPump -> LeadPump)`) and necessary-condition guards (`G(LoadValve -> Motor)`, `G(SprayEnable -> ExhaustFan)`), which are classified as invariants / prohibitions. The 13:
 - X01 P4 `G((Enable & EStop & WaterTemp >= 25) -> Fan1)`
 - X02 P5 `G((!HoistUp & !HoistDown) -> BrakeSet)`
 - X03 P5 `G((EStop & Enable & DoorClosed & Temp1 < 200) -> Heater1)`
 - X04 P5 `G((EStop & VentCmd) -> VentValve)`
 - X05 P5 `G((EStop & !Jam & RunConveyor) -> ConveyorRun)`
 - X07 P4 `G((FanCmd & EStop) -> ExhaustFan)`
 - X08 P2 `G(Pressure >= 280 -> ReliefValve)`
 - X08 P5 `G((EStop & Enable & Pressure < 120) -> LeadPump)`
 - X10 P4 `G(State = 1 -> Valve1)`
 - X10 P5 `G(State = 3 -> Valve2)` *(new)*
 - X10 P6 `G(State = 5 -> Valve3)` *(new)*
 - X11 P5 `G((Imbalance >= 70 & EStop) -> Trip)`
 - X12 P5 `G((EStop & Enable & Agitator & pH >= 20 & pH <= 120 & pH < 65) -> BaseValve)`

  (The two new ones vs the draft's 11 are the X10 row-2 and row-3 per-state pulse obligations.)
- **Difficulty mix:** 4 easy · 5 medium · 3 hard (unchanged).

---

## 5. Harness re-verification evidence (12/12)

Command (from repo root):
```
wsl bash toolchain/wsl_analysis.sh analysis/check_external_draft.py
```
Environment: WSL, `nuXmv` 2.2.0 + MATIEC `iec2c`. The checker loads `external_testset_draft/tasks`, runs compile + all properties + all scenarios on every reference, and audits the two subset rules (no TON `Q` read before its call; no `T#1s` preset).

Final run (after all edits):
```
OK X01_cooling_tower_fan_staging   compile=OK verify=OK props=4/4 scen=4/4 Qbeforecall=False T#1s=False
OK X02_hoist_overtravel_slackrope  compile=OK verify=OK props=7/7 scen=3/3 Qbeforecall=False T#1s=False
OK X03_oven_zone_door_interlock    compile=OK verify=OK props=6/6 scen=4/4 Qbeforecall=False T#1s=False
OK X04_vacuum_pumpdown_valves      compile=OK verify=OK props=5/5 scen=3/3 Qbeforecall=False T#1s=False
OK X05_diverter_gate_jam           compile=OK verify=OK props=5/5 scen=4/4 Qbeforecall=False T#1s=False
OK X06_screw_conveyor_choke        compile=OK verify=OK props=4/4 scen=4/4 Qbeforecall=False T#1s=False
OK X07_paint_booth_purge           compile=OK verify=OK props=5/5 scen=4/4 Qbeforecall=False T#1s=False
OK X08_accumulator_leadlag_pumps   compile=OK verify=OK props=6/6 scen=4/4 Qbeforecall=False T#1s=False
OK X09_compressor_load_unload      compile=OK verify=OK props=5/5 scen=3/3 Qbeforecall=False T#1s=False
OK X10_bagfilter_pulsejet_sequencer compile=OK verify=OK props=6/6 scen=4/4 Qbeforecall=False T#1s=False
OK X11_centrifuge_imbalance_trip   compile=OK verify=OK props=7/7 scen=4/4 Qbeforecall=False T#1s=False
OK X12_ph_window_dosing            compile=OK verify=OK props=7/7 scen=4/4 Qbeforecall=False T#1s=False

SUMMARY: 12/12 references pass all gates (compile + verify + scenarios + no-Q-before-call + no-T#1s)
```

---

## 6. Freeze manifest

`external_testset_draft/FREEZE_MANIFEST.sha256` contains SHA-256 digests of **25 files** - all 12 `meta.json`, all 12 `reference.st`, and `README.md` - generated after every edit above. Verify with:
```
cd external_testset_draft && sha256sum -c FREEZE_MANIFEST.sha256
```
(All 25 verified OK at freeze time.)

---

## 7. One-way lock statement

**This set is FROZEN as external test set v1.0 (2026-07-25).** The lock is one-way:

1. **No further edits** to any task, reference, property, or scenario in `external_testset_draft/` - not even "small" ones.
2. **No method development against it.** It is a held-out distribution-shift probe, not a dev/validation set: it must never be used to select models, tune prompts, choose hyperparameters, select checkpoints, design families, or debug the method. Looking at per-task results and then changing the method **burns the set**.
3. **Single confirmatory evaluation** per system, reported as-is (including regressions), separately from the in-distribution benchmark number; the gap is the finding.
4. **Any post-lock change** (e.g. a latent bug found later) creates a **new version id**, and any prior confirmatory numbers are disclosed as being on the superseded version.

Integrity of the frozen bytes is anchored by `FREEZE_MANIFEST.sha256`. The 22-task `benchmark/`, `paper/`, `plcbench/`, and `results/` were **not** touched by this freeze.
