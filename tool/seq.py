"""Cumulative change sequence: each policy follows its own accepted-baseline trajectory."""
import os, sys, json, tempfile
import aae
from aae import analyze, digests, evaluate, FILES

def R(fname, old, new):
    return (fname, old, new)

C = "ctrl.c"
STEPS = [
 ("S1", "Make lower saturation inclusive", {"code": {"clamp_cmd"}},
  [R(C, "  if (raw < 0) return 0;", "  if (raw <= 0) return 0;")]),
 ("S2", "Rate limiter via delta", {"code": {"rate_limit"}},
  [R(C, "  if (target > prev + RATE_STEP) return prev + RATE_STEP;\n  if (target < prev - RATE_STEP) return prev - RATE_STEP;\n  return target;",
        "  int32_t d = target - prev;\n  if (d > RATE_STEP) d = RATE_STEP;\n  if (d < -RATE_STEP) d = -RATE_STEP;\n  return prev + d;")]),
 ("S3", "Widen gain domain to [0,120] (gain 10/3)", {"code": {"gain"}, "contract": {"gain"}},
  [R(C, "__CPROVER_requires(0 <= cmd && cmd <= CMD_MAX)", "__CPROVER_requires(0 <= cmd && cmd <= 120)"),
   R(C, "return GAIN_K * cmd;", "return (cmd * 10) / 3;")]),
 ("S4", "Raise clamp upper limit to 120", {"code": {"clamp_cmd"}, "contract": {"clamp_cmd"}},
  [R(C, "__CPROVER_ensures(0 <= __CPROVER_return_value && __CPROVER_return_value <= CMD_MAX)\n{\n  if (raw",
        "__CPROVER_ensures(0 <= __CPROVER_return_value && __CPROVER_return_value <= 120)\n{\n  if (raw"),
   R(C, "  if (raw > CMD_MAX) return CMD_MAX;", "  if (raw > 120) return 120;")]),
 ("S5", "Mode logic as single expression", {"code": {"mode_next"}},
  [R(C, "  if (mode == MODE_SAFE) return MODE_SAFE;\n  if (fault != 0) return MODE_SAFE;\n  return MODE_RUN;",
        "  return (mode == MODE_SAFE || fault) ? MODE_SAFE : MODE_RUN;")]),
 ("S6", "Set GAIN_K to 3 (now unused)", {"config": {"GAIN_K"}},
  [R("config.h", "#define GAIN_K       4", "#define GAIN_K       3")]),
 ("S7", "Ring index wrap without modulo", {"code": {"ring_push"}},
  [R(C, "r->idx = (r->idx + 1) % RING_N;", "r->idx = (r->idx + 1 == RING_N) ? 0 : r->idx + 1;")]),
 ("S8", "Set RATE_STEP to 15", {"config": {"RATE_STEP"}},
  [R("config.h", "#define RATE_STEP    20", "#define RATE_STEP    15")]),
 ("S9", "Gain 4x over [0,120] with output bound 480", {"code": {"gain"}, "contract": {"gain"}},
  [R(C, "__CPROVER_return_value <= ACT_MAX)\n{\n  return (cmd * 10) / 3;", "__CPROVER_return_value <= 480)\n{\n  return 4 * cmd;")]),
 ("S10", "Filter accumulates in 64 bits", {"code": {"filter_avg"}},
  [R(C, "int32_t acc = 0;", "int64_t acc = 0;")]),
]

def base_state(files):
    td = tempfile.mkdtemp(prefix="seq_")
    aae.materialize(files, td)
    a = analyze(td)
    raw, full = digests(a, a["cg"])
    return a, raw, full

def main():
    files0 = {f: open(os.path.join(aae.BASE, f)).read() for f in FILES}
    out = {}
    for pol in ("B1", "B2", "B3"):
        files = dict(files0); traj = []
        a, raw, full = base_state(files)
        for sid, req, auth, edits in STEPS:
            auth = {"code": set(auth.get("code", ())), "contract": set(auth.get("contract", ())), "config": set(auth.get("config", ()))}
            nf = dict(files)
            for fname, old, new in edits:
                assert old in nf[fname], (pol, sid, old)
                nf[fname] = nf[fname].replace(old, new, 1)
            r = evaluate({"id": sid, "family": "seq", "request": req, "auth": auth, "files": nf}, a, raw, full)
            pr = r[pol]
            if pr["accept"]:
                files = nf
                a, raw, full = base_state(files)
            traj.append({"step": sid, "request": req, "accept": pr["accept"], "reason": pr["reason"],
                         "rerun": pr["rerun"], "secs": pr["secs"], "candidate_truth": r["truth"],
                         "affected_B3": r["affected_B3"]})
            print(pol, sid, pr["accept"], len(pr["rerun"]), r["truth"], flush=True)
        # final audit of the policy's baseline with the oracle
        td = tempfile.mkdtemp(prefix="final_")
        aae.materialize(files, td)
        out[pol] = {"trajectory": traj, "final_oracle": aae.oracle(td)}
        print(pol, "final", out[pol]["final_oracle"], flush=True)
    json.dump(out, open(os.path.join(aae.HERE, "..", "results", "seq_results.json"), "w"), indent=1, default=list)

main()
