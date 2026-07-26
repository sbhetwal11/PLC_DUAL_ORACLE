#!/usr/bin/env bash
# Collect all Phase-3 outputs into ~/Downloads/plcbench_phase3_outputs/ for pulling
# to Drive: result JSONs + summaries, the SFT/RL adapters, the generated datasets,
# the key docs, and the training logs. Also writes a tarball next to it.
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DST="$HOME/Downloads/plcbench_phase3_outputs"
mkdir -p "$DST"/{results,adapters,data,docs,logs}

# metrics (small, the most important artifacts)
cp -r "$REPO/results/seeds" "$DST/results/" 2>/dev/null
cp -r "$REPO/results/v2"    "$DST/results/" 2>/dev/null
cp "$REPO"/results/passk_hf_*.json "$DST/results/" 2>/dev/null

# datasets (verified SFT pairs + RL frontier prompts)
cp "$REPO"/finetune/data/*.jsonl "$DST/data/" 2>/dev/null

# trained adapters (final only; checkpoints already pruned)
for d in "$REPO"/finetune/out/seeds/* "$REPO"/finetune/out/v2/*; do
  [ -d "$d" ] || continue
  name="$(basename "$(dirname "$d")")_$(basename "$d")"
  mkdir -p "$DST/adapters/$name"
  cp "$d"/adapter_*.* "$d"/*.json "$DST/adapters/$name/" 2>/dev/null
done

# docs + logs
cp "$REPO"/docs/10_FINETUNE_RESULTS.md "$REPO"/docs/08_FINETUNE_PLAN.md "$DST/docs/" 2>/dev/null
cp "$REPO"/finetune/README.md "$DST/docs/finetune_README.md" 2>/dev/null
cp -r "$REPO"/results/seeds/logs "$DST/logs/seeds_logs" 2>/dev/null
cp -r "$REPO"/results/v2/logs    "$DST/logs/v2_logs" 2>/dev/null

du -sh "$DST" 2>/dev/null
echo "staged -> $DST"
( cd "$HOME/Downloads" && tar czf plcbench_phase3_outputs.tgz plcbench_phase3_outputs 2>/dev/null \
  && echo "tarball -> $HOME/Downloads/plcbench_phase3_outputs.tgz ($(du -h plcbench_phase3_outputs.tgz|cut -f1))" )
