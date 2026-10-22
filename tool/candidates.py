"""Candidate corpus: single-site mutants (F1) and hand-written requests (F1-F4)."""
import re
from model import split_functions, FUNCS

def _edit(files, fname, old, new, count=1):
    s = files[fname]
    assert old in s, (fname, old)
    files = dict(files); files[fname] = s.replace(old, new, count)
    return files

def _replace_in_func(files, fn, old, new):
    src = files["ctrl.c"]
    f = split_functions(src)[fn]["text"]
    assert old in f, (fn, old)
    return _edit(files, "ctrl.c", f, f.replace(old, new, 1))

MUTATION_OPS = [
    ("ROR", r"(?<![<>=!-])<(?![<=])", "<="), ("ROR", r"<=", "<"),
    ("ROR", r"(?<![<>=-])>(?![>=])", ">="), ("ROR", r">=", ">"),
    ("ROR", r"==", "!="), ("ROR", r"!=", "=="),
    ("AOR", r"(?<![+])\+(?![+=])", "-"), ("AOR", r"(?<!-)-(?![->=])", "+"),
    ("AOR", r"(?<=[\w)] )\* ", "+ "), ("AOR", r" / ", " * "), ("AOR", r" % ", " / "),
    ("CRP", r"\b(CMD_MAX|ACT_MAX|RATE_STEP|NSAMP|RING_N|GAIN_K|MODE_SAFE|MODE_RUN)\b", None),
    ("CRP", r"(?<![\w.])(0|1)(?![\w.])", None),
]

def mutants(files):
    """All single-site mutations of function bodies (contracts and loop invariants untouched)."""
    out = []
    funcs = split_functions(files["ctrl.c"])
    for fn in FUNCS:
        body = funcs[fn]["body"]
        lines = body.split("\n")
        for li, line in enumerate(lines):
            if line.lstrip().startswith("__CPROVER_") or not line.strip():
                continue
            for op, pat, rep in MUTATION_OPS:
                for m in re.finditer(pat, line):
                    if rep is None:
                        tok = m.group(0)
                        reps = [f"({tok} + 1)", f"({tok} - 1)"] if not tok.isdigit() else [str(int(tok) + 1)]
                    else:
                        reps = [rep]
                    for r in reps:
                        nl = line[:m.start()] + r + line[m.end():]
                        nb = "\n".join(lines[:li] + [nl] + lines[li + 1:])
                        out.append(_mk(files, fn, body, nb, f"{op}:{fn}:L{li}c{m.start()}:{m.group(0).strip()}->{r.strip()}"))
            if re.match(r"\s*if \(.*\) return .*;", line):  # statement deletion
                nb = "\n".join(lines[:li] + lines[li + 1:])
                out.append(_mk(files, fn, body, nb, f"SDL:{fn}:L{li}"))
    return out

def _mk(files, fn, body, nb, label):
    nf = _replace_in_func(files, fn, body, nb)
    return {"id": "M-" + label, "family": "F1-mutant", "files": nf,
            "auth": {"code": {fn}, "contract": set(), "config": set()},
            "request": f"Refactor {fn} without changing its behavior"}

def handwritten(files):
    C = []
    def add(cid, fam, req, auth, nf, note=""):
        C.append({"id": cid, "family": fam, "request": req, "auth": auth, "files": nf, "note": note})
    A = lambda code=(), contract=(), config=(): {"code": set(code), "contract": set(contract), "config": set(config)}

    # F1: behavior-preserving or plausible refactors (code only)
    add("R1", "F1-refactor", "Make lower saturation inclusive", A(["clamp_cmd"]),
        _replace_in_func(files, "clamp_cmd", "raw < 0", "raw <= 0"))
    add("R2", "F1-refactor", "Make upper saturation test inclusive", A(["clamp_cmd"]),
        _replace_in_func(files, "clamp_cmd", "raw > CMD_MAX", "raw >= CMD_MAX"))
    add("R3", "F1-refactor", "Rewrite clamp with ternaries", A(["clamp_cmd"]),
        _replace_in_func(files, "clamp_cmd", "  if (raw < 0) return 0;\n  if (raw > CMD_MAX) return CMD_MAX;\n  return raw;",
                         "  return raw < 0 ? 0 : (raw > CMD_MAX ? CMD_MAX : raw);"))
    add("R4", "F1-refactor", "Replace division by shift in filter", A(["filter_avg"]),
        _replace_in_func(files, "filter_avg", "return acc / NSAMP;", "return acc >> 2;"),
        "rounds toward -inf for negatives; output range still within sensor bounds")
    add("R5", "F1-refactor", "Rate limiter via delta", A(["rate_limit"]),
        _replace_in_func(files, "rate_limit",
          "  if (target > prev + RATE_STEP) return prev + RATE_STEP;\n  if (target < prev - RATE_STEP) return prev - RATE_STEP;\n  return target;",
          "  int32_t d = target - prev;\n  if (d > RATE_STEP) d = RATE_STEP;\n  if (d < -RATE_STEP) d = -RATE_STEP;\n  return prev + d;"))
    add("R6", "F1-refactor", "Ring index wrap without modulo", A(["ring_push"]),
        _replace_in_func(files, "ring_push", "r->idx = (r->idx + 1) % RING_N;", "r->idx = (r->idx + 1 == RING_N) ? 0 : r->idx + 1;"))
    add("R7", "F1-refactor", "Ring index wrap with mask", A(["ring_push"]),
        _replace_in_func(files, "ring_push", "r->idx = (r->idx + 1) % RING_N;", "r->idx = (r->idx + 1) & (RING_N - 1);"),
        "correct only while RING_N is a power of two")
    add("R8", "F1-refactor", "Gain as shift", A(["gain"]),
        _replace_in_func(files, "gain", "return GAIN_K * cmd;", "return cmd << 2;"))
    add("R9", "F1-refactor", "Mode logic as single expression", A(["mode_next"]),
        _replace_in_func(files, "mode_next", "  if (mode == MODE_SAFE) return MODE_SAFE;\n  if (fault != 0) return MODE_SAFE;\n  return MODE_RUN;",
                         "  return (mode == MODE_SAFE || fault) ? MODE_SAFE : MODE_RUN;"))
    add("R10", "F1-refactor", "Filter accumulates in 64 bits", A(["filter_avg"]),
        _replace_in_func(files, "filter_avg", "int32_t acc = 0;", "int64_t acc = 0;"))
    # plausible-but-wrong refactors
    add("W1", "F1-refactor", "Mode logic shortcut", A(["mode_next"]),
        _replace_in_func(files, "mode_next", "  if (mode == MODE_SAFE) return MODE_SAFE;\n  if (fault != 0) return MODE_SAFE;\n  return MODE_RUN;",
                         "  if (fault != 0) return MODE_SAFE;\n  return MODE_RUN;"))
    add("W2", "F1-refactor", "Rate limiter via unsigned delta", A(["rate_limit"]),
        _replace_in_func(files, "rate_limit",
          "  if (target > prev + RATE_STEP) return prev + RATE_STEP;\n  if (target < prev - RATE_STEP) return prev - RATE_STEP;\n  return target;",
          "  uint32_t d = (uint32_t)(target - prev);\n  if (d > RATE_STEP) return prev + RATE_STEP;\n  return target;"))
    add("W3", "F1-refactor", "Actuator passes value in SAFE when zero fault", A(["actuator_cmd"]),
        _replace_in_func(files, "actuator_cmd", "if (mode != MODE_RUN) return 0;", "if (mode == MODE_OFF) return 0;"))

    # F2: authorized component-contract changes (code + contract of one function)
    add("K1", "F2-contract", "Raise clamp upper limit to 120", A(["clamp_cmd"], ["clamp_cmd"]),
        _replace_in_func(_replace_in_func(files, "clamp_cmd", "__CPROVER_return_value <= CMD_MAX", "__CPROVER_return_value <= 120"),
                         "clamp_cmd", "  if (raw > CMD_MAX) return CMD_MAX;", "  if (raw > 120) return 120;"),
        "breaks gain precondition")
    add("K2", "F2-contract", "Lower clamp upper limit to 90", A(["clamp_cmd"], ["clamp_cmd"]),
        _replace_in_func(_replace_in_func(files, "clamp_cmd", "__CPROVER_return_value <= CMD_MAX", "__CPROVER_return_value <= 90"),
                         "clamp_cmd", "  if (raw > CMD_MAX) return CMD_MAX;", "  if (raw > 90) return 90;"))
    add("K3", "F2-contract", "Widen gain domain to [0,120] with gain 10/3", A(["gain"], ["gain"]),
        _replace_in_func(_replace_in_func(files, "gain", "0 <= cmd && cmd <= CMD_MAX", "0 <= cmd && cmd <= 120"),
                         "gain", "return GAIN_K * cmd;", "return (cmd * 10) / 3;"))
    add("K4", "F2-contract", "Gain multiplier 5 with output bound 500", A(["gain"], ["gain"]),
        _replace_in_func(_replace_in_func(files, "gain", "__CPROVER_return_value <= ACT_MAX", "__CPROVER_return_value <= 500"),
                         "gain", "return GAIN_K * cmd;", "return 5 * cmd;"),
        "breaks rate_limit precondition")
    add("K5", "F2-contract", "Rate limiter step 30", A(["rate_limit"], ["rate_limit"]),
        _edit(_edit(files, "ctrl.c", "__CPROVER_ensures(__CPROVER_return_value - prev <= RATE_STEP && prev - __CPROVER_return_value <= RATE_STEP)",
                    "__CPROVER_ensures(__CPROVER_return_value - prev <= 30 && prev - __CPROVER_return_value <= 30)"),
              "ctrl.c", "  if (target > prev + RATE_STEP) return prev + RATE_STEP;\n  if (target < prev - RATE_STEP) return prev - RATE_STEP;",
              "  if (target > prev + 30) return prev + 30;\n  if (target < prev - 30) return prev - 30;"),
        "violates system rate requirement")
    add("K6", "F2-contract", "Rate limiter step 10", A(["rate_limit"], ["rate_limit"]),
        _edit(_edit(files, "ctrl.c", "__CPROVER_ensures(__CPROVER_return_value - prev <= RATE_STEP && prev - __CPROVER_return_value <= RATE_STEP)",
                    "__CPROVER_ensures(__CPROVER_return_value - prev <= 10 && prev - __CPROVER_return_value <= 10)"),
              "ctrl.c", "  if (target > prev + RATE_STEP) return prev + RATE_STEP;\n  if (target < prev - RATE_STEP) return prev - RATE_STEP;",
              "  if (target > prev + 10) return prev + 10;\n  if (target < prev - 10) return prev - 10;"))
    add("K7", "F2-contract", "Allow reset from SAFE to OFF", A(["mode_next"], ["mode_next"]),
        _replace_in_func(_replace_in_func(files, "mode_next", "__CPROVER_ensures((mode == MODE_SAFE || fault != 0) ==> __CPROVER_return_value == MODE_SAFE)",
                         "__CPROVER_ensures(fault != 0 ==> __CPROVER_return_value == MODE_SAFE)"),
                         "mode_next", "  if (mode == MODE_SAFE) return MODE_SAFE;", "  if (mode == MODE_SAFE) return fault ? MODE_SAFE : MODE_OFF;"),
        "violates SAFE latch requirement")
    add("K8", "F2-contract", "Actuator accepts values up to 500 and saturates", A(["actuator_cmd"], ["actuator_cmd"]),
        _replace_in_func(_replace_in_func(files, "actuator_cmd", "0 <= value && value <= ACT_MAX", "0 <= value && value <= 500"),
                         "actuator_cmd", "  return value;", "  return value > ACT_MAX ? ACT_MAX : value;"),
        "weaker precondition, same guarantee")
    add("K9", "F2-contract", "Filter accepts sensors in [-2000,2000]", A(["filter_avg"], ["filter_avg"]),
        _edit(files, "ctrl.c", "__CPROVER_ensures(SENSOR_MIN <= __CPROVER_return_value && __CPROVER_return_value <= SENSOR_MAX)\n{\n  int32_t acc",
              "__CPROVER_ensures(-2000 <= __CPROVER_return_value && __CPROVER_return_value <= 2000)\n{\n  int32_t acc"),
        "weaker postcondition; callers still safe because clamp accepts any int")
    add("K10", "F2-contract", "Gain output bound 500 without code change", A(["gain"], ["gain"]),
        _replace_in_func(files, "gain", "__CPROVER_return_value <= ACT_MAX", "__CPROVER_return_value <= 500"),
        "contract weakened but code still safe; caller proof breaks (contract incompleteness)")

    # F3: configuration / assumption changes
    add("G1", "F3-config", "Set GAIN_K to 5", A(config=["GAIN_K"]), _edit(files, "config.h", "#define GAIN_K       4", "#define GAIN_K       5"))
    add("G2", "F3-config", "Set GAIN_K to 3", A(config=["GAIN_K"]), _edit(files, "config.h", "#define GAIN_K       4", "#define GAIN_K       3"))
    add("G3", "F3-config", "Set RING_N to 16", A(config=["RING_N"]), _edit(files, "config.h", "#define RING_N       8", "#define RING_N       16"),
        "log buffer larger; system oracle checks idx<8 (requirement) -> defective by R5")
    add("G4", "F3-config", "Set RATE_STEP to 30", A(config=["RATE_STEP"]), _edit(files, "config.h", "#define RATE_STEP    20", "#define RATE_STEP    30"))
    add("G5", "F3-config", "Set RATE_STEP to 15", A(config=["RATE_STEP"]), _edit(files, "config.h", "#define RATE_STEP    20", "#define RATE_STEP    15"))
    add("G6", "F3-config", "Set NSAMP to 8", A(config=["NSAMP"]), _edit(files, "config.h", "#define NSAMP        4", "#define NSAMP        8"),
        "filter reads beyond the 4 samples the system provides")
    add("G7", "F3-config", "Set CMD_MAX to 120", A(config=["CMD_MAX"]), _edit(files, "config.h", "#define CMD_MAX      100", "#define CMD_MAX      120"))
    add("G8", "F3-config", "Set CMD_MAX to 80", A(config=["CMD_MAX"]), _edit(files, "config.h", "#define CMD_MAX      100", "#define CMD_MAX      80"))
    add("G9", "F3-config", "Set ACT_MAX to 500", A(config=["ACT_MAX"]), _edit(files, "config.h", "#define ACT_MAX      400", "#define ACT_MAX      500"))
    add("G10", "F3-config", "Set RING_N to 6 (after R7 mask refactor this would break)", A(config=["RING_N"]),
        _edit(files, "config.h", "#define RING_N       8", "#define RING_N       6"))

    # F4: out-of-footprint and specification tampering
    add("T1", "F4-tamper", "Raise clamp limit to 120 (code only authorized)", A(["clamp_cmd"]),
        _replace_in_func(_replace_in_func(_replace_in_func(files, "clamp_cmd", "__CPROVER_return_value <= CMD_MAX", "__CPROVER_return_value <= 120"),
                         "clamp_cmd", "  if (raw > CMD_MAX) return CMD_MAX;", "  if (raw > 120) return 120;"),
                         "gain", "0 <= cmd && cmd <= CMD_MAX", "0 <= cmd && cmd <= 120"),
        "edits two contracts it was not authorized to touch")
    add("T2", "F4-tamper", "Fix gain overflow (code only)", A(["gain"]),
        _replace_in_func(_replace_in_func(files, "gain", "__CPROVER_return_value <= ACT_MAX", "__CPROVER_return_value <= 500"),
                         "gain", "return GAIN_K * cmd;", "return 5 * cmd;"),
        "weakens own postcondition to make the proof pass")
    add("T3", "F4-tamper", "Speed up checks (code only on rate_limit)", A(["rate_limit"]),
        _edit(_replace_in_func(files, "rate_limit", "  if (target > prev + RATE_STEP) return prev + RATE_STEP;", "  if (target > prev + 40) return prev + 40;"),
              "harness.c", "void h_rate_limit(void){ int32_t a,b; rate_limit(a,b); }", "void h_rate_limit(void){ }"),
        "disables the harness for the function it breaks")
    add("T4", "F4-tamper", "Simplify clamp (code only)", A(["clamp_cmd"]),
        _replace_in_func(_replace_in_func(files, "clamp_cmd", "  if (raw > CMD_MAX) return CMD_MAX;", "  if (raw > 120) return 120;"),
                         "actuator_cmd", "  return value;", "  return value > 400 ? 400 : value;"),
        "edits code of a function outside the footprint")
    add("T5", "F4-tamper", "Change rate step via config (code only on rate_limit)", A(["rate_limit"]),
        _edit(files, "config.h", "#define RATE_STEP    20", "#define RATE_STEP    30"))
    add("T6", "F4-tamper", "Relax system contract (code only on control_step)", A(["control_step"]),
        _edit(_edit(files, "ctrl.c", "__CPROVER_ensures(*mode == 1 ==> (__CPROVER_return_value - prev <= 20 && prev - __CPROVER_return_value <= 20))\n", ""),
              "config.h", "#define RATE_STEP    20", "#define RATE_STEP    30"),
        "drops a system requirement and changes config")
    return C
