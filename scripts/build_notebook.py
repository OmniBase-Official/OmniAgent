"""Generate notebooks/train_omniagent_lora.ipynb.

Writing the notebook as a script keeps the JSON valid by construction and lets
the cell sources be linted like any other file.
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path("notebooks/train_omniagent_lora.ipynb")


def md(text: str) -> dict[str, object]:
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip().splitlines(True)}


def code(text: str) -> dict[str, object]:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": text.strip().splitlines(True),
    }


CELLS = [
    md(
        """
# OmniAgent — LoRA fine-tune → GGUF → Ollama

Train a model on OmniAgent's own run logs, then run OmniAgent on it. Built to
run **locally, in VS Code**, on the same machine as Ollama.

**Why local rather than Colab.** The whole project runs on one rule: nothing
leaves localhost. The dataset breaks that rule the moment it is uploaded — it
contains your questions, your system prompt, and the contents of any file the
agent read with `read_file` or `search_text`. Training here keeps the rule
intact end to end, and there is no multi-hundred-megabyte GGUF to download
afterwards: `ollama create` is a cell in this notebook.

**Before you start**

1. Collect runs — `python scripts/collect_dataset.py --model qwen2.5-coder:7b`
2. Export them — `python export_dataset.py "data/*.jsonl" -o data/dataset.jsonl --stats`
3. Select this project's `.venv` as the notebook kernel.
4. Install the training extras — `pip install -e ".[training]"`

**VRAM.** The notebook picks its own strategy: with CUDA it loads the base
model in 4-bit (QLoRA), which fits a 4 GB card; without CUDA it falls back to
fp32 on the CPU, which is only sensible for a tiny model. Set `FOUR_BIT = False`
if you have the VRAM to spare and want bf16 LoRA instead.

**Licensing.** The default base model is `Qwen/Qwen2.5-1.5B-Instruct`, which is
Apache-2.0. The 3B of the same family is released under a different, more
restrictive licence. If this is heading anywhere commercial, read the model card
of whatever you put in `BASE_MODEL` before you train, not after.
"""
    ),
    md("## 1. Settings"),
    code(
        '''
import os
from pathlib import Path

# Apache-2.0, and small enough for a 4 GB card in 4-bit. Check the licence if
# you change it.
BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"

PROJECT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
OUTPUT_DIR = PROJECT / "models"

# The defaults are what built the model registered as `omniagent`, kept so this
# notebook stays the record of how that was made. Every path below derives from
# OUTPUT_NAME, and the demo is pinned to the OLLAMA_NAME tag, so a run that must
# not overwrite either sets these in the environment instead of editing the
# cell:
#
#   OMNIAGENT_DATASET=data/dataset-merged-2026-10-10.jsonl
#   OMNIAGENT_OUTPUT_NAME=omniagent-qwen2.5-1.5b-v3
#   OMNIAGENT_OLLAMA_NAME=omniagent-v3
DATASET = Path(os.environ.get("OMNIAGENT_DATASET", "")) or PROJECT / "data" / "dataset.jsonl"
if not DATASET.is_absolute():
    DATASET = PROJECT / DATASET
OUTPUT_NAME = os.environ.get("OMNIAGENT_OUTPUT_NAME", "omniagent-qwen2.5-1.5b")
OLLAMA_NAME = os.environ.get("OMNIAGENT_OLLAMA_NAME", "omniagent")

# Ollama defaults to a 4096-token context regardless of what the model
# supports. OmniAgent's system prompt is ~900 tokens before any tool output,
# so a single read_file blows straight past it with an HTTP 400. Raise it.
NUM_CTX = 16384

# f16 is the safe conversion. q8_0 halves the file and fits a small card
# entirely in VRAM, at some cost in quality.
OUTTYPE = "f16"

FOUR_BIT = True              # QLoRA; set False for bf16 LoRA if VRAM allows
EPOCHS = 3
LEARNING_RATE = 2e-4
MAX_LENGTH = 2048            # the system prompt alone is ~2900 characters
BATCH_SIZE = 1
GRAD_ACCUM = 8

LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05

MIN_EXAMPLES = 10            # below this, training is not worth the time
SEED = 0

print("project:", PROJECT)
print("dataset:", DATASET)
'''
    ),
    md(
        """## 2. Check the machine

What is available here decides how the model is loaded, so look before
assuming."""
    ),
    code(
        '''
import torch

CUDA = torch.cuda.is_available()
print("torch   :", torch.__version__)
print("cuda    :", CUDA)

if CUDA:
    free, total = torch.cuda.mem_get_info()
    print("device  :", torch.cuda.get_device_name(0))
    print(f"vram    : {free / 1024**3:.2f} GB free of {total / 1024**3:.2f} GB")
    print("bf16    :", torch.cuda.is_bf16_supported())
else:
    print("no CUDA: training will run on the CPU, which is only sensible for a tiny model")

FOUR_BIT = FOUR_BIT and CUDA   # bitsandbytes needs a GPU
print("strategy:", "QLoRA 4-bit" if FOUR_BIT else ("bf16 LoRA" if CUDA else "fp32 CPU LoRA"))
'''
    ),
    md(
        """## 3. Validate the dataset first

Nothing is loaded until the data passes. The validator refuses a malformed
conversation and — more importantly — refuses a dataset containing anything
that looks like a credential, because a model trained on a leaked key will
reproduce it."""
    ),
    code(
        '''
import sys

sys.path.insert(0, str(PROJECT))
from validate_dataset import validate_file

report = validate_file(DATASET, min_examples=MIN_EXAMPLES)
print(report.render())
if not report.ok:
    raise SystemExit("dataset refused; fix it before training")
'''
    ),
    md("## 4. Load the base model"),
    code(
        '''
from transformers import AutoModelForCausalLM, AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

load_kwargs = {}
if FOUR_BIT:
    from transformers import BitsAndBytesConfig

    load_kwargs["quantization_config"] = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    load_kwargs["device_map"] = {"": 0}
elif CUDA:
    load_kwargs["dtype"] = torch.bfloat16
    load_kwargs["device_map"] = {"": 0}
else:
    load_kwargs["dtype"] = torch.float32

model = AutoModelForCausalLM.from_pretrained(BASE_MODEL, **load_kwargs)
model.config.use_cache = False       # incompatible with gradient checkpointing

print(f"{BASE_MODEL}: {sum(p.numel() for p in model.parameters()):,} parameters")
print("device:", next(model.parameters()).device)
if CUDA:
    print(f"vram in use: {torch.cuda.memory_allocated() / 1024**3:.2f} GB")
'''
    ),
    md(
        """## 5. Train the LoRA adapter

`SFTTrainer` reads the `messages` column directly, so the chat template is
applied for us. Note the modern argument names: `max_length` (not
`max_seq_length`) and `processing_class` (not `tokenizer`)."""
    ),
    code(
        '''
from datasets import load_dataset
from peft import LoraConfig, prepare_model_for_kbit_training
from trl import SFTConfig, SFTTrainer

data = load_dataset("json", data_files=str(DATASET), split="train")
print(f"{len(data)} examples")

if FOUR_BIT:
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)

trainer = SFTTrainer(
    model=model,
    args=SFTConfig(
        output_dir=str(OUTPUT_DIR / "runs" / OUTPUT_NAME),
        num_train_epochs=EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM,
        gradient_checkpointing=CUDA,
        learning_rate=LEARNING_RATE,
        max_length=MAX_LENGTH,
        logging_steps=5,
        save_strategy="no",
        report_to=[],
        bf16=CUDA,
        use_cpu=not CUDA,
        optim="paged_adamw_8bit" if FOUR_BIT else "adamw_torch",
        seed=SEED,
    ),
    train_dataset=data,
    processing_class=tokenizer,
    peft_config=LoraConfig(
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules="all-linear",
    ),
)

result = trainer.train()
print("final loss:", round(result.training_loss, 4))
if CUDA:
    print(f"peak vram: {torch.cuda.max_memory_allocated() / 1024**3:.2f} GB")
'''
    ),
    md(
        """## 6. Merge the adapter into the base model

A 4-bit model cannot be merged into directly, so the base weights are reloaded
in fp16 on the CPU and the adapter is merged there. It needs RAM, not VRAM."""
    ),
    code(
        '''
import gc

from peft import PeftModel

adapter_dir = OUTPUT_DIR / f"{OUTPUT_NAME}-adapter"
merged_dir = OUTPUT_DIR / f"{OUTPUT_NAME}-merged"
trainer.model.save_pretrained(adapter_dir)
print("adapter saved to", adapter_dir)

# Free the GPU before pulling a full-precision copy into RAM.
del trainer, model
gc.collect()
if CUDA:
    torch.cuda.empty_cache()

base = AutoModelForCausalLM.from_pretrained(BASE_MODEL, dtype=torch.float16, device_map="cpu")
merged = PeftModel.from_pretrained(base, adapter_dir).merge_and_unload()
merged.save_pretrained(merged_dir)
tokenizer.save_pretrained(merged_dir)

for path in sorted(merged_dir.iterdir()):
    print(f"  {path.name:28} {path.stat().st_size:>14,} bytes")
'''
    ),
    md(
        """## 7. Does it still speak ReAct?

One generation, checked for the format the agent depends on. This is a sanity
check, not an evaluation — a model that passes here can still be wrong about
everything."""
    ),
    code(
        '''
SYSTEM = (
    "You are OmniAgent, a careful reasoning assistant that solves tasks by "
    "thinking step by step and calling tools.\\n\\nAVAILABLE TOOLS\\n"
    "- calculate(expression: str)\\n- get_current_time()\\n\\n"
    "Reply with Thought/Action/Action Input, or Thought/Final Answer."
)

merged.eval()
prompt = tokenizer.apply_chat_template(
    [{"role": "system", "content": SYSTEM},
     {"role": "user", "content": "What is 23% of 1800?"}],
    tokenize=False,
    add_generation_prompt=True,
)
inputs = tokenizer(prompt, return_tensors="pt")
with torch.no_grad():
    out = merged.generate(
        **inputs, max_new_tokens=96, do_sample=False,
        pad_token_id=tokenizer.pad_token_id,
    )
reply = tokenizer.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
print(reply)

followed = reply.strip().startswith("Thought:") and (
    "Action:" in reply or "Final Answer:" in reply
)
print("\\nfollows the ReAct format:", followed)
'''
    ),
    md(
        """## 8. Convert to GGUF

`convert_hf_to_gguf.py` is no longer a standalone file — it imports a
`conversion` package from the repository, so the repo has to be cloned rather
than the single script downloaded. The clone is kept beside the models so a
second run reuses it."""
    ),
    code(
        '''
import subprocess

LLAMA_CPP_REF = "master"   # pin to a tag for a reproducible build
llama_cpp = OUTPUT_DIR / "llama.cpp"

if not llama_cpp.exists():
    subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", LLAMA_CPP_REF,
         "https://github.com/ggml-org/llama.cpp.git", str(llama_cpp)],
        check=True,
    )

gguf_path = OUTPUT_DIR / f"{OUTPUT_NAME}-{OUTTYPE}.gguf"
subprocess.run(
    [sys.executable, str(llama_cpp / "convert_hf_to_gguf.py"), str(merged_dir),
     "--outfile", str(gguf_path), "--outtype", OUTTYPE],
    check=True,
)
print(f"{gguf_path.name}: {gguf_path.stat().st_size:,} bytes")
'''
    ),
    md(
        """## 9. Checksum and manifest

So that the model Ollama loads is provably the model you built."""
    ),
    code(
        '''
import hashlib
import json
import platform
from datetime import datetime, timezone


def sha256_of(path, chunk=1 << 20):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while block := handle.read(chunk):
            digest.update(block)
    return digest.hexdigest()


manifest = {
    "name": OUTPUT_NAME,
    "base_model": BASE_MODEL,
    "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "python": platform.python_version(),
    "torch": torch.__version__,
    "device": torch.cuda.get_device_name(0) if CUDA else "cpu",
    "strategy": "qlora-4bit" if FOUR_BIT else ("lora-bf16" if CUDA else "lora-fp32-cpu"),
    "examples": report.examples,
    "epochs": EPOCHS,
    "learning_rate": LEARNING_RATE,
    "lora": {"r": LORA_R, "alpha": LORA_ALPHA, "dropout": LORA_DROPOUT},
    "final_loss": round(result.training_loss, 4),
    "gguf": gguf_path.name,
    "outtype": OUTTYPE,
    "num_ctx": NUM_CTX,
    "gguf_sha256": sha256_of(gguf_path),
}
# Each run keeps its own directory, because one manifest file for every run
# meant each training erased the record of the one before it. run_dir refuses
# a manifest missing base_model, examples or strategy.
import shutil
import sys

sys.path.insert(0, str(PROJECT / "scripts"))
from run_dir import new_run_dir, write_manifest

run = new_run_dir(OUTPUT_DIR / "runs", datetime.now(timezone.utc))
manifest_path = write_manifest(run, manifest)
if adapter_dir.is_dir():
    shutil.copytree(adapter_dir, run / "adapter", dirs_exist_ok=True)

# The flat path stays, as a copy of the newest, so anything reading it keeps
# working. The copy carries the run name, so it can say where it came from.
flat = OUTPUT_DIR / f"{OUTPUT_NAME}-manifest.json"
flat.write_text(manifest_path.read_text(encoding="utf-8"), encoding="utf-8")

print(manifest_path.read_text(encoding="utf-8"))
print(f"run directory: {run}")
'''
    ),
    md(
        """## 10. Register it with Ollama

No upload, no download: Ollama is on this machine, so the model it loads is the
file the cell above just hashed."""
    ),
    code(
        r'''
modelfile = f"""FROM ./{gguf_path.name}

TEMPLATE \"\"\"{{{{ if .System }}}}<|im_start|>system
{{{{ .System }}}}<|im_end|>
{{{{ end }}}}{{{{ if .Prompt }}}}<|im_start|>user
{{{{ .Prompt }}}}<|im_end|>
{{{{ end }}}}<|im_start|>assistant
{{{{ .Response }}}}<|im_end|>
\"\"\"

PARAMETER temperature 0.1
PARAMETER num_ctx {NUM_CTX}
PARAMETER stop "<|im_end|>"
PARAMETER stop "Observation:"
"""
modelfile_path = OUTPUT_DIR / f"Modelfile-{OUTPUT_NAME}"
modelfile_path.write_text(modelfile, encoding="utf-8")
print(modelfile)

subprocess.run(
    ["ollama", "create", OLLAMA_NAME, "-f", modelfile_path.name],
    cwd=OUTPUT_DIR,
    check=True,
)
print(f"\nregistered as {OLLAMA_NAME}")
'''
    ),
    md(
        """## 11. Run the agent on it

The real test. Not "did the pipeline finish", but "does OmniAgent work on the
model we just trained"."""
    ),
    code(
        '''
subprocess.run(
    [sys.executable, "main.py", "--model", OLLAMA_NAME, "--ask",
     "What is 23% of 1800 plus the square root of 324?"],
    cwd=PROJECT,
    check=False,
)
'''
    ),
    md(
        """From a terminal, the same thing:

```bash
python main.py --model omniagent --ask "What is 23% of 1800?"
```

If the new model is worse than the stock one, say so out loud and keep the
stock one. A fine-tune that nobody checked is not an improvement."""
    ),
]

NOTEBOOK = {
    "cells": CELLS,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.12"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(NOTEBOOK, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"wrote {OUT} with {len(CELLS)} cells")
