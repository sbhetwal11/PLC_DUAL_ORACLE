# References - verified / candidate sources

BibTeX keys provisional. Verify final metadata before camera-ready.

## Anchor prior work (verified)
```bibtex
@article{agents4plc2024,
  title  = {Agents4PLC: Automating Closed-loop PLC Code Generation and Verification in Industrial Control Systems using LLM-based Agents},
  year   = {2024},
  note   = {arXiv:2410.14209. First LLM multi-agent PLC codegen with code-level formal verification; public ~23-task benchmark; RAG + LoRA. VERIFY exact title/author list before citing.}
}
```

## Adjacent / runner-up area (verified entities)
```bibtex
@misc{gifteval2024,
  title  = {GIFT-Eval: A Benchmark for General Time Series Forecasting Model Evaluation},
  year   = {2024},
  note   = {arXiv:2410.10393. 23 datasets, 7 domains, 177M points. HuggingFace: Salesforce/GIFT-Eval}
}
```
- **iTrust/SUTD ICS datasets** (SWaT, WADI, HAI, etc.) - free, form request (~3 days). itrust.sutd.edu.sg/itrust-labs_datasets/
- **Edge-IIoTset** - public IIoT cybersecurity dataset (centralized + federated). IEEE doc 9751703.

## Core competitive landscape (VERIFIED 2026-06-09 - must-cite / position against)
```bibtex
@misc{agents4plc2024,
  title={Agents4PLC: Automating Closed-loop PLC Code Generation and Verification in Industrial Control Systems using LLM-based Agents},
  year={2024}, note={arXiv:2410.14209. 23 ST tasks (16 easy/7 medium); MATIEC/RuSTy + nuXmv/PLCverif/CBMC; GPT-4o 50% easy / 28.6% medium pass. Code: github.com/Luoji-zju/Agents4PLC_release. ANCHOR - verification at inference, not training.}
}
@misc{autoplc2024,
  title={AutoPLC: Generating Vendor-Aware Structured Text for Programmable Logic Controllers},
  author={Yang, Donghao and Wu, Aolang and Zhang, Tianyi and Zhang, Li and Liu, Fang and Lian, Xiaoli and others},
  year={2024}, note={arXiv:2412.02410. 914-task vendor-aware (Siemens TIA + CODESYS) benchmark; 90%+ compilation; NO formal verification.}
}
@inproceedings{haag2025onlinefeedback,
  title={Training LLMs for Generating IEC 61131-3 Structured Text with Online Feedback},
  author={Haag, Aaron and Fuchs, Bertram and Kacan, Altay and Lohse, Oliver},
  year={2025}, note={arXiv:2410.22159. LLM4Code @ ICSE 2025. Online feedback fine-tuning = compiler + LLM-judge (NOT a formal model-checker reward).}
}
@misc{spec2control2025,
  title={Spec2Control: Automating PLC/DCS Control-Logic Engineering from Natural Language Requirements with LLMs - A Multi-Plant Evaluation},
  author={Koziolek, Heiko and Braun, Thilo and Ashiwal, Virendra and Linsbauer, Sofia and Hansen, Marthe Ahlgreen and Grotterud, Karoline},
  year={2025}, note={arXiv:2510.04519. ABB. NL -> GRAPHICAL control logic; 10 narratives/65 cases. Graphical, not ST.}
}
@misc{kersting2025vendoraware,
  title={Vendor-Aware Industrial Agents: RAG-Enhanced LLMs for Secure On-Premise PLC Code Generation},
  author={Kersting, Joschka and Rummel, Michael and Benndorf, Gesa},
  year={2025}, note={arXiv:2511.09122. ICIT2026. RAG, no fine-tuning, on-premise.}
}
```
Also: **LLM-PLC-AS** (ScienceDirect S2666827025001872; 21 prompting techniques × 25 use cases); **LLM4PLC** (ICSE SEIP 2024, DOI 10.1145/3639477.3639743, superseded); **LLM4SFC** (arXiv:2512.06787); **LD→SFC** (arXiv:2509.12593); IEC 61131-3 graphic langs (arXiv:2410.15200); LLM+formal verification (arXiv:2507.04857); survey (arXiv:2410.03981).

## Verified IRRELEVANT (do NOT cite for this project)
- arXiv:2509.12229 - LoRA/QLoRA profiling on RTX 4060 (not PLC).
- arXiv:2512.07624 - Time Series Foundation Models for Process Model Forecasting (process mining, not PLC).

## Tools (cite as software/URLs)
- OpenPLC - github.com/thiagoralves/OpenPLC_v3
- MATIEC - IEC 61131-3 → C compiler
- RuSTy (`rusty`) - github.com/PLC-lang/rusty
- nuXmv - nuxmv.fbk.eu ; NuSMV - nusmv.fbk.eu

## Do NOT cite
- **ExCyTIn-Bench** as "first" benchmark for LLM agents on cyber-threat investigation - claim refuted (0-3).
- **NASA C-MAPSS** via the NASA data portal - download is dead (mirrors only); irrelevant here anyway.
