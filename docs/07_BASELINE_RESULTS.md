# 07 - Baseline Results (frontier LLMs)

> **⭐ HEADLINE (dual-oracle, compile + verify) - this supersedes the nuXmv-only
> numbers further down.** Run 2026-06-09 with the FULL pipeline: a candidate is
> **verified** only if it (1) compiles in MATIEC (a real IEC 61131-3 compiler) AND
> (2) all safety properties hold in nuXmv. 22 tasks, 1 sample/task.
> Raw: `source/baseline_compileverify_2026-06-09/*.json`.
>
> | Model | verified | unsafe | parse_err | compile_err | easy / med / hard |
> |---|---|---|---|---|---|
> | grok-3 | **0.636** (14/22) | 0.045 | 0.136 | 0.045 | 0.71 / 0.64 / 0.50 |
> | claude-sonnet-4-6 | **0.545** (12/22) | 0.0 | 0.364 | 0.0 | 1.0 / 0.27 / 0.50 |
> | gemini-2.5-flash | **0.045** (1/22) | 0.0 | 0.909 | 0.045 | 0.14 / 0 / 0 |
> | gpt-4o | **0.000** (0/22) | 0.0 | 0.545 | 0.455 | 0 / 0 / 0 |
>
> **Key methodological finding:** model-checking ALONE overestimates LLM PLC quality.
> GPT-4o drops from 0.28 (nuXmv-only) to **0.0** once a real compiler is required - its
> code parses + model-checks as "safe" but does not compile (10/22 compile_errors).
> Grok-3 and Claude write standards-compliant ST and hold up; GPT-4o and Gemini collapse.
> Grok-3 produced 1 genuinely UNSAFE solution (compiles + runs, violates a property) - 
> evidence the safety oracle catches real violations.
>
> **Caveat:** `parse_error` here = our nuXmv-translator subset rejected it (a harness
> limitation), distinct from `compile_error` = MATIEC (real compiler) rejected it. Some
> parse_errors may be valid IEC that our translator doesn't yet cover; future work =
> widen the translator / drive it off the MATIEC AST. `compile_error` is unambiguous.
>
> **Run-to-run variance (single sample @ provider default temperature ≈ stochastic).**
> Two independent dual-oracle runs:
>
> | Model | run 1 | run 2 |
> |---|---|---|
> | grok-3 | 0.636 | 0.682 |
> | claude-sonnet-4-6 | 0.545 | 0.682 |
> | gemini-2.5-flash | 0.045 | 0.182 |
> | gpt-4o | 0.000 | 0.091 |
>
> Ranking is stable (grok/claude top; gemini/gpt-4o bottom) but point estimates move
> by up to ~0.14. **Therefore: do NOT report single-sample numbers.** The canonical
> tables are the compile+verify pass@k below.
>
> ## ⭐⭐ CANONICAL: compile+verify pass@k, n=10, temp 0.8 (the paper tables)
> Raw: `source/passk_compileverify_n10_2026-06-09/*.json`. verified = compiles
> (MATIEC) AND all safety properties hold (nuXmv).
>
> | Model | pass@1 | pass@3 | pass@5 | pass@10 |
> |---|---|---|---|---|
> | grok-3 | 0.645 | 0.817 | 0.881 | **0.955** |
> | claude-sonnet-4-6 | 0.564 | 0.611 | 0.635 | 0.682 |
> | gemini-2.5-flash | 0.095 | 0.172 | 0.204 | 0.273 |
> | gpt-4o | 0.091 | 0.161 | 0.196 | 0.227 |
>
> pass@1 by tier (easy / medium / hard):
> grok-3 0.857 / 0.536 / 0.575 · claude 1.00 / 0.318 / 0.475 ·
> gemini 0.20 / 0.00 / 0.175 · gpt-4o 0.157 / 0.082 / 0.00.
>
> Findings: (1) grok-3 ≫ claude ≫ gemini ≈ gpt-4o. (2) **Systematic vs stochastic** - 
> grok-3 0.645→0.955 across k (sampling recovers), claude ~flat 0.564→0.682
> (systematic). (3) **Tier walls** - gpt-4o verifies 0 hard tasks at any k; gemini
> verifies 0 medium tasks at any k. (4) medium tier is the binding constraint for the
> strong models. These supersede all earlier (single-sample / nuXmv-only) numbers.
>
> ### RQ2 exact: safety-only vs dual-oracle pass@1 (matched n=10)
> Raw: `source/passk_nuxmvonly_n10_2026-06-28/*.json` vs the compile+verify snapshot.
>
> | Model | safety-only | dual-oracle | retained |
> |---|---|---|---|
> | grok-3 | 0.745 | 0.645 | 0.87 |
> | claude-sonnet-4-6 | 0.591 | 0.564 | 0.95 |
> | gemini-2.5-flash | 0.155 | 0.095 | 0.61 |
> | gpt-4o | 0.295 | 0.091 | **0.31** |
>
> Requiring real compilation barely affects standards-clean models (claude 95%,
> grok 87%) but collapses gpt-4o (31%; ~69% relative drop) and gemini (61%). Vivid:
> under safety-only, gpt-4o appears to solve 75% of HARD tasks at pass@10; under
> dual-oracle, 0%. → safety-only overstates verified-safe rate by up to ~3x.

---

## (earlier, single-sample, nuXmv-ONLY - superseded by the table above)

**Date:** 2026-06-09. First Phase-C run: each model generates ST from each task's NL
spec + interface; scored by the harness (parse → nuXmv model-check of safety
properties → scenario simulation). 18 tasks (6 easy / 9 medium / 3 hard), 59
properties. One sample per task, temperature default. Raw per-task results +
generated code: `source/baseline_results_2026-06-09/*.json`.

Models (current IDs as of run): `claude-sonnet-4-6`, `gpt-4o`, `gemini-2.5-flash`,
`grok-3`.

## Results

| Model | Verified | Unsafe | Parse-error | Translate-error | Easy | Medium | Hard |
|---|---|---|---|---|---|---|---|
| grok-3 | **0.667** (12/18) | 0.0 | 0.222 | 0.111 | 1.00 | 0.44 | 0.67 |
| claude-sonnet-4-6 | **0.500** (9/18) | 0.0 | 0.333 | 0.167 | 1.00 | 0.22 | 0.33 |
| gpt-4o | **0.278** (5/18) | 0.0 | 0.722 | 0.0 | 0.67 | 0.00 | 0.33 |
| gemini-2.5-flash | **0.111** (2/18) | 0.0 | 0.889 | 0.0 | 0.33 | 0.00 | 0.00 |

Outcome categories (mutually exclusive): **verified** = compiles + all safety
properties hold; **unsafe** = parses & model-checks but ≥1 property FAILS;
**parse_error** = not valid ST in the supported subset; **translate_error** =
parses but can't be lowered to the checker.

## Findings
1. **Strong separation** - verified-safe rate spans 0.11-0.67 across frontier models.
2. **`unsafe_rate = 0` everywhere** - on this task set, whenever a model produced
   valid in-subset ST, it satisfied the formal safety properties. The binding
   constraint is **producing valid Structured Text**, not safety reasoning.
3. **`parse_error` dominates failures** - e.g. GPT-4o frequently emits non-standard
   syntax (`END_VAR_INPUT;` instead of `END_VAR`). Consistent with ST being a
   low-resource language for LLMs.
4. **Difficulty gradient** - medium is hardest for most; hard-tier (N=3) is noisy.

## Honest caveats (address before publication)
- **`parse_error` is not purely "model wrote bad ST."** It conflates genuine syntax
  errors with constructs that are *valid IEC 61131-3 but outside our supported
  subset*. Need: (a) sample-and-classify parse_errors (genuine vs unsupported), and
  (b) corroborate with **MATIEC** (a real compiler) - if MATIEC also rejects, it's a
  genuine error. (The GPT-4o `END_VAR_INPUT` case is a genuine error MATIEC would
  also reject.)
- **Small N** (18 tasks; only 3 hard). Grow the benchmark for statistical power and
  stable per-tier rates.
- **Single sample per task.** Add pass@k sampling for robustness.
- **Prompt sensitivity.** One prompt template; report prompt and consider variants.

## So what (paper narrative + next steps)
- The benchmark cleanly ranks models and exposes a concrete, measurable gap: frontier
  models often cannot produce *verifiably-safe* PLC code, mostly failing on ST
  validity. That is the motivation for the method contribution.
- **Next:** (1) grow benchmark; (2) wire MATIEC to corroborate the syntax-validity
  story; (3) error-analyze parse failures; (4) the verifier-feedback fine-tuning /
  RL on the 5090 - now well-motivated (teach valid-ST + safety from compiler +
  model-checker feedback).

---

# pass@k results (n=5 samples/task, temperature 0.8)

Benchmark now 22 tasks (7 easy / 11 medium / 4 hard). pass@k = unbiased estimator
(Chen et al.) over 5 samples; a "pass" = verified-safe (compiles + all safety
properties hold). Raw: `source/baseline_results_2026-06-09/passk_*.json`.

| Model | pass@1 | pass@3 | pass@5 |
|---|---|---|---|
| grok-3 | 0.736 | 0.873 | **0.909** |
| claude-sonnet-4-6 | 0.536 | 0.545 | 0.545 |
| gpt-4o | 0.173 | 0.332 | 0.409 |
| gemini-2.5-flash | 0.127 | 0.191 | 0.227 |

By tier (pass@1 / pass@5):

| Model | easy | medium | hard |
|---|---|---|---|
| grok-3 | 0.94 / 1.00 | 0.66 / 0.91 | 0.60 / 0.75 |
| claude-sonnet-4-6 | 1.00 / 1.00 | 0.27 / 0.27 | 0.45 / 0.50 |
| gpt-4o | 0.31 / 0.71 | 0.055 / 0.18 | 0.25 / 0.50 |
| gemini-2.5-flash | 0.29 / 0.43 | 0.055 / 0.09 | 0.05 / 0.25 |

## Findings
1. **Ranking** grok-3 ≫ claude > gpt-4o > gemini, consistent with the single-sample run.
2. **Systematic vs. stochastic failures (headline insight).** The pass@1→pass@5 gain
   differs sharply: **claude is ~flat (0.536→0.545)** - the *same* tasks fail all 5
   samples even at temp 0.8, i.e. *deterministic/systematic* failures; **gpt-4o more
   than doubles (0.173→0.409)** and grok rises (0.736→0.909) - *stochastic* failures
   that resampling recovers. Implication: the right remedy is model-dependent - for
   claude, sampling does **not** help (needs better prompting / fine-tuning); for
   gpt-4o, sampling does. This motivates the verifier-feedback fine-tuning contribution.
3. **Medium is the hardest tier** for every model (timed + sequential logic), above
   the (N=4) hard tier.
4. Even the strongest model (grok-3, pass@5 0.909) leaves a real gap on medium/hard.
5. **unsafe_rate remains ~0** - failures are dominated by ST validity, not unsafe logic
   (same as single-sample).

## Caveats (unchanged + new)
- pass@k from n=5 (so k ≤ 5); pass@5 = "≥1 of 5 verified."
- Same `parse_error` caveat: corroborate with MATIEC (in progress) + classify a sample.
- Run note: the batch run exited non-zero due to a mid-run script edit, but all four
  per-model JSONs completed and were validated.

