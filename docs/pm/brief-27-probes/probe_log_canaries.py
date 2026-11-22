import sys, io, contextlib
sys.path.insert(0, ".")
import observability as obs, main as m
from agent import ReActAgent, AgentConfig
from tests.fakes import FakeOpenAI
import agent as a; print("agent file:", a.__file__)
CAN = ["Q_CANARY", "T_CANARY", "A_CANARY", "ARGS_CANARY", "OBS_CANARY"]
obs.reset(); obs.configure(console=True, force=True)
fake = FakeOpenAI(replies=["Thought: T_CANARY\nAction: calculate\nAction Input: 2 + 2", "Thought: done\nFinal Answer: A_CANARY",])
ag = ReActAgent(config=AgentConfig(max_retries=0, verbose=False), client=fake.as_client())
out, err = io.StringIO(), io.StringIO()
with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
    rc = m.answer(ag, "Q_CANARY")
log = err.getvalue()
print("rc", rc, "| log lines", len(log.splitlines()))
print("canaries in LOG:", [c for c in CAN if c in log], "| in stdout:", [c for c in CAN if c in out.getvalue()])
