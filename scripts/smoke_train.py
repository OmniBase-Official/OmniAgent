"""Run the whole fine-tuning pipeline on a CPU with a tiny model.

The notebook in ``notebooks/`` is meant for a Colab GPU and a real base model,
which cannot be exercised here. This script runs the same steps -- validate,
load, LoRA-train, merge, generate -- small enough to finish on a laptop, so
that an API change in transformers/trl/peft fails here rather than twenty
minutes into someone's Colab session.

It is a smoke test: it proves the pipeline executes, not that the model is any
good.

Usage::

    python scripts/smoke_train.py
    python scripts/smoke_train.py --dataset data/dataset.jsonl --epochs 1
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from validate_dataset import validate_file

#: Small enough to train on a CPU in under a minute, and Apache-2.0.
SMOKE_MODEL = "HuggingFaceTB/SmolLM2-135M-Instruct"

SYSTEM = (
    "You are OmniAgent. Reply with Thought/Action/Action Input, or "
    "Thought/Final Answer."
)


def synthetic_dataset(path: Path, count: int = 12) -> Path:
    """A handful of well-formed ReAct conversations, for when no log exists yet."""
    examples = []
    for index in range(count):
        left, right = index + 2, index + 3
        examples.append(
            {
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": f"What is {left} * {right}?"},
                    {
                        "role": "assistant",
                        "content": (
                            f"Thought: I should use the calculator.\n"
                            f"Action: calculate\nAction Input: {left} * {right}"
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Observation: {left} * {right} = {left * right}",
                    },
                    {
                        "role": "assistant",
                        "content": (
                            f"Thought: I have the result.\n"
                            f"Final Answer: {left} * {right} is {left * right}."
                        ),
                    },
                ]
            }
        )
    path.write_text(
        "\n".join(json.dumps(example, ensure_ascii=False) for example in examples) + "\n",
        encoding="utf-8",
    )
    return path


def step(number: int, title: str) -> None:
    print(f"\n[{number}/6] {title}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CPU smoke test for the training pipeline.")
    parser.add_argument("--dataset", type=Path, help="Dataset to use instead of a synthetic one.")
    parser.add_argument(
        "--model", default=SMOKE_MODEL, help=f"Base model (default: {SMOKE_MODEL})."
    )
    parser.add_argument("--epochs", type=float, default=1.0)
    parser.add_argument("--max-length", type=int, default=512)
    args = parser.parse_args(argv)

    started = time.perf_counter()
    workdir = Path(tempfile.mkdtemp(prefix="omniagent-smoke-"))
    print(f"workdir: {workdir}")

    # -- 1. the dataset ---------------------------------------------------- #
    step(1, "validate the dataset")
    dataset_path = args.dataset or synthetic_dataset(workdir / "smoke.jsonl")
    report = validate_file(dataset_path, min_examples=1)
    print(report.render())
    if not report.ok:
        print("\nREFUSED: the dataset did not validate", file=sys.stderr)
        return 1

    # Imported late so that a dataset problem is reported before torch loads.
    step(2, "load the base model")
    import torch
    from datasets import load_dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import SFTConfig, SFTTrainer

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(args.model, dtype=torch.float32)
    print(f"  {args.model}: {sum(p.numel() for p in model.parameters()):,} parameters")

    step(3, "train a LoRA adapter")
    data = load_dataset("json", data_files=str(dataset_path), split="train")
    print(f"  {len(data)} examples")

    trainer = SFTTrainer(
        model=model,
        args=SFTConfig(
            output_dir=str(workdir / "run"),
            num_train_epochs=args.epochs,
            per_device_train_batch_size=1,
            gradient_accumulation_steps=1,
            learning_rate=2e-4,
            max_length=args.max_length,
            logging_steps=5,
            save_strategy="no",
            report_to=[],
            use_cpu=True,
            seed=0,
        ),
        train_dataset=data,
        processing_class=tokenizer,
        peft_config=LoraConfig(
            r=8,
            lora_alpha=16,
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
            target_modules="all-linear",
        ),
    )
    result = trainer.train()
    print(f"  final loss: {result.training_loss:.4f}")

    step(4, "merge the adapter into the base model")
    merged = trainer.model.merge_and_unload()
    merged_dir = workdir / "merged"
    merged.save_pretrained(merged_dir)
    tokenizer.save_pretrained(merged_dir)
    files = sorted(p.name for p in merged_dir.iterdir())
    print(f"  saved to {merged_dir}: {', '.join(files)}")

    step(5, "generate once from the merged model")
    merged.eval()
    prompt = tokenizer.apply_chat_template(
        [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "What is 6 * 7?"},
        ],
        tokenize=False,
        add_generation_prompt=True,
    )
    inputs = tokenizer(prompt, return_tensors="pt")
    with torch.no_grad():
        output = merged.generate(
            **inputs, max_new_tokens=48, do_sample=False, pad_token_id=tokenizer.pad_token_id
        )
    reply = tokenizer.decode(output[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True)
    print(f"  reply: {reply.strip()[:300]!r}")

    step(6, "done")
    print(f"  the pipeline ran end to end in {time.perf_counter() - started:.1f}s")
    print("  (this proves the steps execute; it says nothing about model quality)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
