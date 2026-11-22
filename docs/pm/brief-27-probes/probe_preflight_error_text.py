import sys, json, io, logging, contextlib
sys.path.insert(0, "."); sys.path.insert(0, "scripts")
import httpx
from openai import APIStatusError
import observability as obs, main as m
from agent import ReActAgent, AgentConfig
from tests.fakes import FakeOpenAI
import agent as a; print("agent file:", a.__file__)
obs.reset(); obs.configure(console=True, force=True)
resp = httpx.Response(500, request=httpx.Request("GET", "http://localhost/test"))
err = APIStatusError("SERVER_ERROR_CANARY", response=resp, body=None)
fake = FakeOpenAI(models_error=err)
ag = ReActAgent(config=AgentConfig(max_retries=0), client=fake.as_client())
out, errb = io.StringIO(), io.StringIO()
with contextlib.redirect_stdout(out), contextlib.redirect_stderr(errb):
    rc = m.preflight(ag)
print("rc", rc)
print("STDOUT has canary:", "SERVER_ERROR_CANARY" in out.getvalue(), "| STDERR(log) has canary:", "SERVER_ERROR_CANARY" in errb.getvalue(), "| prompt in any:", "PROMPT_CANARY" in out.getvalue()+errb.getvalue())
print(out.getvalue()[:300])
