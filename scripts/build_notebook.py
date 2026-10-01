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

Train a model on OmniAgent's own run logs, then run OmniAgent on it.

**Before you start**

1. Collect runs: `python main.py --log-file data/run.jsonl --ask "..."`
2. Export them: `python export_dataset.py "data/*.jsonl" -o data/dataset.jsonl --stats`
3. Upload `data/dataset.jsonl` to this Colab session (or mount Drive).
4. Runtime → Change runtime type → **T4 GPU**.

**What this notebook is not.** Every step below has been executed on a CPU with
a 135M model (`scripts/smoke_train.py`), which proves the pipeline runs. It does
not prove the result is any good — that is what step 7 and your own judgement
are for.

**Licensing.** The default base model is `Qwen/Qwen2.5-1.5B-Instruct`, which is
Apache-2.0. The 3B of the same family is released under a different, more
restrictive licence. If this is heading anywhere commercial, read the model card
of whatever you put in `BASE_MODEL` before you train, not after.
"""
    ),
    md("## 1. Settings"),
    code(
        '''
# Apache-2.0, and small enough for a free T4. Check the licence if you change it.
BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"

DATASET = "data/dataset.jsonl"   # exported by export_dataset.py
OUTPUT_NAME = "omniagent-qwen2.5-1.5b"

EPOCHS = 3
LEARNING_RATE = 2e-4
MAX_LENGTH = 2048            # the system prompt alone is ~2900 characters
BATCH_SIZE = 1
GRAD_ACCUM = 8

LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05

MIN_EXAMPLES = 10            # below this, training is not worth the GPU time
SEED = 0
'''
    ),
    md(
        """## 2. Install

Pinned, because these libraries move fast and a silent API change is a wasted
session. Colab already ships torch, so it is left alone."""
    ),
    code(
        '''
import subprocess, sys

PINS = [
    "transformers==5.17.0",
    "trl==1.13.0",
    "peft==0.21.0",
    "datasets==5.0.1",
    "accelerate",
    "sentencepiece",     # convert_hf_to_gguf.py needs it for some tokenizers
    "protobuf",
]
subprocess.run([sys.executable, "-m", "pip", "install", "-q", *PINS], check=True)

import transformers, trl, peft, datasets
print("transformers", transformers.__version__)
print("trl         ", trl.__version__)
print("peft        ", peft.__version__)
print("datasets    ", datasets.__version__)
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
# If validate_dataset.py is not beside the notebook, upload it or clone the repo.
from pathlib import Path

if not Path("validate_dataset.py").exists():
    raise SystemExit("upload validate_dataset.py from the OmniAgent repo first")

from validate_dataset import validate_file

report = validate_file(Path(DATASET), min_examples=MIN_EXAMPLES)
print(report.render())
if not report.ok:
    raise SystemExit("dataset refused; fix it before training")
'''
    ),
    md("## 4. Load the base model"),
    code(
        '''
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
    device_map="auto" if torch.cuda.is_available() else None,
)
print(f"{BASE_MODEL}: {sum(p.numel() for p in model.parameters()):,} parameters")
print("device:", next(model.parameters()).device)
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
from peft import LoraConfig
from trl import SFTConfig, SFTTrainer

data = load_dataset("json", data_files=DATASET, split="train")
print(f"{len(data)} examples")

trainer = SFTTrainer(
    model=model,
    args=SFTConfig(
        output_dir="runs/omniagent",
        num_train_epochs=EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM,
        learning_rate=LEARNING_RATE,
        max_length=MAX_LENGTH,
        logging_steps=5,
        save_strategy="no",
        report_to=[],
        bf16=torch.cuda.is_available(),
        use_cpu=not torch.cuda.is_available(),
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
'''
    ),
    md("## 6. Merge the adapter into the base model"),
    code(
        '''
merged_dir = f"{OUTPUT_NAME}-merged"

merged = trainer.model.merge_and_unload()
merged.save_pretrained(merged_dir)
tokenizer.save_pretrained(merged_dir)

for path in sorted(Path(merged_dir).iterdir()):
    print(f"  {path.name:28} {path.stat().st_size:>12,} bytes")
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
inputs = tokenizer(prompt, return_tensors="pt").to(merged.device)
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
than the single script downloaded."""
    ),
    code(
        '''
import subprocess, sys
from pathlib import Path

LLAMA_CPP_REF = "master"   # pin to a tag for a reproducible build

if not Path("llama.cpp").exists():
    subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", LLAMA_CPP_REF,
         "https://github.com/ggml-org/llama.cpp.git"],
        check=True,
    )

gguf_path = f"{OUTPUT_NAME}-f16.gguf"
subprocess.run(
    [sys.executable, "llama.cpp/convert_hf_to_gguf.py", merged_dir,
     "--outfile", gguf_path, "--outtype", "f16"],
    check=True,
)
print(f"{gguf_path}: {Path(gguf_path).stat().st_size:,} bytes")
'''
    ),
    md(
        """## 9. Checksum and manifest

So that the file you download is provably the file you built."""
    ),
    code(
        '''
import hashlib, json, platform
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
    "examples": report.examples,
    "epochs": EPOCHS,
    "learning_rate": LEARNING_RATE,
    "lora": {"r": LORA_R, "alpha": LORA_ALPHA, "dropout": LORA_DROPOUT},
    "final_loss": round(result.training_loss, 4),
    "gguf": gguf_path,
    "gguf_sha256": sha256_of(gguf_path),
}
Path(f"{OUTPUT_NAME}-manifest.json").write_text(json.dumps(manifest, indent=2))
print(json.dumps(manifest, indent=2))
'''
    ),
    md(
        """## 10. Modelfile for Ollama

Written here so the download is self-contained."""
    ),
    code(
        r'''
modelfile = f"""FROM ./{gguf_path}

TEMPLATE \"\"\"{{{{ if .System }}}}<|im_start|>system
{{{{ .System }}}}<|im_end|>
{{{{ end }}}}{{{{ if .Prompt }}}}<|im_start|>user
{{{{ .Prompt }}}}<|im_end|>
{{{{ end }}}}<|im_start|>assistant
{{{{ .Response }}}}<|im_end|>
\"\"\"

PARAMETER temperature 0.1
PARAMETER stop "<|im_end|>"
PARAMETER stop "Observation:"
"""
Path("Modelfile").write_text(modelfile, encoding="utf-8")
print(modelfile)
'''
    ),
    md(
        """## 11. Download

Then, on the machine that runs Ollama:

```bash
ollama create omniagent -f Modelfile
python main.py --model omniagent --ask "What is 23% of 1800?"
```

OmniAgent accepts the untagged name; Ollama stores it as `omniagent:latest`."""
    ),
    code(
        '''
try:
    from google.colab import files
    files.download(gguf_path)
    files.download("Modelfile")
    files.download(f"{OUTPUT_NAME}-manifest.json")
except ImportError:
    print("not running in Colab; the files are in the working directory:")
    for name in (gguf_path, "Modelfile", f"{OUTPUT_NAME}-manifest.json"):
        print("  ", name)
'''
    ),
]

NOTEBOOK = {
    "cells": CELLS,
    "metadata": {
        "accelerator": "GPU",
        "colab": {"provenance": []},
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.12"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(NOTEBOOK, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"wrote {OUT} with {len(CELLS)} cells")
