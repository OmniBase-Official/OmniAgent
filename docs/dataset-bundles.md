# Dataset bundles — what gets stored, and how to train from one

A bundle is a directory holding one exported dataset together with enough
record to reproduce it and enough proof to trust it. `scripts/publish_dataset.py`
writes one; `--verify-only` re-checks it later.

The store is `G:\OmniAgent\datasets\<date>\`. G: is a removable exFAT volume
(checked: `DriveType Removable`, 2 TB) — **local hardware, not a cloud sync
folder**, which is what keeps this inside the project's local-only rule.
If G: is ever replaced by a synced folder, stop: publishing there would send
the dataset off the machine.

## What is in a bundle

| file | what it is |
|---|---|
| `dataset.jsonl` | the chat-format SFT examples, one JSON object per line |
| `dataset.jsonl.provenance.json` | the sidecar: example count and the sha256 of the system prompt the data was collected under |
| `collect-<date>.jsonl` | the raw run log the dataset was exported from — the source of truth, kept because the export is lossy and its filters may change |
| `collect-run-<date>.log` | the console record: what was asked, what came back, how long each took |
| `MANIFEST.json` | the teacher model, the workspace rule, the source commit, and a sha256 per file |
| `SHA256SUMS` | the same digests in `sha256sum` format |
| `README.md` | this file |

## Why MANIFEST.json exists next to the sidecar

The sidecar answers one question — which system prompt was in force — and
refuses to let a missing answer read as agreement. Two other things change the
data just as much and it records neither:

- **The teacher.** The question bank is asked of whatever model is configured.
  A 1.5B fine-tune and a 7B coder do not answer alike, so a dataset without
  its teacher recorded cannot be compared with another.
- **The workspace rule.** Until `359967c` the agent could read its own earlier
  transcripts while being asked the bank, so a trajectory could contain an
  answer copied out of a log rather than worked out. Sealed, it cannot. A
  dataset collected on either side of that is a different dataset, and nothing
  in the file itself says which side it came from.

## Verify a bundle before you train on it

```
.venv/Scripts/python.exe scripts/publish_dataset.py --verify-only --dest "G:/OmniAgent/datasets/<date>"
```

An empty `verified` is the only passing answer. Any name printed means the
file on the drive no longer matches what was published, and the bundle should
not be trained on until that is understood.

## Train from a bundle

The pipeline is `notebooks/train_omniagent_lora.ipynb`, eleven cells: check
the machine, validate the dataset, load `Qwen/Qwen2.5-1.5B-Instruct`, train
the LoRA adapter, merge it, check it still speaks ReAct, convert to GGUF,
checksum and write the model manifest, register it with Ollama as `omniagent`,
run the agent on it.

Cell 2 reads the dataset from `PROJECT/data/dataset.jsonl`, so either copy the
bundle's `dataset.jsonl` there or point `DATASET` at the bundle. **Copy the
sidecar with it**: cell 6 runs `validate_dataset.validate_file` and the
pipeline is meant to refuse a dataset that cannot say what prompt it belongs
to.

`NUM_CTX` is 16384 on purpose. Ollama defaults to 4096 whatever the model
supports, and the system prompt is ~900 tokens before any tool output, so one
`read_file` passes that and returns HTTP 400.

For a CPU-only rehearsal of the whole pipeline without training anything real:

```
.venv/Scripts/python.exe scripts/smoke_train.py --dataset data/dataset.jsonl --epochs 1
```

## Publish a new bundle

```
.venv/Scripts/python.exe scripts/publish_dataset.py data/dataset.jsonl \
  --dest "G:/OmniAgent/datasets/<date>" \
  --teacher qwen2.5-coder:7b \
  --workspace-rule "without_own_transcripts: data/ listable, contents unreadable" \
  --also data/collect-<date>.jsonl data/collect-run-<date>.log docs/dataset-bundles.md
```

Each file is hashed at the source and again at the destination, and the
publish fails rather than reporting success if the two disagree. That check is
the reason this is a script and not a copy command: the destination is
removable media, and a dataset is only worth training on if what arrived is
what was collected.

## Do not pool bundles

One bundle, one teacher, one workspace rule, one prompt fingerprint. Exporting
two collection logs into one dataset produces a dataset that is true of
neither — the same mistake `82884ae` fixed for the evaluation reports, where a
pooled figure across code versions described no version that had been run.
