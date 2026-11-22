# ruff: noqa
import pathlib
import sys
import tempfile

sys.path.insert(0, ".")
import dataset_provenance as dp

print("module:", dp.__file__)
d = pathlib.Path(tempfile.mkdtemp())


def run(name, text, fn):
    p = d / name
    p.write_text(text, encoding="utf-8")
    try:
        r = fn(p)
        print(f"{name}: OK -> {str(r)[:60]}")
    except Exception as e:
        print(f"{name}: {type(e).__name__}: {str(e)[:80]}")


run("list_line.jsonl", "[1,2]\n", dp.dataset_fingerprint)
run("str_line.jsonl", '"x"\n', dp.dataset_fingerprint)
run("deep.jsonl", "[" * 200000 + "]" * 200000 + "\n", dp.dataset_fingerprint)
run("badmsgs.jsonl", '{"messages": 5}\n', dp.dataset_fingerprint)
run("badmsg_item.jsonl", '{"messages": [1]}\n', dp.dataset_fingerprint)
run("sidecar_list.json", "[1]", dp.read_sidecar)
run("sidecar_deep.json", "[" * 200000 + "]" * 200000, dp.read_sidecar)
run("sidecar_big.json", '{"a": "' + "x" * (20 * 1024 * 1024) + '"}', dp.read_sidecar)
