"""AAE prototype orchestrator and replay study (policies B1, B2, B3, B3-noperm)."""
import os, sys, json, shutil, tempfile, subprocess, time, hashlib
from model import split_functions, macro_table, typedef_text, resolve, h, callgraph, FUNCS
import gates

FILES = ["ctrl.c", "config.h", "harness.c"]
TOOLCFG = "cbmc-5.95.1 " + " ".join(gates.CHECKS) + " dfcc"
LOOPS = lambda funcs, f: "for (" in funcs[f]["body"] or "while (" in funcs[f]["body"]
_cache = {}

def materialize(files, td):
    for k, v in files.items():
        open(os.path.join(td, k), "w").write(v)
    for extra in ("oracle.c", "randtest.c"):
        shutil.copy(os.path.join(BASE, extra), td)

def analyze(td):
    src = open(os.path.join(td, "ctrl.c")).read()
    funcs = split_functions(src)
    macros, typedefs = macro_table(td), typedef_text(td)
    harness = open(os.path.join(td, "harness.c")).read()
    cg = callgraph(td)
    return {"funcs": funcs, "macros": macros, "typedefs": typedefs, "harness": harness, "cg": cg}

def harness_line(harness, f):
    for l in harness.splitlines():
        if l.startswith(f"void h_{f}("):
            return l
    return ""

def digests(a, callees_of):
    """Raw digest (source text of f) and AAE digest (all semantic inputs of obligation O_f)."""
    raw, full = {}, {}
    for f in FUNCS:
        fn = a["funcs"].get(f)
        if fn is None:
            raw[f] = full[f] = "missing"; continue
        raw[f] = h(fn["text"])
        parts = [resolve(fn["sig"] + fn["contract"] + fn["body"], a["macros"], a["typedefs"])]
        for c in sorted(callees_of.get(f, ())):
            cf = a["funcs"].get(c)
            parts.append(c + ":" + (resolve(cf["sig"] + cf["contract"], a["macros"], a["typedefs"]) if cf else "missing"))
        parts += [harness_line(a["harness"], f), TOOLCFG]
        full[f] = h(*parts)
    return raw, full

def obligation(td, a, f, callees):
    key = h(open(os.path.join(td, "ctrl.c")).read(), open(os.path.join(td, "config.h")).read(),
            a["harness"], f, ",".join(sorted(callees)))
    if key not in _cache:
        _cache[key] = gates.run_obligation(td, f, sorted(callees), LOOPS(a["funcs"], f))
    return _cache[key]

def oracle(td):
    """Ground truth: whole-program CBMC on fixed requirements + native random/boundary tests with sanitizers."""
    g = os.path.join(td, "or.goto")
    r = subprocess.run(["goto-cc", "ctrl.c", "oracle.c", "-o", g], cwd=td, capture_output=True, text=True)
    if r.returncode:
        cb = "fail"
    else:
        try:
            r = subprocess.run(["cbmc", g, "--unwind", "17"] + gates.CHECKS, capture_output=True, text=True, timeout=300)
            cb = "pass" if "VERIFICATION SUCCESSFUL" in r.stdout else ("fail" if "VERIFICATION FAILED" in r.stdout else "unknown")
            cbfail = [l.strip() for l in r.stdout.splitlines() if l.endswith(": FAILURE")]
        except subprocess.TimeoutExpired:
            cb = "unknown"
    stubs = ["-D__CPROVER_requires(...)=", "-D__CPROVER_ensures(...)=", "-D__CPROVER_assigns(...)=",
             "-D__CPROVER_loop_invariant(...)="]
    exe = os.path.join(td, "rt")
    r = subprocess.run(["gcc", "-O1", "-fsanitize=undefined,address", "-fno-sanitize-recover=all", "-I."] + stubs +
                       ["ctrl.c", "randtest.c", "-o", exe], cwd=td, capture_output=True, text=True)
    if r.returncode:
        rt = "fail"
    else:
        r = subprocess.run([exe], capture_output=True, text=True, timeout=300)
        rt = "pass" if r.returncode == 0 and "PASS" in r.stdout else "fail"
    return cb, rt

def scope_ok(base, a, auth):
    """Textual footprint gate: changed code/contracts/config/harness must be authorized."""
    viol = []
    for f in FUNCS:
        b, c = base["funcs"][f], a["funcs"].get(f)
        if c is None:
            viol.append(f"removed {f}"); continue
        if (b["sig"] + b["body"]) != (c["sig"] + c["body"]) and f not in auth["code"]:
            viol.append(f"code:{f}")
        if b["contract"] != c["contract"] and f not in auth["contract"]:
            viol.append(f"contract:{f}")
    for m in set(base["macros"]) | set(a["macros"]):
        if base["macros"].get(m) != a["macros"].get(m) and m not in auth["config"]:
            viol.append(f"config:{m}")
    if base["typedefs"] != a["typedefs"]:
        viol.append("typedef")
    if base["harness"] != a["harness"]:
        viol.append("harness")
    return viol

def evaluate(cand, base, base_raw, base_full):
    td = tempfile.mkdtemp(prefix="cand_")
    materialize(cand["files"], td)
    a = analyze(td)
    res = {"id": cand["id"], "family": cand["family"], "request": cand["request"], "note": cand.get("note", "")}
    viol = scope_ok(base, a, cand["auth"])
    res["scope_violations"] = viol
    cg_union = None
    if a["cg"] is not None:
        cg_union = {f: set(base["cg"].get(f, ())) | set(a["cg"].get(f, ())) for f in FUNCS}
    callees = cg_union or {f: set(base["cg"].get(f, ())) for f in FUNCS}
    raw, full = digests(a, callees)
    plans = {
        "B1": [f for f in FUNCS if raw[f] != base_raw[f]],
        "B2": list(FUNCS),
        "B3": ([f for f in FUNCS if full[f] != base_full[f]] if cg_union is not None else list(FUNCS)),
    }
    plans["B3-noperm"] = plans["B3"]
    plans["B3-sys"] = plans["B3"]
    roots = [f for f in FUNCS if not any(f in base["cg"].get(g, ()) for g in FUNCS)]
    sysviol = [f"syscontract:{f}" for f in roots if f not in cand["auth"]["contract"] and
               resolve(base["funcs"][f]["contract"], base["macros"], base["typedefs"]) !=
               resolve(a["funcs"][f]["contract"], a["macros"], a["typedefs"])]
    res["sys_violations"] = sysviol
    res["affected_B3"] = plans["B3"]
    for pol, todo in plans.items():
        verdicts, secs = {}, 0.0
        gate_scope = pol != "B3-noperm"
        if gate_scope and (viol or (pol == "B3-sys" and sysviol)):
            res[pol] = {"accept": False, "reason": "scope", "rerun": [], "secs": 0.0, "verdicts": {}}
            continue
        for f in todo:
            v, t, d = obligation(td, a, f, callees.get(f, ()))
            verdicts[f] = (v, d[:200]); secs += t
        bad = {f: v for f, v in verdicts.items() if v[0] != "pass"}
        res[pol] = {"accept": not bad, "reason": ("ok" if not bad else "gate:" + ",".join(f"{f}={v[0]}" for f, v in bad.items())),
                    "rerun": todo, "secs": round(secs, 3), "verdicts": verdicts}
    cb, rt = oracle(td)
    res["oracle_cbmc"], res["oracle_rand"] = cb, rt
    res["truth"] = "defective" if "fail" in (cb, rt) else ("correct" if cb == rt == "pass" else "unknown")
    res["oracle_disagree"] = (cb != rt)
    shutil.rmtree(td, ignore_errors=True)
    return res

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(HERE, "..", "case_study")

def baseline():
    files = {f: open(os.path.join(BASE, f)).read() for f in FILES}
    a = analyze(BASE)
    raw, full = digests(a, a["cg"])
    for f in FUNCS:
        v = obligation(BASE, a, f, a["cg"].get(f, ()))
        assert v[0] == "pass", (f, v)
    return files, a, raw, full

if __name__ == "__main__":
    import candidates
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "results", "results.json")
    files, a, raw, full = baseline()
    cands = candidates.handwritten(files) + candidates.mutants(files)
    results = []
    for i, c in enumerate(cands):
        r = evaluate(c, a, raw, full)
        results.append(r)
        print(i, r["id"], r["truth"], {p: r[p]["accept"] for p in ("B1", "B2", "B3", "B3-noperm", "B3-sys")}, r["scope_violations"], flush=True)
    json.dump(results, open(out, "w"), indent=1, default=list)
