"""Localize the 0xC0000409 crash in fit: run its stages with flushed
checkpoints. The last CHECKPOINT printed before the crash names the
dying stage. Run:  python debug_fit.py"""
import sys
sys.path.insert(0, ".")


def ck(msg):
    print(f"CHECKPOINT {msg}", flush=True)


ck("0 imports")
import csv as _csv
from biointel import config
from biointel.fit import (FEATURES, SPLIT, _n, _standardize,
                          _fit_logistic, _sigmoid, _auc_pr, _auc_roc)

ck("1 load panel")
with (config.GOLD / "model_panel.csv").open(encoding="utf-8") as f:
    rows = list(_csv.DictReader(f))
ck(f"2 rows={len(rows)}")

announce_by_iid = {}
epath = config.SILVER / "ma_events.csv"
if epath.exists():
    with epath.open(encoding="utf-8") as f:
        for e in _csv.DictReader(f):
            if e.get("Role") == "target" and e.get("AnnounceDate"):
                iid = str(e["FilerIID"])
                d = e["AnnounceDate"]
                if iid not in announce_by_iid or d < announce_by_iid[iid]:
                    announce_by_iid[iid] = d
ck(f"3 censor map={len(announce_by_iid)}")

usable = [r for r in rows
          if (r.get("Currency") or "USD") == "USD"
          and (_n(r.get("CashSTI")) is not None
               or (_n(r.get("TrialsTotal")) or 0) > 0)
          and not (str(r["IID"]) in announce_by_iid
                   and r["QuarterEnd"] >= announce_by_iid[str(r["IID"])])]
ck(f"4 usable={len(usable)}")

train = [r for r in usable if r["QuarterEnd"] <= SPLIT]
test = [r for r in usable if r["QuarterEnd"] > SPLIT]
ck(f"5 train={len(train)} test={len(test)}")

Xtr = [[fn(r) for _, fn in FEATURES] for r in train]
ytr = [1 if r.get("AcquiredNext12m") == "1" else 0 for r in train]
ck(f"6 train matrix pos={sum(ytr)}")
Xte = [[fn(r) for _, fn in FEATURES] for r in test]
yte = [1 if r.get("AcquiredNext12m") == "1" else 0 for r in test]
ck(f"7 test matrix pos={sum(yte)}")

Ztr, mu, sd = _standardize(Xtr)
ck("8 standardized train")
Zte, _, _ = _standardize(Xte, mu, sd)
ck("9 standardized test")

# logistic with per-50-iteration heartbeat
n, d = len(Ztr), len(Ztr[0])
pos = sum(ytr)
w_pos = (n - pos) / max(pos, 1)
w = [0.0] * d
b = 0.0
import math
for it in range(400):
    gb = 0.0
    gw = [0.0] * d
    for xi, yi in zip(Ztr, ytr):
        z = b + sum(wj * xj for wj, xj in zip(w, xi))
        p = 0.0 if z < -35 else 1.0 if z > 35 else 1.0 / (1.0 + math.exp(-z))
        wt = w_pos if yi else 1.0
        err = wt * (p - yi)
        gb += err
        for j in range(d):
            gw[j] += err * xi[j]
    scale = 0.5 / n
    b -= scale * gb
    for j in range(d):
        w[j] -= scale * (gw[j] + 1e-3 * w[j] * n)
    if it % 50 == 0:
        ck(f"10 logistic iter {it}")
ck("11 logistic done")

ste = [_sigmoid(b + sum(wj * xj for wj, xj in zip(w, z))) for z in Zte]
ck("12 scored test")
ck(f"13 AUC-PR test={_auc_pr(ste, yte):.4f} ROC={_auc_roc(ste, yte):.4f}")

from datetime import date, timedelta
mature_cut = (date.today() - timedelta(days=365)).isoformat()
mature_qs = [r["QuarterEnd"] for r in test if r["QuarterEnd"] <= mature_cut]
last_q = max(mature_qs) if mature_qs else max(r["QuarterEnd"] for r in test)
idx_last = [i for i, r in enumerate(test) if r["QuarterEnd"] == last_q]
top10 = sorted(idx_last, key=lambda i: -ste[i])[:10]
ck(f"14 mature quarter {last_q}: precision@10="
   f"{sum(yte[i] for i in top10)/max(len(top10),1):.2f}")
ck("15 COMPLETE - crash not reproduced in harness")
