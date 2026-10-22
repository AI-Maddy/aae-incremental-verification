# aae-incremental-verification

Prototype, case study and replay data for Atomic Agentic Engineering (AAE): contract-guided acceptance of untrusted code changes with dependency-aware reuse of verification evidence.

## Layout

| Path | Contents |
|---|---|
| `case_study/ctrl.c`, `config.h` | Eight-function sequential C controller (filter, clamp, gain, rate limiter, mode state machine, actuator gate, ring log, top-level step), each function annotated with CBMC code contracts |
| `case_study/harness.c` | One proof harness per function |
| `case_study/oracle.c` | Ground-truth oracle 1: whole-program CBMC check of the fixed system requirements, no component contracts |
| `case_study/randtest.c` | Ground-truth oracle 2: 200,000 random and boundary inputs on a native build with UBSan and ASan |
| `tool/model.py` | Splits functions into code and contract, resolves configuration macros, and builds the call graph with the Frama-C Callgraph plugin |
| `tool/gates.py` | Discharges one modular obligation per function with CBMC (`--dfcc --enforce-contract`, callees replaced by their contracts) |
| `tool/aae.py` | Footprint gate, evidence digests, the acceptance policies, and the replay driver |
| `tool/candidates.py` | The 99-candidate corpus: 60 single-site mutants and 39 hand-written change requests |
| `tool/seq.py` | Ten-step cumulative change sequence, run once per policy |
| `tool/summarize.py` | Prints acceptance and rejection rates, obligation counts and checker time |
| `results/` | Raw per-candidate JSON, sequence JSON and the printed summary |

## Policies

- **B1**: local-only checking. Re-runs proofs only for functions whose source text changed.
- **B2**: re-checks all obligations after every change.
- **B3**: AAE. Re-runs an obligation only when the digest of its inputs changes. The inputs are the function's code and contract, its callees' contracts, the configuration values these use (resolved), the harness, and the tool settings.
- **B3-sys**: B3, plus escalation when the resolved top-level contract changes without authorization.
- **B3-noperm**: B3 without the footprint and authorization gate.

## Requirements

Tested on Ubuntu 24.04 with:

    apt install cbmc frama-c-base gcc python3

That installs CBMC 5.95.1, Frama-C 25.0 (Manganese) and GCC 13.

## Reproduce

    python3 tool/aae.py                 # replay study; writes results/results.json (about 6 min on 4 cores)
    python3 tool/seq.py                 # sequence study; writes results/seq_results.json
    python3 tool/summarize.py           # prints the summary in results/summary.txt

All candidates are generated from `case_study/`, which is left unmodified; each candidate is evaluated in a temporary directory.
