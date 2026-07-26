"""Phase 3: verifier-feedback fine-tuning.

datagen: procedural task families (DISJOINT from the 22-task eval benchmark) whose
reference solutions are kept only if they pass the dual oracle (MATIEC compile +
nuXmv safety). Produces (prompt -> verified ST) SFT pairs. See docs/08_FINETUNE_PLAN.md.
"""
