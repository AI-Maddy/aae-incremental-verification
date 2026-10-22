"""Source model: split ctrl.c into per-function code and contract, compute digests."""
import re, hashlib, subprocess, os, tempfile

SIG = re.compile(r"^(?:int32_t|void)\s+(\w+)\s*\(", re.M)
FUNCS = ["filter_avg", "clamp_cmd", "gain", "rate_limit", "mode_next",
         "actuator_cmd", "ring_push", "control_step"]

def split_functions(src):
    """Return {name: {'sig','contract','body','text'}} for each top-level function."""
    out = {}
    starts = [(m.start(), m.group(1)) for m in SIG.finditer(src)]
    for i, (pos, name) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(src)
        text = src[pos:end].rstrip() + "\n"
        lines = text.splitlines()
        sig, contract, body = [lines[0]], [], []
        j = 1
        while j < len(lines) and lines[j].startswith("__CPROVER_") and not lines[j].startswith("__CPROVER_loop"):
            contract.append(lines[j]); j += 1
        body = lines[j:]
        out[name] = {"sig": lines[0], "contract": "\n".join(contract),
                     "body": "\n".join(body), "text": text}
    return out

def strip_contracts(src):
    """Remove contract and loop-invariant lines so Frama-C can parse the code."""
    keep = [l for l in src.splitlines() if not l.lstrip().startswith("__CPROVER_")]
    return "\n".join(keep) + "\n"

def macro_table(srcdir):
    r = subprocess.run(["gcc", "-dM", "-E", "config.h"], cwd=srcdir, capture_output=True, text=True)
    tab = {}
    for l in r.stdout.splitlines():
        m = re.match(r"#define (\w+) (.*)", l)
        if m and not m.group(1).startswith("_"):
            tab[m.group(1)] = m.group(2)
    return tab

def typedef_text(srcdir):
    s = open(os.path.join(srcdir, "config.h")).read()
    m = re.search(r"typedef struct .*?;", s, re.S)
    return m.group(0) if m else ""

def resolve(text, macros, typedefs):
    """Text plus values of every macro (transitively) and typedef it mentions."""
    seen, todo = {}, set(re.findall(r"\b[A-Za-z_]\w*\b", text))
    while todo:
        t = todo.pop()
        if t in macros and t not in seen:
            seen[t] = macros[t]
            todo |= set(re.findall(r"\b[A-Za-z_]\w*\b", macros[t]))
    extra = "".join(f"{k}={v};" for k, v in sorted(seen.items()))
    if "ring_t" in text:
        extra += typedefs
    return text + "\n/*env*/" + extra

def h(*parts):
    return hashlib.sha256("\x00".join(parts).encode()).hexdigest()[:16]

def callgraph(srcdir):
    """Call edges from Frama-C's Callgraph plugin on the contract-stripped source."""
    with tempfile.TemporaryDirectory() as td:
        stripped = os.path.join(td, "ctrl_stripped.c")
        open(stripped, "w").write(strip_contracts(open(os.path.join(srcdir, "ctrl.c")).read()))
        dot = os.path.join(td, "cg.dot")
        r = subprocess.run(["frama-c", "-cpp-extra-args=-I" + srcdir, stripped, "-cg", dot],
                           capture_output=True, text=True)
        if r.returncode or not os.path.exists(dot):
            return None  # unknown dependency information
        d = open(dot).read()
    edges = {}
    for a, b in re.findall(r'"UV (\w+) \(\d+\)" -> "UV (\w+) \(\d+\)"', d):
        edges.setdefault(a, set()).add(b)
    return edges
