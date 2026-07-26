"""Generators: produce candidate ST for a task.

- ReferenceGenerator: returns the task's reference (pipeline sanity; ~100% verified).
- Anthropic (Claude), OpenAI-compatible (OpenAI GPT / xAI Grok / DeepSeek), and
  Google Gemini generators. API keys come from environment variables.

Uses only the stdlib (urllib) - no SDK dependency. Model spec strings:
    reference
    anthropic:<model>           e.g. anthropic:claude-3-5-sonnet-latest
    openai:<model>              e.g. openai:gpt-4o
    grok:<model>                e.g. grok:grok-2-latest        (xAI)
    deepseek:<model>            e.g. deepseek:deepseek-chat
    gemini:<model>              e.g. gemini:gemini-1.5-pro     (Google)
"""
from __future__ import annotations

import json
import os
import urllib.request

from .extract import extract_st
from .prompt import build_prompt

_MAXTOK = 1500


def _post(url: str, headers: dict, payload: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"content-type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())


class ReferenceGenerator:
    name = "reference"

    def available(self) -> bool:
        return True

    def generate(self, lt, temperature=None) -> str:
        return lt.reference_st


class AnthropicGenerator:
    def __init__(self, model: str):
        self.model = model
        self.name = f"anthropic:{model}"
        self.key = os.environ.get("ANTHROPIC_API_KEY")

    def available(self) -> bool:
        return bool(self.key)

    def generate(self, lt, temperature=None) -> str:
        payload = {"model": self.model, "max_tokens": _MAXTOK,
                   "messages": [{"role": "user", "content": build_prompt(lt.task)}]}
        if temperature is not None:
            payload["temperature"] = temperature
        data = _post("https://api.anthropic.com/v1/messages",
                     {"x-api-key": self.key, "anthropic-version": "2023-06-01"}, payload)
        text = "".join(b.get("text", "") for b in data.get("content", []))
        return extract_st(text)


class OpenAICompatGenerator:
    """OpenAI chat-completions API shape: OpenAI, xAI Grok, DeepSeek."""
    def __init__(self, provider: str, model: str, base_url: str, key_env: str):
        self.model = model
        self.name = f"{provider}:{model}"
        self.base_url = base_url
        self.key = os.environ.get(key_env)

    def available(self) -> bool:
        return bool(self.key)

    def generate(self, lt, temperature=None) -> str:
        payload = {"model": self.model, "max_tokens": _MAXTOK,
                   "messages": [{"role": "user", "content": build_prompt(lt.task)}]}
        if temperature is not None:
            payload["temperature"] = temperature
        data = _post(f"{self.base_url}/chat/completions",
                     {"authorization": f"Bearer {self.key}"}, payload)
        text = data["choices"][0]["message"]["content"]
        return extract_st(text)


class GeminiGenerator:
    def __init__(self, model: str):
        self.model = model
        self.name = f"gemini:{model}"
        self.key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

    def available(self) -> bool:
        return bool(self.key)

    def generate(self, lt, temperature=None) -> str:
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self.model}:generateContent?key={self.key}")
        gen_cfg = {"maxOutputTokens": _MAXTOK}
        if temperature is not None:
            gen_cfg["temperature"] = temperature
        data = _post(url, {}, {
            "contents": [{"parts": [{"text": build_prompt(lt.task)}]}],
            "generationConfig": gen_cfg,
        })
        text = "".join(
            p.get("text", "")
            for p in data["candidates"][0]["content"]["parts"])
        return extract_st(text)


class LocalHFGenerator:
    """Local HuggingFace model (optionally with a PEFT/LoRA adapter), for evaluating
    fine-tuned models on the benchmark with the same harness. spec forms:
        hf:<model_path>            base/instruct model
        hf:<model_path>+<adapter>  model + LoRA adapter (e.g. finetune/out/sft)
    Runs on the GPU box (transformers + torch + peft). Untested on the dev laptop.
    """
    def __init__(self, spec: str):
        parts = spec.split("+", 1)
        self.model_path = parts[0]
        self.adapter = parts[1] if len(parts) > 1 else None
        self.name = f"hf:{spec}"
        self._tok = self._model = None

    def available(self) -> bool:
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
            return True
        except Exception:
            return False

    def _ensure(self):
        if self._model is not None:
            return
        import torch
        # This box's bundled cudnn fails to resolve symbols (aborts on dlopen);
        # LLM inference is matmul-only and needs no cudnn. Disable it + use eager
        # attention so we never touch the cudnn SDPA backend.
        torch.backends.cudnn.enabled = False
        import os
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self._tok = AutoTokenizer.from_pretrained(self.model_path)
        if self._tok.pad_token is None:
            self._tok.pad_token = self._tok.eos_token
        mk = {"device_map": "auto", "dtype": torch.bfloat16,
              "attn_implementation": "eager"}
        if os.environ.get("PLCBENCH_LOAD_4BIT"):   # fit big models (e.g. 14B) on 32 GB
            from transformers import BitsAndBytesConfig
            mk["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
        self._model = AutoModelForCausalLM.from_pretrained(self.model_path, **mk)
        if self.adapter:
            from peft import PeftModel
            self._model = PeftModel.from_pretrained(self._model, self.adapter)
        self._model.eval()

    def generate_text(self, prompt: str, temperature=None) -> str:
        """Generate from an arbitrary user prompt (used by the repair eval)."""
        import torch
        self._ensure()
        msgs = [{"role": "user", "content": prompt}]
        text = self._tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        inputs = self._tok(text, return_tensors="pt").to(self._model.device)
        gkw = {"max_new_tokens": 1024, "pad_token_id": self._tok.eos_token_id,
               "do_sample": bool(temperature)}
        if temperature:
            gkw["temperature"] = temperature
        with torch.no_grad():
            out = self._model.generate(**inputs, **gkw)
        gen = self._tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        return extract_st(gen)

    def generate(self, lt, temperature=None) -> str:
        return self.generate_text(build_prompt(lt.task), temperature)

    def generate_many_text(self, prompt: str, n: int, temperature=0.8,
                           max_batch: int = 10) -> list:
        """Sample n completions for one prompt in batched forward passes
        (num_return_sequences), far faster than n sequential calls. Returns a list
        of n extracted-ST strings. Failed/oversized batches fall back to singles."""
        import torch
        self._ensure()
        msgs = [{"role": "user", "content": prompt}]
        text = self._tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        inputs = self._tok(text, return_tensors="pt").to(self._model.device)
        outs = []
        remaining = n
        while remaining > 0:
            b = min(remaining, max_batch)
            gkw = {"max_new_tokens": 1024, "pad_token_id": self._tok.eos_token_id,
                   "do_sample": True, "temperature": temperature or 0.8,
                   "num_return_sequences": b}
            with torch.no_grad():
                out = self._model.generate(**inputs, **gkw)
            plen = inputs["input_ids"].shape[1]
            for row in out:
                gen = self._tok.decode(row[plen:], skip_special_tokens=True)
                outs.append(extract_st(gen))
            remaining -= b
        return outs

    def generate_many(self, lt, n: int, temperature=0.8) -> list:
        return self.generate_many_text(build_prompt(lt.task), n, temperature)


def make_generator(spec: str):
    if spec == "reference":
        return ReferenceGenerator()
    if spec.startswith("hf:"):
        return LocalHFGenerator(spec[3:])
    if ":" not in spec:
        raise ValueError(f"model spec must be 'provider:model' or 'reference', got {spec!r}")
    provider, model = spec.split(":", 1)
    if provider == "anthropic":
        return AnthropicGenerator(model)
    if provider == "openai":
        return OpenAICompatGenerator("openai", model, "https://api.openai.com/v1", "OPENAI_API_KEY")
    if provider == "grok":
        return OpenAICompatGenerator("grok", model, "https://api.x.ai/v1", "XAI_API_KEY")
    if provider == "deepseek":
        return OpenAICompatGenerator("deepseek", model, "https://api.deepseek.com", "DEEPSEEK_API_KEY")
    if provider == "gemini":
        return GeminiGenerator(model)
    raise ValueError(f"unknown provider {provider!r} "
                     "(anthropic | openai | grok | deepseek | gemini)")
