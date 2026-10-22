import json, math, collections, sys
R = json.load(open(sys.argv[1] if len(sys.argv) > 1 else __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "..", "results", "results.json")))
P = ["B1", "B2", "B3", "B3-sys", "B3-noperm"]
def wilson(k, n, z=1.96):
    if n == 0: return (float("nan"),) * 2
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - r) / d, (c + r) / d)
print("N", len(R), collections.Counter(r["truth"] for r in R), "disagree", [r["id"] for r in R if r["oracle_disagree"]])
fams = sorted(set(r["family"] for r in R))
for fam in fams + ["ALL"]:
    S = [r for r in R if fam == "ALL" or r["family"] == fam]
    d = [r for r in S if r["truth"] == "defective"]; c = [r for r in S if r["truth"] == "correct"]
    print(f"\n{fam}: n={len(S)} defective={len(d)} correct={len(c)}")
    for p in P:
        fa = sum(r[p]["accept"] for r in d); fr = sum(not r[p]["accept"] for r in c)
        ob = sum(len(r[p]["rerun"]) for r in S); sec = sum(r[p]["secs"] for r in S)
        lo, hi = wilson(fa, len(d))
        print(f"  {p:10s} FAR {fa}/{len(d)} [{lo:.2f},{hi:.2f}]  FRR {fr}/{len(c)}  oblig {ob}  cpu {sec:.1f}s")
print("\nB1 accepted defective:", [r["id"] for r in R if r["truth"] == "defective" and r["B1"]["accept"]])
print("B3 accepted defective:", [r["id"] for r in R if r["truth"] == "defective" and r["B3"]["accept"]])
print("B3-sys accepted defective:", [r["id"] for r in R if r["truth"] == "defective" and r["B3-sys"]["accept"]])
print("B3-noperm accepted defective:", [r["id"] for r in R if r["truth"] == "defective" and r["B3-noperm"]["accept"]])
print("B3 rejected correct:", [(r["id"], r["B3"]["reason"][:60]) for r in R if r["truth"] == "correct" and not r["B3"]["accept"]])
print("B3-sys rejected correct extra:", [r["id"] for r in R if r["truth"] == "correct" and not r["B3-sys"]["accept"] and r["B3"]["accept"]])
print("B2 vs B3 decisions differ:", [r["id"] for r in R if r["B2"]["accept"] != r["B3"]["accept"]])
print("B3 affected-set size dist:", collections.Counter(len(r["affected_B3"]) for r in R))
for r in R:
    if r["family"] != "F1-mutant": print(r["id"], r["truth"], r["oracle_cbmc"], r["oracle_rand"], {p: r[p]["accept"] for p in P}, r["affected_B3"], r["scope_violations"], r.get("sys_violations"))
