"""REPL de Lean simulado (solo para pruebas): imita el protocolo JSON del REPL real."""
import json
import re
import sys
import time

buf, env_id = [], 0


def reply(obj):
    sys.stdout.write(json.dumps(obj, indent=2) + "\n\n")
    sys.stdout.flush()


POS = {"line": 1, "column": 0}
for line in sys.stdin:
    if line.strip():
        buf.append(line)
        continue
    if not buf:
        continue
    req = json.loads("".join(buf))
    buf = []
    cmd = req["cmd"]
    if "env" not in req:                       # import: crea el entorno base
        reply({"env": env_id})
        continue
    if "CRASH" in cmd:
        sys.exit(1)
    if "SLEEP" in cmd:
        time.sleep(30)
    out, msgs = {}, []
    if "zzz" in cmd:
        msgs.append({"severity": "error", "pos": {"line": 2, "column": 49}, "endPos": POS,
                     "data": "unknown identifier 'zzz'"})
    if "sorry" in cmd:
        msgs.append({"severity": "warning", "pos": {"line": 2, "column": 8}, "endPos": POS,
                     "data": "declaration uses 'sorry'"})
        out["sorries"] = [{"pos": POS, "endPos": POS, "goal": "⊢ False"}]
    for n in re.findall(r"#print axioms (\S+)", cmd):
        if "axiom ax" in cmd:
            ax = "[ax]"
        elif "sorry" in cmd:
            ax = "[sorryAx]"
        else:
            ax = "[propext, Classical.choice, Quot.sound]"
        msgs.append({"severity": "info", "pos": POS, "endPos": POS,
                     "data": f"'{n}' depends on axioms: {ax}"})
    env_id += 1
    out["messages"], out["env"] = msgs, env_id
    reply(out)
