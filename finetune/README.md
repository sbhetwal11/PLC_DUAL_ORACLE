# Phase 3 - verifier-feedback fine-tuning

Plan: `../docs/08_FINETUNE_PLAN.md`. Goal: a small open model that produces
**verifiably-safe** ST (compiles + all safety properties hold), trained with the
dual oracle as the signal.

## Files
- `datagen.py` - procedural task families (disjoint from the 22 eval tasks).
- `build_sft.py` - generate → dual-oracle verify → keep verified → `data/sft.jsonl`.
- `reward.py` - graded dual-oracle reward (compile + formal safety) for RL.
- `sft.py` - Stage 1: QLoRA SFT on the verified pairs.
- `rl.py` - Stage 2: GRPO with the verifier reward.
- Eval the tuned model with the existing harness via `hf:` generator (added to
  `plcbench.generate.clients`).

## Status
- **Data pipeline: works.** `bash ../toolchain/wsl_build_sft.sh` → currently
  **158/158 generated tasks verified** → `data/sft.jsonl` (git-ignored).
- **sft.py / rl.py / hf-eval: written but UNTESTED on the dev laptop (no GPU).**
  Validate and run on the 5090; expect minor TRL-version API tweaks.

## Workflow on the 5090
```bash
pip install -r finetune/requirements.txt        # + torch cu128
# 1. data (in WSL/Docker with nuXmv+MATIEC):
bash toolchain/wsl_build_sft.sh                  # -> finetune/data/sft.jsonl
# 2. baseline eval of the BASE model on the benchmark (with nuXmv+MATIEC env):
python -m plcbench.cli eval-passk --model hf:Qwen/Qwen2.5-Coder-7B-Instruct \
    --n 10 --k 1,3,5,10 --out results/passk_hf_base.json
# 3. SFT:
python -m finetune.sft --data finetune/data/sft.jsonl \
    --model Qwen/Qwen2.5-Coder-7B-Instruct --out finetune/out/sft
# 4. eval SFT model:
python -m plcbench.cli eval-passk \
    --model "hf:Qwen/Qwen2.5-Coder-7B-Instruct+finetune/out/sft" \
    --n 10 --k 1,3,5,10 --out results/passk_hf_sft.json
# 5. RL (verifier reward; needs nuXmv+MATIEC env for reward):
python -m finetune.rl --data finetune/data/sft.jsonl \
    --model Qwen/Qwen2.5-Coder-7B-Instruct --adapter finetune/out/sft --out finetune/out/rl
# 6. eval RL model (as step 4 with the rl adapter) -> compare base vs SFT vs RL in the paper.
```

## To strengthen before the real run
- Scale data further: more families + wider grids; add rejection-sampling (step 2)
  and counterexample-repair pairs (step 3) from `docs/08`.
- Audit for leakage vs the 22 eval tasks (different processes/params/names - current
  families are generalizations, not the eval instances themselves).
- Watch reward hacking (model gaming the ST subset); spot-check with MATIEC + by eye.
