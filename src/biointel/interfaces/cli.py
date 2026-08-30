#!/usr/bin/env python3
"""Command line for the biointel pipeline.

python -m biointel add REGN [MORE ...]        add companies
python -m biointel events IID                 FDA approvals + rejections
python -m biointel events-all                 every company
python -m biointel trials IID                 clinical trials
python -m biointel trials-all                 every company
python -m biointel calendar IID               pipeline calendar, trials + FDA
python -m biointel backfill                   fill CIK for migrated rows
python -m biointel fin IID                    SEC financials, one company
python -m biointel fin-all                    every company
python -m biointel snapshot                   cash, burn and runway per company
python -m biointel partners                   partnership network from trials
python -m biointel partners-of IID            one company's collaborators
python -m biointel deals IID                  8-K material agreements
python -m biointel deals-all                  every company
python -m biointel deals-of IID               one company's deal filings
python -m biointel cparty IID [N]             extract counterparties from filings
python -m biointel cparty-all [N]             every company
python -m biointel tags IID                   which XBRL tags a company reports
python -m biointel window "APPNO" YYYY-MM-DD  price window around one event
python -m biointel study "APPNO" YYYY-MM-DD   event-study metrics for one event
python -m biointel study-all                  metrics for every event since 2010
python -m biointel freeze                     snapshot silver+gold for reproducibility
python -m biointel relationships              N2: unified trial+deal partner table
python -m biointel labels                     L: ma_events.csv + label_panel.csv
python -m biointel features                   M1: feature_panel.csv + model_panel.csv
python -m biointel predict [QUARTER]          M3/M4: ranked M&A predictions
python -m biointel universe-probe             P1a: test EDGAR browse parsing (run FIRST)
python -m biointel patents-sql                PAT: generate BigQuery query from your company list
python -m biointel patents-import             PAT: consume BigQuery CSV export -> silver/patents.csv
python -m biointel pairs-substrate [MODE]     paired substrate comparison (patents|targets)
python -m biointel chembl-probe               CHM: test ChEMBL download route (run FIRST)
python -m biointel chembl-ingest              CHM: download+build silver/drug_targets.csv
python -m biointel pairs-exact                paired MASS-exact vs incumbent engine test
python -m biointel pairs-full-exact           full-universe re-rank with the adopted engine
python -m biointel orangebook-probe           OB: test Orange Book download (run FIRST)
python -m biointel universe                   P1a: build rule-defined universe.csv
python -m biointel harvest                    L: propose acquisition events for whole universe
python -m biointel verify-fill                L: auto-extract acquirers from merger proxies
python -m biointel ingest [N]                 P1b: ingest next N universe members (default 50)
python -m biointel backtest                   M5: rank of verified deals pre-announcement
python -m biointel fit [LEAD_DAYS]            M4: fitted model (optional censor lead, e.g. 90)
python -m biointel qa                         L-QA: agreement dates, EventClass, worklist
python -m biointel qa-corroborate             L-QA: auto-verify vs acquirer filings
python -m biointel qa-wiki                    L-QA: verify residue vs Wikipedia
python -m biointel robust                     M5: robustness suite
python -m biointel improve                    M6: iterate on VALIDATION (holdout locked)
python -m biointel list                       show companies
python -m biointel sponsors                   top CT.gov lead sponsors
python -m biointel coverage                   what was fetched, and when
"""

import csv
import sys

from biointel import (
    add_company,
    backfill_identity,
    build_partners,
    build_snapshot,
    config,
    coverage_report,
    get_all_counterparties,
    get_all_deals,
    get_all_events,
    get_all_financials,
    get_all_trials,
    get_counterparties,
    get_deals,
    get_events,
    get_financials,
    get_trials,
    pipeline_calendar,
    price_window,
    read_companies,
    read_events,
)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]

    if cmd == "add":
        for t in argv[2:]:
            print(add_company(t)["message"])

    elif cmd == "events":
        print(get_events(int(argv[2]))["message"])

    elif cmd == "events-all":
        r = get_all_events()
        for d in r["detail"]:
            print("  " + d["message"])
        print(f"{r['companies']} companies, {r['added']} new event rows")

    elif cmd == "trials":
        print(get_trials(int(argv[2]))["message"])

    elif cmd == "trials-all":
        r = get_all_trials()
        for d in r["detail"]:
            print("  " + d["message"])
        print(f"{r['companies']} companies, {r['added']} new trial rows")

    elif cmd == "calendar":
        iid = int(argv[2])
        rows = pipeline_calendar(iid)
        if not rows:
            print("Nothing yet. Run:  python -m biointel trials", iid)
            return 1
        out = config.GOLD / f"calendar_{iid}.csv"
        cols = ["Date", "Stage", "Drug", "Detail", "Status", "Ref", "Source"]
        with out.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        print(f"{len(rows)} rows -> {out}\n")
        for r in rows[:40]:
            print(
                f"  {r['Date']:<12} {r['Stage']:<16} {str(r['Drug'])[:34]:<34} "
                f"{str(r['Detail'])[:28]:<28} {r['Source']}"
            )
        if len(rows) > 40:
            print(f"  ... {len(rows) - 40} more in the CSV")

    elif cmd == "backfill":
        print(backfill_identity()["message"])

    elif cmd == "fin":
        print(get_financials(int(argv[2]))["message"])

    elif cmd == "fin-all":
        r = get_all_financials()
        for d in r["detail"]:
            print("  " + d["message"])
        print(f"{r['companies']} companies, {r['added']} new financial rows")

    elif cmd == "snapshot":
        rows = build_snapshot()
        if not rows:
            print("No financials yet. Run:  python -m biointel fin-all")
            return 1
        print(f"{len(rows)} companies -> {config.SNAPSHOT_CSV}\n")
        print(f"  {'IID':>3} {'TICK':<6} {'CASH+STI':>14} {'BURN/YR':>14} {'RUNWAY':>9}")
        print("  " + "-" * 52)
        for r in rows:
            cash = f"{r['TotalCash']:,.0f}" if r.get("TotalCash") else "-"
            burn = f"{r['BurnAnnual']:,.0f}" if r.get("BurnAnnual") else "-"
            run = f"{r['RunwayMonths']} mo" if r.get("RunwayMonths") else "profitable/na"
            print(f"  {r['IID']:>3} {r['Ticker']:<6} {cash:>14} {burn:>14} {run:>9}")
        print("\n  Sorted by runway, shortest first. Blank burn means the")
        print("  company is cash-flow positive or did not report OCF.")

    elif cmd == "partners":
        r = build_partners()
        print(r["message"])
        if r["status"] != "ok":
            return 1
        print(f"  -> {config.PARTNERS_CSV}")
        print(f"  -> {config.PARTNER_SUMMARY_CSV}\n")
        import csv as _csv

        rows = list(_csv.DictReader(config.PARTNER_SUMMARY_CSV.open(encoding="utf-8")))
        print(
            f"  {'TICK':<6}{'TOTAL':>6}{'INDUSTRY':>10}{'ACADEMIC':>10}"
            f"{'GOVT':>7}{'CRO':>6}{'DIAG':>6}{'CDMO':>6}"
        )
        print("  " + "-" * 57)
        for r2 in rows[:25]:
            print(
                f"  {r2['Ticker']:<6}{r2['TotalPartners']:>6}"
                f"{r2['Industry (unclassified)']:>10}{r2['Academic']:>10}"
                f"{r2['Government']:>7}{r2['CRO']:>6}"
                f"{r2['Diagnostics/Lab']:>6}{r2['CDMO/Manufacturing']:>6}"
            )

    elif cmd == "partners-of":
        import csv as _csv

        if not config.PARTNERS_CSV.exists():
            print("Run:  python -m biointel partners")
            return 1
        rows = [
            r
            for r in _csv.DictReader(config.PARTNERS_CSV.open(encoding="utf-8"))
            if str(r["IID"]) == argv[2]
        ]
        if not rows:
            print(f"No collaborators recorded for IID {argv[2]}.")
            return 1
        print(f"{rows[0]['Company']}  ({len(rows)} partners)\n")
        print(f"  {'TRIALS':>6}  {'TYPE':<24}{'PARTNER':<42}YEARS")
        print("  " + "-" * 92)
        for r2 in rows[:40]:
            yrs = f"{r2['FirstTrial'][:4]}-{r2['LastTrial'][:4]}" if r2["FirstTrial"] else ""
            print(f"  {r2['Trials']:>6}  {r2['Type'][:23]:<24}{r2['Collaborator'][:41]:<42}{yrs}")
        if len(rows) > 40:
            print(f"  ... {len(rows) - 40} more in the CSV")

    elif cmd == "deals":
        print(get_deals(int(argv[2]))["message"])

    elif cmd == "deals-all":
        r = get_all_deals()
        for d in r["detail"]:
            print("  " + d["message"])
        print(f"{r['companies']} companies, {r['added']} new deal rows")

    elif cmd == "deals-of":
        import csv as _csv

        if not config.DEALS_CSV.exists():
            print("Run:  python -m biointel deals-all")
            return 1
        rows = [
            r
            for r in _csv.DictReader(config.DEALS_CSV.open(encoding="utf-8"))
            if str(r["IID"]) == argv[2]
        ]
        if not rows:
            print(f"No deal filings for IID {argv[2]}.")
            return 1
        rows.sort(key=lambda r: r["FilingDate"], reverse=True)
        print(f"{rows[0]['Company']}  ({len(rows)} deal filings)\n")
        from collections import Counter

        for item, n in sorted(Counter(r["Item"] for r in rows).items()):
            lbl = (
                rows[0]["EventType"]
                if False
                else next(x["EventType"] for x in rows if x["Item"] == item)
            )
            print(f"   Item {item}  {n:>4}  {lbl}")
        print(f"\n  {'DATE':<12}{'ITEM':<7}{'EVENT':<38}URL")
        print("  " + "-" * 100)
        for r in rows[:30]:
            print(
                f"  {r['FilingDate']:<12}{r['Item']:<7}{r['EventType'][:37]:<38}{r['FilingURL'][:44]}"
            )
        if len(rows) > 30:
            print(f"  ... {len(rows) - 30} more in {config.DEALS_CSV.name}")

    elif cmd == "cparty":
        lim = int(argv[3]) if len(argv) > 3 else None
        r = get_counterparties(int(argv[2]), lim)
        print(r["message"])
        if r.get("added"):
            import csv as _csv

            rows = [
                x
                for x in _csv.DictReader(config.COUNTERPARTY_CSV.open(encoding="utf-8"))
                if str(x["IID"]) == argv[2]
            ]
            rows.sort(key=lambda x: x["FilingDate"], reverse=True)
            print(f"\n  {'DATE':<12}{'TYPE':<22}COUNTERPARTY")
            print("  " + "-" * 78)
            for x in rows[:30]:
                print(
                    f"  {x['FilingDate']:<12}{x['AgreementType'][:21]:<22}{x['Counterparty'][:44]}"
                )
            if len(rows) > 30:
                print(f"  ... {len(rows) - 30} more in {config.COUNTERPARTY_CSV.name}")

    elif cmd == "cparty-all":
        lim = int(argv[2]) if len(argv) > 2 else None
        r = get_all_counterparties(lim)
        for d in r["detail"]:
            print("  " + d["message"])
        print(f"{r['companies']} companies, {r['added']} counterparties")

    elif cmd == "tags":
        from biointel.sources.financials import inventory_tags

        c = next((x for x in read_companies() if str(x["IID"]) == argv[2]), None)
        if not c or not c.get("CIK"):
            print("No such IID, or no CIK on that row.")
            return 1
        tags = inventory_tags(c["CIK"])
        print(f"{c['Name']}  ({len(tags)} us-gaap tags reported)\n")
        for t, n in list(tags.items())[:50]:
            print(f"  {n:>5}  {t}")

    elif cmd == "window":
        rows = price_window(argv[2], argv[3])
        if not rows:
            print(
                "No window. Check the AppNo and date exist in events.csv,"
                " and that price data covers that date."
            )
            return 1
        out = config.GOLD / "window.csv"
        cols = [
            "IID",
            "AppNo",
            "Drug",
            "Event",
            "RelDay",
            "Date",
            "Open",
            "High",
            "Low",
            "Close",
            "AdjClose",
            "Volume",
            "PctFromT0",
        ]
        with out.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        print(f"{len(rows)} rows -> {out}")
        for r in rows:
            pct = "" if r["PctFromT0"] is None else f"{r['PctFromT0']:+7.2f}%"
            print(f"  {r['RelDay']:>3}  {r['Date']}  adj={r['AdjClose']:>9.2f}  {pct}")

    elif cmd == "relationships":
        from biointel.pipeline import build_relationships

        r = build_relationships()
        print(r["message"])
        if r["status"] != "ok":
            return 1

    elif cmd == "labels":
        from biointel.labels import MA_COLS, PANEL_COLS, build_label_panel
        from biointel.pipeline import CP_COLS as _CP
        from biointel.pipeline import _read, read_deals

        read_cp = lambda: _read(config.COUNTERPARTY_CSV, _CP)
        from biointel.labels import merged_events

        events = merged_events(read_companies, read_deals, read_cp)
        out = config.SILVER / "ma_events.csv"
        with out.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=MA_COLS, extrasaction="ignore")
            w.writeheader()
            w.writerows(events)
        panel = build_label_panel(read_companies, events)
        out2 = config.GOLD / "label_panel.csv"
        with out2.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=PANEL_COLS, extrasaction="ignore")
            w.writeheader()
            w.writerows(panel)
        n_t = sum(1 for e in events if e["Role"] == "target")
        n_a = sum(1 for e in events if e["Role"] == "acquirer")
        n_u = sum(1 for e in events if e["Role"] == "unknown")
        pos12 = sum(r["AcquiredNext12m"] for r in panel)
        print(f"{len(events)} M&A events -> {out}")
        print(f"  roles: {n_a} acquirer, {n_t} target, {n_u} unknown")
        print(f"{len(panel)} firm-quarters -> {out2}")
        print(f"  AcquiredNext12m positives: {pos12} ({100 * pos12 / len(panel):.2f}% base rate)")

    elif cmd == "features":
        from biointel.features import FEATURE_COLS, MODEL_COLS, build_features, join_with_labels

        feats = build_features(read_companies)
        out = config.GOLD / "feature_panel.csv"
        with out.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FEATURE_COLS, extrasaction="ignore")
            w.writeheader()
            w.writerows(feats)
        model = join_with_labels(feats)
        out2 = config.GOLD / "model_panel.csv"
        with out2.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=MODEL_COLS, extrasaction="ignore")
            w.writeheader()
            w.writerows(model)
        n_fin = sum(1 for r in feats if r.get("Cash") is not None)
        n_px = sum(1 for r in feats if r.get("PriceQ") not in (None, ""))
        pos = sum(1 for r in model if r.get("AcquiredNext12m") == "1")
        print(f"{len(feats)} firm-quarters -> {out}")
        print(f"  with financials: {n_fin}  with price: {n_px}")
        print(f"model panel -> {out2}  (positives joined: {pos})")

    elif cmd == "universe-probe":
        from biointel.universe import probe

        r = probe()
        print(r["message"])
        if r["status"] != "ok":
            return 1

    elif cmd == "patents-sql":
        from biointel.sources.patents import write_sql

        r = write_sql()
        print(r["message"])
        if r["status"] != "ok":
            return 1

    elif cmd == "patents-import":
        from biointel.sources.patents import import_export

        r = import_export()
        print(r["message"])
        if r["status"] != "ok":
            return 1

    elif cmd == "pairs-substrate":
        from biointel.baselines import pairs_substrates

        mode = argv[2] if len(argv) > 2 else "patents"
        r = pairs_substrates(mode=mode)
        if r["status"] != "ok":
            print(r["message"])
            return 1

    elif cmd == "chembl-probe":
        from biointel.sources.chembl import probe as ch_probe

        r = ch_probe()
        print(r["message"])
        if r["status"] != "ok":
            return 1

    elif cmd == "pairs-full-exact":
        from biointel.pairs import pairs_full_exact

        r = pairs_full_exact()
        if r["status"] != "ok":
            print(r["message"])
            return 1

    elif cmd == "pairs-exact":
        from biointel.pairs import pairs_exact

        r = pairs_exact()
        if r["status"] != "ok":
            print(r["message"])
            return 1

    elif cmd == "chembl-ingest":
        from biointel.sources.chembl import ingest as ch_ingest

        r = ch_ingest()
        print(r["message"])
        if r["status"] != "ok":
            return 1

    elif cmd == "orangebook-probe":
        from biointel.sources.orangebook import probe as ob_probe

        r = ob_probe()
        print(r["message"])
        if r["status"] != "ok":
            return 1

    elif cmd == "universe":
        from biointel.universe import build

        r = build(read_companies)
        print(r["message"])
        if r["status"] != "ok":
            return 1

    elif cmd == "harvest":
        from biointel.labels import harvest_universe

        r = harvest_universe()
        print(r["message"])
        if r["status"] != "ok":
            return 1

    elif cmd == "verify-fill":
        from biointel.labels import verify_fill

        r = verify_fill()
        print(r["message"])
        if r["status"] != "ok":
            return 1

    elif cmd == "ingest":
        from biointel.pipeline import ingest_universe

        n = int(argv[2]) if len(argv) > 2 else 50
        r = ingest_universe(n)
        print(r["message"])
        if r["status"] != "ok":
            return 1

    elif cmd == "predict":
        from biointel.score import predict

        res = predict(argv[2] if len(argv) > 2 else None)
        print(res["message"])
        if res["status"] != "ok":
            return 1
        print(f"  {'#':<3} {'Ticker':<7} {'Score':<6} Top acquirer (fit)   Known outcome")
        for r in res["rows"][:15]:
            print(
                f"  {r['Rank']:<3} {r['Ticker']:<7} {r['TargetScore']:<6.0f} "
                f"{r['Acquirer1']:<7} ({r['Fit1']:<5}) {r['KnownOutcome']}"
            )

    elif cmd == "fit":
        from biointel.fit import fit as _fit

        r = _fit(int(argv[2]) if len(argv) > 2 else 0)
        print(r["message"])
        if r["status"] != "ok":
            return 1

    elif cmd == "qa":
        from biointel.labels import qa_pass

        r = qa_pass()
        print(r["message"])
        if r["status"] != "ok":
            return 1

    elif cmd == "qa-corroborate":
        from biointel.labels import qa_corroborate

        r = qa_corroborate(read_companies)
        print(r["message"])
        if r["status"] != "ok":
            return 1

    elif cmd == "qa-wiki":
        from biointel.labels import qa_wiki

        r = qa_wiki(read_companies)
        print(r["message"])
        if r["status"] != "ok":
            return 1

    elif cmd == "robust":
        from biointel.fit import robust as _robust

        r = _robust()
        if r["status"] != "ok":
            print(r["message"])
            return 1
        print(f"\nreport -> {config.GOLD / 'robustness_report.txt'}")

    elif cmd == "improve":
        from biointel.fit import improve as _improve

        r = _improve()
        print(r["message"])
        if r["status"] != "ok":
            return 1

    elif cmd == "text-ingest":
        from biointel.pipeline import text_ingest

        r = text_ingest(int(argv[2]) if len(argv) > 2 else 100)
        print(r["message"])

    elif cmd == "pairs":
        from biointel.baselines import evaluate_pairs
        from biointel.pairs import build_pair_feature

        r1 = build_pair_feature()
        print(r1["message"])
        r2 = evaluate_pairs()
        print(r2["message"])
        if r2["status"] != "ok":
            return 1

    elif cmd == "pairs-fit":
        from biointel.baselines import supervised_pairs

        r = supervised_pairs()
        print(r["message"])
        if r["status"] != "ok":
            return 1

    elif cmd == "pairs-protocol":
        from biointel.baselines import pairs_protocol

        r = pairs_protocol()
        if r["status"] != "ok":
            print(r["message"])
            return 1

    elif cmd == "develop":
        from biointel.improve import develop as _dev

        if len(argv) > 2 and argv[2] == "tune":
            from biointel.improve import tune as _t

            r = _t()
        elif len(argv) > 2 and argv[2] == "textsweep":
            from biointel.improve import text_sweep as _ts

            r = _ts()
        else:
            r = _dev()
        if r["status"] != "ok":
            print(r["message"])
            return 1
        print(f"\nreport -> {config.GOLD / 'development_report.txt'}")

    elif cmd == "holdout":
        from biointel.improve import holdout as _ho

        r = _ho(argv[2], argv[3])
        print(r["message"])

    elif cmd == "backtest":
        from biointel.score import backtest

        lines = backtest()
        if not lines:
            print("No verified positive quarters in model_panel.csv.")
            return 1
        for ln in lines:
            print(" ", ln)

    elif cmd == "study":
        from datetime import date as _date

        from biointel.study import event_metrics

        ev = next(
            (
                e
                for e in read_events()
                if str(e["AppNo"]).strip() == argv[2].strip() and str(e["Date"]) == argv[3]
            ),
            None,
        )
        if ev is None:
            print("No such event in events.csv.")
            return 1
        co = next(c for c in read_companies() if str(c["IID"]) == str(ev["IID"]))
        m = event_metrics(co["Ticker"], _date.fromisoformat(argv[3]))
        if not m:
            print("No price window for that date.")
            return 1
        for k, v in m.items():
            print(f"  {k:<12} {v}")

    elif cmd == "study-all":
        from biointel.study import STUDY_COLS, run_study, summarize

        rows = run_study(read_events(), read_companies())
        if not rows:
            print("No computable events. Check price connectivity.")
            return 1
        out = config.GOLD / "event_study.csv"
        with out.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=STUDY_COLS, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        summ = summarize(rows)
        out2 = config.GOLD / "event_study_summary.csv"
        with out2.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(summ[0].keys()), extrasaction="ignore")
            w.writeheader()
            w.writerows(summ)
        print(f"{len(rows)} events -> {out}")
        print(f"{len(summ)} outcome classes -> {out2}")
        for r in summ:
            print(
                f"  {r['OutcomeClass']:<32} N={r['N']:<5} "
                f"CAR[-1,+1] mean {r['CAR_m1_p1_mean']}  median {r['CAR_m1_p1_median']}"
            )

    elif cmd == "freeze":
        import json as _json
        import shutil
        from datetime import date as _date

        dst = config.DATA / "frozen" / _date.today().isoformat().replace("-", "")
        dst.mkdir(parents=True, exist_ok=True)
        for sub in ("silver", "gold"):
            src = config.DATA / sub
            if src.exists():
                shutil.copytree(src, dst / sub, dirs_exist_ok=True)
        manifest = coverage_report()
        (dst / "manifest.json").write_text(_json.dumps(manifest, indent=1), encoding="utf-8")
        print(f"Frozen silver+gold + coverage manifest ({len(manifest)} fetches) -> {dst}")
        print("Bronze is immutable raw and is referenced by the manifest, not copied.")

    elif cmd == "list":
        for c in read_companies():
            print(f"  {c['IID']:>3}  {c['Ticker']:<6} {c['Name']}")

    elif cmd == "sponsors":
        from biointel.sources.trials import sponsor_landscape

        for v in sponsor_landscape()[:60]:
            print(f"  {v.get('studiesCount', 0):>7,}  {v.get('value', '')}")
        print("\n  NOTE: head of the distribution only. Small sponsors are absent.")

    elif cmd == "coverage":
        for m in coverage_report():
            print(f"  {m['fetched_at']}  {m.get('tag', '-'):<22} {m['status']}  {m['url'][:90]}")

    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
