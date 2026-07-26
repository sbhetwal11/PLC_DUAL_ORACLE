"""Stage 2: verifier-reward RL (GRPO) on top of an SFT (or base) policy.

The reward is the SOUND dual oracle (compile + model-check [+ scenarios]), not an
LLM judge -- this is the method contribution. RUN ON THE 5090.

    python -m finetune.rl --data finetune/data/rl_prompts_lite.jsonl \
        --model Qwen/Qwen2.5-Coder-7B-Instruct --adapter finetune/out/sftlite \
        --reward taskvalid --out finetune/out/rl_func

Requires nuXmv (NUXMV_BIN) + MATIEC (MATIEC_IEC2C) on env so the reward can verify.
Written for trl>=1.7 / transformers>=5. Pass --no-4bit for bf16 LoRA.

Reward selection (--reward):
  invariant  compile + all safety invariants           (the original metric)
  taskvalid  compile + invariants + functional scenarios (DeepReview B1/B4)
  taskvalid_gated  taskvalid, but HARD-CAPPED at 0.1 if any 'critical'-severity
                   safety property fails (safety-critical gating; see reward.py)

Exp3/M13 controls: --beta (KL coeff), --entropy_coef, --temperature. Per-step
GRPO diagnostics (group reward variance, zero-variance fraction, nonzero-advantage
fraction, plus trl's entropy/kl log) are written to --metrics_out.
"""
from __future__ import annotations

import argparse
import json

from finetune.reward import dual_oracle_reward, task_valid_reward, reward_taskvalid_gated


def load_prompts(path, limit=0):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                rows.append({"prompt": r["prompt"], "meta": r["meta"]})
    if limit and len(rows) > limit:
        rows = rows[:limit]
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="finetune/data/sft.jsonl")
    ap.add_argument("--model", default="Qwen/Qwen2.5-Coder-7B-Instruct")
    ap.add_argument("--adapter", default="finetune/out/sft", help="SFT LoRA to warm-start; 'base' = fresh LoRA")
    ap.add_argument("--out", default="finetune/out/rl")
    ap.add_argument("--reward", choices=["invariant", "taskvalid", "taskvalid_gated"],
                    default="invariant")
    ap.add_argument("--num_gen", type=int, default=8, help="GRPO group size")
    ap.add_argument("--grad_accum", type=int, default=4)
    ap.add_argument("--max_steps", type=int, default=30)
    ap.add_argument("--max_completion_length", type=int, default=512)
    ap.add_argument("--lr", type=float, default=1e-5)
    ap.add_argument("--beta", type=float, default=0.0, help="KL coefficient (M13)")
    ap.add_argument("--entropy_coef", type=float, default=0.0, help="entropy bonus (M13)")
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--limit", type=int, default=0, help="cap #prompts (fixed-frontier control)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--metrics_out", default=None)
    ap.add_argument("--no-4bit", dest="four_bit", action="store_false")
    args = ap.parse_args()

    reward_of = {"invariant": dual_oracle_reward,
                 "taskvalid": task_valid_reward,
                 "taskvalid_gated": reward_taskvalid_gated}[args.reward]

    import torch
    torch.backends.cudnn.enabled = False  # bundled cudnn aborts on dlopen here
    from datasets import Dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import LoraConfig, PeftModel, prepare_model_for_kbit_training
    from trl import GRPOConfig, GRPOTrainer

    tok = AutoTokenizer.from_pretrained(args.model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    rows = load_prompts(args.data, limit=args.limit)

    def fmt(p):
        return tok.apply_chat_template([{"role": "user", "content": p}],
                                       tokenize=False, add_generation_prompt=True)
    ds = Dataset.from_list([{"prompt": fmt(r["prompt"]), "meta": r["meta"]}
                            for r in rows])

    # Per-step diagnostics: GRPO passes num_gen contiguous completions per prompt.
    step_diag = []

    def reward_fn(completions, meta, **kwargs):
        rewards = [reward_of(m, c) for c, m in zip(completions, meta)]
        g = args.num_gen
        import statistics as st
        stds, zero_var, nz_adv = [], 0, 0
        for i in range(0, len(rewards), g):
            grp = rewards[i:i + g]
            if len(grp) < 2:
                continue
            s = st.pstdev(grp)
            stds.append(s)
            if s == 0.0:
                zero_var += 1
            else:
                nz_adv += sum(1 for r in grp if r != (sum(grp) / len(grp)))
        ngrp = max(1, len(stds))
        step_diag.append({
            "n": len(rewards), "reward_mean": round(sum(rewards) / len(rewards), 4),
            "group_reward_std_mean": round(sum(stds) / ngrp, 4),
            "zero_variance_group_frac": round(zero_var / ngrp, 4),
            "nonzero_advantage_frac": round(nz_adv / len(rewards), 4),
        })
        return rewards

    model_kwargs = {"device_map": "auto", "dtype": torch.bfloat16,
                    "attn_implementation": "eager"}
    if args.four_bit:
        model_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    base = AutoModelForCausalLM.from_pretrained(args.model, **model_kwargs)
    if args.four_bit:
        base = prepare_model_for_kbit_training(base)
    from_base = args.adapter.lower() in ("", "none", "base")
    peft_cfg = None
    if from_base:
        peft_cfg = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias="none",
                              task_type="CAUSAL_LM",
                              target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                                              "gate_proj", "up_proj", "down_proj"])
        model = base
    else:
        model = PeftModel.from_pretrained(base, args.adapter, is_trainable=True)
    model.config.use_cache = False

    cfg_kwargs = dict(output_dir=args.out, per_device_train_batch_size=args.num_gen,
                      gradient_accumulation_steps=args.grad_accum, learning_rate=args.lr,
                      num_generations=args.num_gen,
                      max_completion_length=args.max_completion_length,
                      max_steps=args.max_steps, logging_steps=1,
                      save_strategy="steps", save_steps=1000, bf16=True,
                      seed=args.seed, beta=args.beta, temperature=args.temperature,
                      gradient_checkpointing=True,
                      gradient_checkpointing_kwargs={"use_reentrant": False})
    # entropy_coef is a newer GRPOConfig knob. Pass it when supported; if the caller
    # explicitly asked for a nonzero coefficient but this TRL lacks it, FAIL LOUDLY
    # rather than silently running an unregularized job (M13 confound guard).
    import inspect
    has_ent = "entropy_coef" in inspect.signature(GRPOConfig.__init__).parameters
    if has_ent:
        cfg_kwargs["entropy_coef"] = args.entropy_coef
    elif args.entropy_coef:
        raise SystemExit(f"--entropy_coef={args.entropy_coef} requested but this TRL "
                         f"({__import__('trl').__version__}) GRPOConfig has no entropy_coef")
    print(f"[rl] reward={args.reward} beta={args.beta} entropy_coef="
          f"{args.entropy_coef if has_ent else 'UNSUPPORTED'} temp={args.temperature}")
    cfg = GRPOConfig(**cfg_kwargs)
    trainer = GRPOTrainer(model=model, reward_funcs=reward_fn, args=cfg,
                          train_dataset=ds, processing_class=tok, peft_config=peft_cfg)
    trainer.train()
    trainer.save_model(args.out)
    print("saved RL adapter to", args.out)

    if args.metrics_out:
        import os
        os.makedirs(os.path.dirname(args.metrics_out) or ".", exist_ok=True)
        with open(args.metrics_out, "w", encoding="utf-8") as f:
            json.dump({
                "config": {"reward": args.reward, "beta": args.beta,
                           "entropy_coef": args.entropy_coef, "temperature": args.temperature,
                           "lr": args.lr, "adapter": args.adapter, "num_gen": args.num_gen,
                           "max_steps": args.max_steps, "n_prompts": len(rows),
                           "seed": args.seed},
                "step_diag": step_diag,
                "log_history": trainer.state.log_history,
            }, f, indent=1)
        print("wrote metrics to", args.metrics_out)


if __name__ == "__main__":
    main()
