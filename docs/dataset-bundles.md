# Dataset bundles — what gets stored, and how to train from one

A bundle is a directory holding one exported dataset together with metadata
to describe it and checksums to detect internal inconsistencies.
`scripts/publish_dataset.py` writes one; `--verify-only` checks it later.

The configured store is `G:\OmniAgent\datasets\<date>\`. G: is a removable
exFAT volume (checked: `DriveType Removable`, 2 TB) — **local hardware, not a
cloud sync folder**, which keeps this inside the project's local-only rule.
The publisher now requires a filesystem that enforces private staging through
persistent ACLs (Windows) or private directory permissions (Linux). exFAT does
not provide that guarantee, so publishing to G: fails closed until the store is
moved to a supported filesystem. Do not use a synced folder; publishing there
would send the dataset off the machine.

## What is in a bundle

| file | what it is |
|---|---|
| `dataset.jsonl` | the chat-format SFT examples, one JSON object per line |
| `dataset.jsonl.provenance.json` | the sidecar: example count and the sha256 of the system prompt the data was collected under |
| `collect-<date>.jsonl` | optional raw run log; it may contain user questions, model replies, tool inputs and observations |
| `collect-run-<date>.log` | optional console log; review its contents before including it |
| `MANIFEST.json` | the teacher model, the workspace rule, the source commit, and a sha256 per file |
| `SHA256SUMS` | the same digests in `sha256sum` format |
| `README.md` | this file |

Raw JSONL and console logs can contain private interactions. They are not
included by default. Before opting in with `--also`, review and redact them for
the intended recipients.

The provenance sidecar has exactly five keys: `dataset` (the dataset filename),
`examples` (a positive integer), `system_prompt_sha256` and
`live_prompt_sha256` (64 lowercase hexadecimal characters each), and
`matches_live_prompt` (a boolean equal to whether those two digests match).
The publisher validates this schema and checks the sidecar's dataset identity,
record count, and data fingerprint against the validated source before it
creates or changes anything in the destination.

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

The manifest has an exact schema, and its dataset name, example count and
prompt fingerprint are checked against the validated dataset and provenance
sidecar. The teacher model, workspace rule, source commit and publication time
are self-reported metadata. Without an external trust anchor or signature,
verification does not authenticate those claims, the bundle publisher, or who
produced the bundle. Manifest values are plaintext: use only non-secret
identifiers and short labels for teacher/workspace metadata. Never put
credentials, filesystem paths, or private free-text notes in these fields.

## Verify a bundle before you train on it

```
.venv/Scripts/python.exe scripts/publish_dataset.py --verify-only --dest "bundle-<date>"
```

The safe default stores bundles in the current user's private publisher
profile: Windows `FOLDERID_LocalAppData/OmniAgent/publish`, or Linux
`$XDG_DATA_HOME/omniagent/publish` (default `~/.local/share/omniagent/publish`).
`--dest` accepts one directory name inside that profile, not an arbitrary
filesystem path. The profile refuses unsafe owners, reparse points, inherited
Windows mutation grants to untrusted SIDs, and POSIX ancestors granting a
foreign identity both write and traverse access. Windows checks a conservative
DACL superset; it does not calculate native effective access. SYSTEM,
Administrators, and the exact TrustedInstaller SID are trusted principals;
compromise of those principals and processes sharing the same user SID/UID are
outside this local single-user boundary.

The old path API is deprecated and local-only. Use `--local-only-path` only
when intentionally accepting the absence of cross-identity destination
protection; the CLI prints a warning. Do not use this option for shared
workspaces or untrusted concurrent writers.

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
  --dest "bundle-<date>" \
  --teacher qwen2.5-coder:7b \
  --workspace-rule "without_own_transcripts: data/ listable, contents unreadable"
```

Each file is hashed at the source and again at the destination, and the
publish fails rather than reporting success if the two disagree. That check is
the reason this is a script and not a copy command: the destination is
private local-user profile, and a dataset is only worth training on if what
arrived is what was collected.

The publisher opens source files once and validates, hashes, and copies the
bytes read from those pinned handles. It holds the publisher profile and
destination ancestors while creating and verifying a private staging
directory through handles, then promotes with an atomic no-replace operation.
It fails closed when the OS or filesystem cannot provide those operations or
enforce private staging. Linux source files must not grant group or other write permission,
and files owned by another UID must not grant owner-write permission.
Windows source handles deny concurrent write and delete sharing. The publisher
captures extras into bounded memory snapshots before producing hashes or
staging output, so manifest and published bytes match the captured bytes; it
does not claim a point-in-time snapshot against a writer sharing the same
publisher identity. The current profile is single-user: same-SID/UID processes
are trusted and are not isolated. Shared service use, authentication, and hard
request cancellation are separate future work. A nonempty destination is refused; choose a new versioned
path for each publish. Verification accepts
only single-component filenames from `SHA256SUMS` and refuses symlink or reparse
targets, so a checksum entry cannot read outside the bundle. Verification
streams that file and caps it at 16 MiB, 4 KiB per line, and 100,000 entries;
an exceeded cap is an explicit verification error. Duplicate names are
reported and never cause the same payload to be hashed twice. Publishing and
verification share a 512 MiB aggregate bundle-byte cap: publication preflights
all source files plus generated `SHA256SUMS` and `MANIFEST.json` bytes before
creating or changing the destination; verification counts those metadata files
and the unique listed payloads before hashing them. Publication writes a
complete bundle in a sibling private staging directory and verifies the bytes
through the staging handles before promotion. A nonempty existing destination
is refused. Replacing an empty directory is attempted only through a supported
atomic handle-relative operation; otherwise publishing fails closed. The
verifier rejects staging directories, missing manifests, and manifests whose
file mapping differs from `SHA256SUMS`.

## Do not pool bundles

One bundle, one teacher, one workspace rule, one prompt fingerprint. Exporting
two collection logs into one dataset produces a dataset that is true of
neither — the same mistake `82884ae` fixed for the evaluation reports, where a
pooled figure across code versions described no version that had been run.
