import sys, json, tempfile, pathlib, time, tracemalloc
sys.path.insert(0, ".")
import dataset_provenance as dp, export_dataset as ex
d = pathlib.Path(tempfile.mkdtemp())
def side(name, text):
    ds = d / name; ds.write_text("{}\n"); dp.sidecar_path(ds).write_text(text, encoding="utf-8")
    try: r = dp.read_sidecar(ds); print(f"sidecar {name}: returned {type(r).__name__}")
    except Exception as e: print(f"sidecar {name}: {type(e).__name__}: {str(e)[:70]}")
side("list", "[1]")
side("deep", "[" * 200000 + "]" * 200000)
tracemalloc.start(); side("big", '{"a": "' + "x" * (30 * 1024 * 1024) + '"}'); print("  peak MiB ~", tracemalloc.get_traced_memory()[1] // 2**20); tracemalloc.stop()
# export read_records: one 40 MiB line
f = d / "log.jsonl"; f.write_text('{"event": "x", "pad": "' + "y" * (40 * 1024 * 1024) + '"}\n')
tracemalloc.start()
try: n = sum(1 for _ in ex.read_records([f])); print("export read_records: yielded", n, "records from one 40 MiB line (no limit)")
except Exception as e: print("export read_records:", type(e).__name__, str(e)[:80])
print("  peak MiB ~", tracemalloc.get_traced_memory()[1] // 2**20)
f2 = d / "deep.jsonl"; f2.write_text("[" * 200000 + "]" * 200000 + "\n")
try: print("export deep:", sum(1 for _ in ex.read_records([f2])), "records")
except Exception as e: print("export deep:", type(e).__name__, str(e)[:80])
