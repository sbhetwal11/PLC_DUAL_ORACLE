# 17 - Benchmark Errata (22-task benchmark, v1.0)

**Status:** Errata for the FROZEN v1.0 benchmark (`benchmark/tasks/**`).
**Source of findings:** author-side rubric-based expert review, `docs/review_package/SUMMARY_SHEET.csv` (10 dimensions D1-D10, 3-point Acceptable/Minor-issue/Defect anchors; rubric in `docs/review_package/RUBRIC.md`).
**Reviewer:** an author of the paper who is a professional PLC programmer / industrial-automation engineer. This is an **author-side** review (a qualified-practitioner audit), **not** independent validation. A multi-reviewer pass by external non-author engineers, with inter-reviewer agreement (`compute_agreement.py`), remains outstanding.

---

## 1. Disposition (read this first)

- The evaluated benchmark is **frozen at v1.0**. Every published number in the paper was produced against these exact frozen files. **Nothing has been retro-patched.** Silently patching the property/scenario suites would invalidate every published number.
- **All 22 reference solutions remain machine-green** against the v1.0 property and scenario suites (each reference compiles under MATIEC and verifies every stated property under nuXmv, and reproduces every stated scenario). The defects below are places where the **formal suite under-constrains the natural-language (NL) spec** - i.e., an unsafe-but-passing implementation is admitted - **or** (E03, and the H04 author note) where the **spec wording itself is off**. They are **not** cases where a reference violates its own encoded checks.
- **Impact on results:** because every evaluated system (frontier APIs, trained models, degenerate baselines) was scored by the **same oracle**, **relative model comparisons are unaffected**. Only **absolute "verified-safe" readings** must be qualified: "verified" means *compiles + passes the v1.0 property/scenario suite*, which - as these findings show - is bounded by property completeness, not full functional/plant safety.
- **Fix policy:** the corrections suggested below may be applied **only as a clearly versioned artifact update after publication** (a new benchmark version id), never as a silent edit to v1.0. Any confirmatory number reported later on a patched set must disclose the version it ran on.

### Aggregate (220 scored cells = 22 tasks × 10 dimensions)

| | Acceptable | Minor issue | Defect |
|---|---:|---:|---:|
| **Cells** | 160 | 45 | 15 |

**Overall verdicts:** 1 Accept (M04) · 18 Accept-with-fixes · 3 Reject-level (M06, H03, H04).
**Tasks carrying a blocking defect (7):** E03, M02, M03, M06, M07, H03, H04.

### Per-dimension counts

| Dim | Dimension | Acceptable | Minor | Defect |
|-----|-----------|-----------:|------:|-------:|
| D1  | Requirement realism            | 12 | 10 | 0 |
| D2  | Input/output polarity correctness | 20 | 2 | 0 |
| D3  | Scan-cycle behavior            | 19 | 2  | 1 |
| D4  | Timer semantics and presets    | 19 | 2  | 1 |
| D5  | Fault / restart handling       | 15 | 5  | 2 |
| D6  | Safety-property completeness   | 9  | 8  | 5 |
| D7  | Property correctness (LTL vs NL) | 20 | 1 | 1 |
| D8  | Scenario coverage              | 10 | 10 | 2 |
| D9  | Reference-solution correctness | 18 | 1  | 3 |
| D10 | Tier assignment                | 18 | 4  | 0 |
| -   | **Total**                      | **160** | **45** | **15** |

**Zero defects on D1 (requirement realism), D2 (polarity), and D10 (tier labels).** Defects concentrate in **D6 (safety-property completeness)** - the weakest dimension at 5 Defect + 8 Minor - which independently corroborates the paper's own positive-obligation-scarcity / vacuity analysis (Section V-C; Sec. S.XV): the property *suites*, not the task premises, are where the benchmark is thinnest.

---

## 2. The 15 Defect cells

| # | Task | Dim | Dimension | What is wrong (place the formal suite under-constrains the NL spec, unless noted) |
|---|------|-----|-----------|-----------------------------------------------------------------------------------|
| 1 | E03 | D9 | Reference-solution correctness | Spec text says door A wins a tie, but the reference keeps an already-open B open, so A does not "win". (The reference is the *safer* behavior; the **spec wording** is the fault.) |
| 2 | M02 | D6 | Safety-property completeness | Break-before-make (dead-time) is neither required nor checked; the one-scan star→delta transfer passes the per-scan exclusion property. |
| 3 | M03 | D5 | Fault / restart handling | No property forbids `CarYellow & CarRed`; unsafe code lighting both aspects passes P1-P4. |
| 4 | M06 | D5 | Fault / restart handling | Failed ignition returns to a reusable `Off` and a held StartPB retries automatically - no lockout, auto-retry hazardous for combustion equipment. |
| 5 | M06 | D6 | Safety-property completeness | No lockout-after-failed-ignition property and no purge-before-fuel / flame-loss property. |
| 6 | M06 | D8 | Scenario coverage | No failed-trial or flame-loss trace, so the central supervision behavior is never demonstrated. |
| 7 | M07 | D6 | Safety-property completeness | The anti-tie-down property (P2) references only the internal `Armed` bit; forcing `Armed` TRUE defeats the function yet passes. |
| 8 | H03 | D4 | Timer semantics and presets | Reaction timer counts on State 3 alone, so the dwell can complete with heater/agitator inhibited (against the spec's "keep heating and agitating"). |
| 9 | H03 | D6 | Safety-property completeness | No over-temperature property although `Temp` is a free input up to 200. |
| 10 | H03 | D8 | Scenario coverage | No trace reaches `Drain` or returns to Idle. |
| 11 | H03 | D9 | Reference-solution correctness | `Fill` also opens for one scan when a batch starts above 80. |
| 12 | H04 | D3 | Scan-cycle behavior | Simultaneous entry and exit edges at capacity net −1 (not 0), dropping `FullSign` while the garage is still full. |
| 13 | H04 | D6 | Safety-property completeness | No `Count >= 0` lower-bound property. |
| 14 | H04 | D7 | Property correctness (LTL vs NL) | P3 NL says full sign *exactly* at capacity, but the formula is one-way; a solution that never asserts `FullSign` passes everything and can open the barrier when full. |
| 15 | H04 | D9 | Reference-solution correctness | The author note (claiming the simultaneous-edge case nets zero) is wrong; the biconditional/lower-bound/edge rule all need fixing. |

(Total: E03 ×1, M02 ×1, M03 ×1, M06 ×3, M07 ×1, H03 ×4, H04 ×4 = 15.)

---

## 3. Per-task findings (verbatim from `SUMMARY_SHEET.csv` notes)

Blocking = the task carries at least one Defect on a critical dimension (a place unsafe-but-passing code is admitted, or a spec/reference fault). "Verdict" and "Blocking" are the reviewer's `overall_verdict` / `blocking_defect` columns.

| Task | Tier | Verdict | Blocking | Finding (reviewer note, verbatim) |
|------|------|---------|:--------:|-----------------------------------|
| E01 motor interlock | easy | Accept-with-fixes | No | Seal-in and e-stop logic correct. Add a Start+Stop same-scan trace to prove stop priority. |
| E02 tank overflow | easy | Accept-with-fixes | No | Hysteresis and overflow logic correct. Sole trace jumps over the 11-89 hold band; add a mid-band step. |
| E03 airlock interlock | easy | Accept-with-fixes | **Yes** | Spec says A always wins a tie. With B already open the reference keeps B open, so A does not win. Keeping B open is the safer behavior, so narrow the spec wording to the both-closed case or change the code. Add a B-open both-commands trace and a priority property. |
| E04 conveyor permissive | easy | Accept-with-fixes | No | Interlocks correct. State whether a held StartPB may relatch the instant a guard or fault clears. Add a refused-start trace. |
| E05 alarm latch | easy | Accept-with-fixes | No | Set-dominant latch correct. P2 retention formula with X is valid but easy to misread; add a timing note. |
| E06 heater over-temp | easy | Accept-with-fixes | No | Logic correct. OverTemp active-high is consistent but a broken wire will not trip; document the assumption. |
| E07 pump dry-run protection | easy | Accept-with-fixes | No | Logic correct. Same active-high caveat as E06. State that auto-restart after LowLevel clears is intended. |
| M01 motor startup delay | medium | Accept-with-fixes | No | Timer and traces correct. No property blocks an early start; a no-delay solution passes P1 and P2 and only the trace catches it. Add a no-early-start property if properties alone are scored. |
| M02 star-delta starter | medium | Accept-with-fixes | **Yes** | Star to delta transfer happens in one scan with no all-off interval. Per-scan exclusion holds but break-before-make is neither required nor checked; on a real starter that risks a phase short through the star arc. Add a dead-time state and a property forbidding delta the scan after star. |
| M03 pedestrian crossing | medium | Accept-with-fixes | **Yes** | Spec says only one car aspect may be lit, but no property forbids yellow with red. Unsafe code passes P1-P4. One line fix: G(!(CarYellow & CarRed)). First green phase also shows one tick short of PT_GREEN in the trace model; define trace sampling. |
| M04 tank fill/drain cycle | medium | Accept | No | Properties, traces, and reference are mutually consistent. No changes. |
| M05 conveyor sequence | medium | Accept-with-fixes | No | Sequence and reference correct. G(C1 -> C2) permits a simultaneous start; the two-tick lead lives only in the trace. Add a temporal property if the delay must be model-checked. |
| M06 burner purge sequence | medium | **Reject** | **Yes** | Failed ignition returns to a reusable Off and a held StartPB retries automatically. No lockout state, no purge-before-fuel or flame-loss property, and no failed-trial or flame-loss trace, so the central supervision behavior is never verified or demonstrated. Not defensible for combustion equipment. Rework with lockout and flame supervision, then retier. |
| M07 two-hand control | medium | Accept-with-fixes | **Yes** | Traces prove anti-tie-down but the properties do not. P2 only references the internal Armed bit; setting Armed TRUE permanently defeats the function and still passes both properties. Add a both-released rearm history property. |
| M08 pump alternation | medium | Accept-with-fixes | No | Exclusion and edge logic correct. Alternation itself is not formally verified and e-stop recovery is untested. State the lead-retention policy across e-stop. |
| M09 gate limits obstruction | medium | Accept-with-fixes | No | Correct throughout. Stop-only obstruction response is a simplification; note that real operators usually reverse or reopen. |
| M10 three-conveyor start | medium | Accept-with-fixes | No | Staged start correct. Ordering properties allow all three conveyors to start together; both delays live only in the trace. Add an EStop trace. Two-timer task sits at the medium-hard boundary; align tier anchors with M03 and M06. |
| M11 dosing counter | medium | Accept-with-fixes | No | Counter correct. Properties are one-way; add Count >= 0 and Done-at-target if counting behavior is scored. Test a held trigger and a pulse at cap. |
| H01 intersection signals | hard | Accept-with-fixes | No | Cross-conflict logic sound. Single partial trace; add a full six-phase cycle with all outputs constrained, plus per-direction one-hot properties. Define first-phase trace sampling. |
| H02 elevator door interlock | hard | Accept-with-fixes | No | Safety gating correct. Four states, no timer, comparable to medium M09; relabel or strengthen the task. State the pause-resume door policy and note that State can advance from limits while motion is paused. |
| H03 batch reactor sequence | hard | **Reject** | **Yes** | Reaction timer counts on State 3 alone, so the dwell can complete with heater and agitator inhibited at low level, against the spec text keep heating and agitating. No over-temperature property although Temp is a free input to 200. No trace reaches Drain or return to Idle. Fill also opens one scan when a batch starts above 80. Rework timer gating, add the temp property, extend traces. |
| H04 parking garage counter | hard | **Reject** | **Yes** | P3 NL says full sign exactly at capacity but the formula is one-way; a solution that never asserts FullSign passes everything and can open the barrier when full. No Count >= 0 property. Simultaneous entry and exit edges at capacity net minus one, not zero, dropping FullSign with the garage still full; the author note is wrong. Fix the biconditional, add the lower bound, define the simultaneous-edge rule. |

---

## 4. Cross-reference

- Paper (main): benchmark-validation caveat in Section III-B reports this executed review; the Threats section folds in the "7 of 22 tasks admit unsafe-but-passing implementations" finding.
- Supplement: Sec. S.XX ("Expert Review of the Benchmark and External Test-Set Freeze") + Table S-XVII (per-dimension counts) present the full summary.
- External test set (separate artifact, frozen v1.0): `docs/16_EXTERNAL_TESTSET_FREEZE.md`. That set is NOT evaluated in this paper.
</content>
</invoke>
