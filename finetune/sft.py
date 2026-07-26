"""Stage 1: QLoRA SFT on verifier-filtered (prompt -> verified ST) pairs.

RUN ON THE 5090. Example:
    python -m finetune.sft --data finetune/data/sft.jsonl \
        --model Qwen/Qwen2.5-Coder-7B-Instruct --out finetune/out/sft

Deps: transformers, trl, peft, bitsandbytes, accelerate, datasets (see
finetune/requirements.txt). Written for trl>=1.7 / transformers>=5 (uses
SFTConfig.max_length and SFTConfig.model_init_kwargs). Pass --no-4bit to do a
plain bf16 LoRA instead of 4-bit QLoRA (fits a 32 GB card for a 7B model and
sidesteps any bitsandbytes/Blackwell kernel issues).
"""
from __future__ import annotations

import argparse
import json


def load_pairs(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="finetune/data/sft.jsonl")
    ap.add_argument("--model", default="Qwen/Qwen2.5-Coder-7B-Instruct")
    ap.add_argument("--out", default="finetune/out/sft")
    ap.add_argument("--epochs", type=float, default=3.0)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--bsz", type=int, default=1)
    ap.add_argument("--grad_accum", type=int, default=8)
    ap.add_argument("--max_len", type=int, default=1024)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-4bit", dest="four_bit", action="store_false",
                    help="use plain bf16 LoRA instead of 4-bit QLoRA")
    args = ap.parse_args()

    import torch
    torch.backends.cudnn.enabled = False  # bundled cudnn aborts on dlopen here
    from datasets import Dataset
    from transformers import AutoTokenizer, BitsAndBytesConfig
    from peft import LoraConfig
    from trl import SFTConfig, SFTTrainer

    tok = AutoTokenizer.from_pretrained(args.model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    rows = load_pairs(args.data)

    def to_text(r):
        msgs = [{"role": "user", "content": r["prompt"]},
                {"role": "assistant", "content": r["completion"]}]
        return {"text": tok.apply_chat_template(msgs, tokenize=False)}

    ds = Dataset.from_list([to_text(r) for r in rows])

    model_init_kwargs = {"device_map": "auto", "dtype": torch.bfloat16,
                         "attn_implementation": "eager"}
    if args.four_bit:
        model_init_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)

    lora = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias="none",
                      task_type="CAUSAL_LM",
                      target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                                      "gate_proj", "up_proj", "down_proj"])
    cfg = SFTConfig(output_dir=args.out, num_train_epochs=args.epochs,
                    per_device_train_batch_size=args.bsz,
                    gradient_accumulation_steps=args.grad_accum,
                    learning_rate=args.lr, logging_steps=10, save_strategy="epoch",
                    bf16=True, max_length=args.max_len, dataset_text_field="text",
                    packing=False, gradient_checkpointing=True,
                    gradient_checkpointing_kwargs={"use_reentrant": False},
                    seed=args.seed, data_seed=args.seed,
                    model_init_kwargs=model_init_kwargs)
    trainer = SFTTrainer(model=args.model, train_dataset=ds, args=cfg,
                         peft_config=lora)
    trainer.train()
    trainer.save_model(args.out)
    print("saved SFT adapter to", args.out)


if __name__ == "__main__":
    main()
