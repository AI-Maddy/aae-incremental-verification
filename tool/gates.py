"""CBMC gate runner: modular contract obligations for one function."""
import subprocess, tempfile, os, time, re

CHECKS = ["--signed-overflow-check", "--bounds-check", "--pointer-check",
          "--div-by-zero-check", "--unwinding-assertions"]
TIMEOUT = 120

def run_obligation(srcdir, fn, callees, has_loop, timeout=TIMEOUT):
    """Return (verdict, seconds, detail). verdict in pass/fail/unknown."""
    t0 = time.time()
    with tempfile.TemporaryDirectory() as td:
        g1, g2 = os.path.join(td, "a.goto"), os.path.join(td, "b.goto")
        r = subprocess.run(["goto-cc", "--function", "h_" + fn, "ctrl.c", "harness.c", "-o", g1],
                           cwd=srcdir, capture_output=True, text=True)
        if r.returncode:
            return "fail", time.time() - t0, "compile: " + (r.stderr or r.stdout)[-300:]
        cmd = ["goto-instrument", "--dfcc", "h_" + fn, "--enforce-contract", fn]
        if has_loop:
            cmd.append("--apply-loop-contracts")
        for c in callees:
            cmd += ["--replace-call-with-contract", c]
        r = subprocess.run(cmd + [g1, g2], capture_output=True, text=True)
        if r.returncode:
            return "unknown", time.time() - t0, "instrument: " + (r.stderr or r.stdout)[-300:]
        try:
            r = subprocess.run(["cbmc", g2] + CHECKS, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return "unknown", time.time() - t0, "timeout"
        out = r.stdout
        if "VERIFICATION SUCCESSFUL" in out:
            return "pass", time.time() - t0, ""
        if "VERIFICATION FAILED" in out:
            fails = [l for l in out.splitlines() if l.endswith(": FAILURE")]
            return "fail", time.time() - t0, "; ".join(fails)[:400]
        return "unknown", time.time() - t0, out[-300:]
