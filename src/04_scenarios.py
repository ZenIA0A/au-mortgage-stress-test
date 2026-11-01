"""Step 4: scenarios for the cash rate to end-2027, the repayment burden they imply, and what the arrears model says about
mortgage non-performing loans to 2028Q4. Monte Carlo over model uncertainty (lag, coefficients, residual persistence, pass-through).
Then: provisions and hardship workload for a HYPOTHETICAL mid-tier lender, risk-based pricing by LVR band, reverse stress test,
sensitivity (tornado) and early-warning triggers.

Everything about the lender (book size, average loan, LGD, cases per officer, time in default) is an ASSUMPTION and labelled so.
Everything about the system (rates, burden, arrears, LVR bands, new-lending standards) is real RBA / APRA data."""
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from common import *
import style as st

st.setup()
rng = np.random.default_rng(2026)
Q = pd.read_csv("data/macro_quarterly.csv", index_col=0, parse_dates=True)
A = pd.read_csv("data/apra_panel_quarterly.csv", index_col=0, parse_dates=True)
BS = json.load(open("outputs/burden_stats.json")); MS = json.load(open("outputs/model_stats.json"))
START = pd.Timestamp("2021-12-31")
IDX = pd.date_range("2021-12-31", "2028-12-31", freq="QE")
HOR = IDX[IDX > "2026-06-30"]                         # 2026Q3 .. 2028Q4
SC_Q = pd.date_range("2026-09-30", "2027-12-31", freq="QE")     # quarters in which a cash-rate path is needed (6)
N = 4000
S = {}

# ---------------- scenario definitions (cash rate at quarter end; 4.60% after the 30 Sep 2026 hike is the common starting point)
CASH = {
    "A. Hold":      [4.60, 4.60, 4.60, 4.60, 4.60, 4.60],
    "B. Ease":      [4.60, 4.60, 4.60, 4.35, 4.10, 4.10],
    "C. Hawkish":   [4.60, 4.85, 5.10, 5.10, 5.10, 5.10],
    "D. Severe":    [4.60, 4.85, 5.10, 5.35, 5.60, 5.60],
}
U_SEVERE_END = 6.0                                     # severe scenario adds a job-loss shock: unemployment to 6.0% by 2027Q4 (assumption)
cash0, disc0, hdti0 = float(Q.cash_rate.loc["2026-06-30"]), float(Q.disc_var_oo.loc["2026-06-30"]), float(Q.housing_debt_to_income.loc["2026-06-30"])
u0 = float(Q.unemployment.loc["2026-06-30"]); K = BS["passthrough_disc"]["cumulative"]; K_SE = BS["passthrough_disc"]["se"]
B_obs = Q.interest_burden.reindex(IDX)

def burden_path(cash_path, k=K, hdti_growth=0.0):
    """Interest burden (% of disposable income) per quarter; observed to 2026Q2, then HDTI x discounted variable rate."""
    b = B_obs.copy()
    for n, (d, c) in enumerate(zip(SC_Q, cash_path), start=1):
        b.loc[d] = (hdti0 + hdti_growth * n) * (disc0 + k * (c - cash0)) / 100
    b = b.ffill()                                      # beyond 2027Q4 not needed (lags >= 4 quarters)
    return b

# ---------------- model fits for each lag and each series (system and the peer group of the hypothetical lender)
def ols(y, X):
    X = np.column_stack([np.ones(len(y))] + list(X)); b = np.linalg.lstsq(X, y, rcond=None)[0]; return b, y - X @ b

def fit_lag(series, L, n_draw=N, seed=7):
    d = pd.DataFrame({"y": series, "x": Q.interest_burden.shift(L)}).reindex(series.index); d = d[d.index >= START].dropna()
    b, e = ols(d.y.values, [d.x.values]); n = len(d)
    rho = float(np.clip(np.corrcoef(e[1:], e[:-1])[0, 1], 0, 0.9))
    r = np.random.default_rng(seed + L); draws = []
    for _ in range(n_draw):
        blocks = [r.integers(0, n - 3) for _ in range(int(np.ceil(n / 4)))]; eb = np.concatenate([e[s:s + 4] for s in blocks])[:n]
        yb = (b[0] + b[1] * d.x.values) + eb; bb, ee = ols(yb, [d.x.values]); draws.append([bb[0], bb[1], np.std(ee, ddof=2)])
    return dict(b=b, resid=e, rho=rho, draws=np.array(draws), last_y=d.y.values[-1], last_x=d.x.values[-1], n=n)

SERIES = {"system": A[A.group == "All ADIs"].npl_ratio, "peer": A[A.group == "Other domestic banks"].npl_ratio}
LAGS = [4, 5, 6]
FITS = {s: {L: fit_lag(y, L) for L in LAGS} for s, y in SERIES.items()}
for s in FITS: print(s, {L: (round(float(f["b"][0]), 3), round(float(f["b"][1]), 4), round(f["rho"], 2)) for L, f in FITS[s].items()})
S["fits"] = {s: {str(L): dict(const=round(float(f["b"][0]), 3), slope=round(float(f["b"][1]), 4), rho=round(f["rho"], 2)) for L, f in FITS[s].items()} for s in FITS}

# unemployment overlay: effect per percentage point from the 'burden + unemployment' robustness regression (weakly identified, n = 19)
GAMMA, GAMMA_SE = MS["robustness"]["+ unemployment"]["coefs"]["u"]; GAMMA_SE = max(GAMMA_SE, 0.026)
u_path = pd.Series(u0, index=IDX)
ramp = np.linspace(u0, U_SEVERE_END, len(SC_Q) + 1)[1:]
for d, v in zip(SC_Q, ramp): u_path.loc[d] = v
u_path[u_path.index > SC_Q[-1]] = ramp[-1]
u_path[u_path.index <= "2026-06-30"] = u0

# ---------------- Monte Carlo
def simulate(series_key, scen):
    cash = CASH[scen]; F = FITS[series_key]
    lag_j = rng.choice(LAGS, size=N); k_j = np.clip(rng.normal(K, K_SE, N), 0.5, 1.0)
    cj = np.zeros(N); sj = np.zeros(N); sg = np.zeros(N); rh = np.zeros(N); e0 = np.zeros(N)
    for L in LAGS:
        m = lag_j == L; pick = rng.integers(0, N, m.sum()); dr = F[L]["draws"][pick]
        cj[m], sj[m], sg[m] = dr[:, 0], dr[:, 1], dr[:, 2]; rh[m] = F[L]["rho"]
        e0[m] = F[L]["last_y"] - (dr[:, 0] + dr[:, 1] * F[L]["last_x"])
    gam = rng.normal(GAMMA, GAMMA_SE, N) if scen.startswith("D") else np.zeros(N)
    # burden paths per draw (pass-through differs by draw)
    Bm = np.zeros((N, len(IDX)))
    Bobs = B_obs.values.copy()
    Bm[:] = Bobs
    for d, c in zip(SC_Q, cash):
        col = IDX.get_loc(d); Bm[:, col:] = (hdti0 * (disc0 + k_j * (c - cash0)) / 100)[:, None]
    out = np.zeros((N, len(HOR))); e = e0.copy()
    for h, d in enumerate(HOR):
        t = IDX.get_loc(d); e = rh * e + np.sqrt(1 - rh ** 2) * sg * rng.standard_normal(N)
        xb = Bm[np.arange(N), t - lag_j]
        out[:, h] = cj + sj * xb + e + gam * (u_path.loc[d] - u0)
    return out, Bm

NPLNOW = {s: float(SERIES[s].iloc[-1]) for s in SERIES}
res, burden_q = {}, {}
for key in SERIES:
    res[key] = {}
    for sc in CASH:
        o, Bm = simulate(key, sc); res[key][sc] = o
        if key == "system": burden_q[sc] = np.median(Bm, axis=0)
qs = [5, 10, 50, 90, 95]
fan = []
for key in SERIES:
    for sc in CASH:
        for h, d in enumerate(HOR):
            v = np.percentile(res[key][sc][:, h], qs); fan.append(dict(series=key, scenario=sc, quarter=quarter_label(d), **{f"p{q}": round(float(x), 3) for q, x in zip(qs, v)}))
fan = pd.DataFrame(fan); fan.to_csv("outputs/scenario_npl_fan.csv", index=False)
bt = pd.DataFrame({sc: pd.Series(burden_q[sc], index=IDX) for sc in CASH}); bt.round(2).to_csv("outputs/scenario_burden.csv")
print(fan[(fan.series == "system") & fan.quarter.isin(["2027Q3", "2028Q2", "2028Q4"])].to_string(index=False))

# locked-in path: until 2027Q3 every scenario gives the same answer because the model uses burden lagged 5 quarters (burden to 2026Q2 is known)
base_known = fan[(fan.series == "system") & (fan.scenario == "A. Hold")].set_index("quarter").p50
S["system"] = {sc: {q: {k: float(fan[(fan.series == "system") & (fan.scenario == sc) & (fan.quarter == q)][k].iloc[0]) for k in ("p5", "p10", "p50", "p90", "p95")} for q in ("2027Q3", "2028Q2", "2028Q4")} for sc in CASH}
S["peer"] = {sc: {q: {k: float(fan[(fan.series == "peer") & (fan.scenario == sc) & (fan.quarter == q)][k].iloc[0]) for k in ("p5", "p10", "p50", "p90", "p95")} for q in ("2027Q3", "2028Q2", "2028Q4")} for sc in CASH}
S["npl_now"] = NPLNOW
S["burden_by_scenario"] = {sc: {q: round(float(bt.loc[pd.Timestamp(d), sc]), 2) for q, d in [("2026Q3", "2026-09-30"), ("2027Q1", "2027-03-31"), ("2027Q3", "2027-09-30"), ("2027Q4", "2027-12-31")]} for sc in CASH}
S["peak_burden"] = {sc: round(float(bt[sc]["2026-09-30":].max()), 2) for sc in CASH}
S["in_sample_burden_max"] = round(float(Q.interest_burden[Q.interest_burden.index >= START].max()), 2)
S["lag5_locked_until"] = "2027Q3"

# ---------------- hypothetical lender (ASSUMPTIONS)
BOOK_BN, AVG_LOAN_K, CASES_PER_OFFICER, TIME_IN_NPL_Y = 60.0, 450.0, 80, 1.5
LGDS = [0.10, 0.20, 0.30]
ASSUME = dict(book_bn=BOOK_BN, avg_loan_k=AVG_LOAN_K, cases_per_officer=CASES_PER_OFFICER, time_in_npl_years=TIME_IN_NPL_Y, lgd_base=0.20, lgd_range=LGDS, peer_group="Other domestic banks (APRA)")
S["assumptions"] = ASSUME
lend = {}
for sc in CASH:
    o = res["peer"][sc]; peak = o.max(axis=1); dstock = (np.percentile(peak, [50, 90]) - NPLNOW["peer"]) / 100 * BOOK_BN * 1000     # $m
    d50, d90 = max(dstock[0], 0), max(dstock[1], 0)
    lend[sc] = dict(peak_npl_p50=round(float(np.percentile(peak, 50)), 2), peak_npl_p90=round(float(np.percentile(peak, 90)), 2),
                    d_stock_p50_m=round(float(d50), 0), d_stock_p90_m=round(float(d90), 0),
                    prov_p50_m={str(l): round(float(d50 * l), 0) for l in LGDS}, prov_p90_m={str(l): round(float(d90 * l), 0) for l in LGDS},
                    extra_loans_p50=round(float(d50 / (AVG_LOAN_K / 1000))), extra_loans_p90=round(float(d90 / (AVG_LOAN_K / 1000))),
                    officers_p50=round(float(d50 / (AVG_LOAN_K / 1000) / CASES_PER_OFFICER), 1), officers_p90=round(float(d90 / (AVG_LOAN_K / 1000) / CASES_PER_OFFICER), 1))
S["lender"] = lend
S["lender_now"] = dict(npl_ratio=round(NPLNOW["peer"], 2), npl_stock_m=round(NPLNOW["peer"] / 100 * BOOK_BN * 1000, 0), npl_loans=round(NPLNOW["peer"] / 100 * BOOK_BN * 1e6 / AVG_LOAN_K))
print(json.dumps(lend, indent=1))

# ---------------- risk-based pricing by LVR band (real NPL rates by band, assumed LGD and time in default)
lv = MS["npl_by_lvr"]; mult = {sc: S["system"][sc]["2028Q4"]["p50"] / NPLNOW["system"] for sc in CASH}
base_rate = (lv["LVR < 60%"][0] * 0.4 + lv["60% ≤ LVR < 80%"][0] * 0.6)                       # approximate pooled <80% (weights are illustrative: 40/60)
price = {}
for band, (now, avg) in lv.items():
    price[band] = dict(npl_now=now, npl_avg_2022_26=avg, premium_bp={str(l): max(0.0, round((now - base_rate) / 100 * l / TIME_IN_NPL_Y * 1e4, 0)) for l in LGDS},
                       premium_bp_severe={str(l): max(0.0, round((now * mult["D. Severe"] - base_rate * mult["D. Severe"]) / 100 * l / TIME_IN_NPL_Y * 1e4, 0)) for l in LGDS})
S["pricing"] = dict(base_npl_below_80=round(base_rate, 2), bands=price, severe_multiplier=round(mult["D. Severe"], 2))
print(json.dumps(S["pricing"], indent=1))

# ---------------- sensitivity (tornado) on the central Hawkish path, NPL ratio 2028Q4, deterministic (no residual)
def central(lag=5, slope=None, const=None, k=K, hg=0.0, convex=1.0, du=0.0, cash=CASH["C. Hawkish"]):
    f = FITS["system"][lag]; c0, s0 = f["b"]; c0 = const if const is not None else c0; s0 = slope if slope is not None else s0
    b = burden_path(cash, k, hg); x = float(b.loc[IDX[IDX.get_loc(pd.Timestamp("2028-12-31")) - lag]])
    xe = min(x, S["in_sample_burden_max"]) + convex * max(x - S["in_sample_burden_max"], 0)
    return c0 + s0 * xe + GAMMA * du
base = central(); lo90, hi90 = MS["bootstrap_slope_90"]
tor = {"Lag 4 quarters (not 5)": central(lag=4), "Lag 6 quarters (not 5)": central(lag=6),
       "Slope at 5th pct of bootstrap": central(slope=lo90), "Slope at 95th pct of bootstrap": central(slope=hi90),
       "Pass-through 0.80": central(k=0.80), "Pass-through 0.95": central(k=0.95),
       "Debt-to-income keeps rising (+0.9 per quarter)": central(hg=0.9),
       "Tail is convex (slope x2 above 9.9%)": central(convex=2.0),
       "Unemployment +1.5 points": central(du=1.5)}
S["tornado"] = dict(base=round(base, 3), values={k: round(v, 3) for k, v in tor.items()})
print("tornado base", round(base, 3)); [print(f"  {k}: {v:.3f}") for k, v in tor.items()]

# ---------------- reverse stress test: what would it take for the system NPL ratio to reach 1.25% / 1.5% by 2028Q4?
c5, s5 = FITS["system"][5]["b"]; hd = hdti0; rev = {}
for target in (1.25, 1.50):
    bneed = (target - c5) / s5; disc_need = bneed / hd * 100; cash_need = cash0 + (disc_need - disc0) / K
    rev[str(target)] = dict(burden_needed=round(float(bneed), 1), cash_rate_needed=round(float(cash_need), 2),
                            unemployment_rise_needed_pts_at_C=round(float((target - base) / GAMMA), 1))
S["reverse_stress"] = rev; print(rev)

# ---------------- early-warning triggers, tested on the 2022 to 2026 sample
a = A[A.group == "All ADIs"]; pdr, npl = a.past_due_ratio, a.npl_ratio
sig = (pdr - pdr.shift(2) >= 0.10); out = (npl.shift(-2) - npl >= 0.05)
ok = pd.DataFrame({"sig": sig, "out": out})[(a.index >= START) & npl.shift(-2).notna() & pdr.shift(2).notna()]
trig = dict(n_quarters=len(ok), n_signals=int(ok.sig.sum()), signals_followed_by_npl_rise=int((ok.sig & ok.out).sum()),
            npl_rises_total=int(ok.out.sum()), npl_rises_flagged=int((ok.sig & ok.out).sum()),
            past_due_change_2q_latest=round(float(pdr.iloc[-1] - pdr.iloc[-3]), 2))
S["trigger_pastdue"] = trig; print(trig)
# ---------------- (a) AASB 9 view: stage 2 (30-89 days past due, the standard's backstop for a significant increase in credit risk) as well as stage 3
peer_a = A[A.group == "Other domestic banks"]; pr = (peer_a.past_due_ratio / peer_a.npl_ratio)[peer_a.index >= START]
S2_RATIO = float(pr.mean()); PD_LIFE = [0.20, 0.30, 0.40]
ecl = {}
for sc in CASH:
    o = res["peer"][sc]; peak = o.max(axis=1)
    for qn_, qv in (("p50", 50), ("p90", 90)):
        d3 = max((np.percentile(peak, qv) - NPLNOW["peer"]) / 100 * BOOK_BN * 1000, 0); d2 = d3 * S2_RATIO
        ecl.setdefault(sc, {})[qn_] = {"stage3_only_m": round(d3 * 0.20), "with_stage2_m": {str(pd_): round(d3 * 0.20 + d2 * pd_ * 0.20) for pd_ in PD_LIFE}}
S["ecl"] = dict(stage2_to_stage3_ratio=round(S2_RATIO, 2), ratio_range=[round(float(pr.min()), 2), round(float(pr.max()), 2)], pd_lifetime=PD_LIFE, lgd=0.20, by_scenario=ecl)
print("ECL", json.dumps(S["ecl"], indent=1))

# ---------------- (b) lenders mortgage insurance: the lender's own loss on high-LVR loans is mostly insured (ASSUMPTIONS)
LMI_SHARE, LMI_RECOVERY = [0.6, 0.8, 0.95], 0.9
lmi = {}
for band in ["80% ≤ LVR < 90%", "LVR ≥ 95%"]:
    p20 = price[band]["premium_bp"]["0.2"]
    lmi[band] = {"uninsured_bp": p20, "net_of_lmi_bp": {str(s): round(p20 * (1 - s * LMI_RECOVERY), 1) for s in LMI_SHARE}}
S["lmi"] = dict(recovery=LMI_RECOVERY, insured_share=LMI_SHARE, bands=lmi); print("LMI", lmi)

nl = a[["new_lvr_ge90_share", "new_dti_ge6_share", "new_io_share", "new_exceptions_share", "funded_le3y_share"]]
S["new_lending_standards"] = {c: dict(low_2025=round(float(nl[c]["2025"].min()), 1), latest=round(float(nl[c].iloc[-1]), 1), a_year_ago=round(float(nl[c].iloc[-5]), 1)) for c in nl.columns}
S["new_lending_assess"] = dict(var_rate=round(float(a.new_var_rate.iloc[-1]), 2), assess_rate=round(float(a.new_assess_rate.iloc[-1]), 2))
json.dump(S, open("outputs/scenario_stats.json", "w"), indent=1)

# ================= figures
COL = {"A. Hold": st.GREY, "B. Ease": st.TEAL, "C. Hawkish": st.BLUE, "D. Severe": st.ORANGE}
LS_ = {"A. Hold": "--", "B. Ease": "-", "C. Hawkish": "-", "D. Severe": "-"}
FILL = COL
# Fig 7: cash rate and burden paths
fig, axs = plt.subplots(1, 2, figsize=(10.5, 4.2))
ax = axs[0]; ch = Q.cash_rate["2021-12-31":"2026-06-30"]; ax.plot(ch.index, ch, color=st.INK2, lw=2)
for sc in CASH:
    xs = [pd.Timestamp("2026-06-30"), pd.Timestamp("2026-09-30")] + list(SC_Q[1:]); ys = [cash0, 4.60] + CASH[sc][1:]
    ax.plot(xs, ys, color=COL[sc], lw=1.8, ls=LS_[sc])
yoff = {"A. Hold": -0.0, "B. Ease": -0.1, "C. Hawkish": 0.0, "D. Severe": 0.0}
for sc in CASH: ax.text(SC_Q[-1] + pd.Timedelta(days=25), CASH[sc][-1] + yoff[sc], f"{sc[3:]} {CASH[sc][-1]:.2f}%", fontsize=8.5, va="center")
ax.set_xlim(pd.Timestamp("2021-12-31"), pd.Timestamp("2029-03-31")); ax.set_ylim(0, 6.2); ax.set_ylabel("Cash rate, %"); st.clean(ax, "y")
ax.set_title("Cash rate: four scenarios (not forecasts)", loc="left", fontsize=10.5)
ax = axs[1]; bh = Q.interest_burden["2021-12-31":"2026-06-30"]; ax.plot(bh.index, bh, color=st.INK2, lw=2)
for sc in CASH:
    b = bt[sc]["2026-06-30":"2027-12-31"]; ax.plot(b.index, b, color=COL[sc], lw=1.8, ls=LS_[sc])
ys = {sc: bt[sc]["2027-12-31"] for sc in CASH}; order = sorted(ys, key=ys.get); adj = {}; prev = -9
for sc in order: v = max(ys[sc], prev + 0.32); adj[sc] = v; prev = v
for sc in CASH: ax.text(pd.Timestamp("2028-01-25"), adj[sc], f"{sc[3:]} {ys[sc]:.1f}%", fontsize=8.5, va="center")
ax.axhline(S["in_sample_burden_max"], color=st.GREY, lw=0.8, ls=":"); ax.text(pd.Timestamp("2022-01-15"), S["in_sample_burden_max"] + 0.12, f"Previous peak {S['in_sample_burden_max']:.1f}% (2023Q4)", fontsize=8, color=st.INK2)
ax.set_xlim(pd.Timestamp("2021-12-31"), pd.Timestamp("2029-03-31")); ax.set_ylim(4, 12); ax.set_ylabel("Interest payments, % of income"); st.clean(ax, "y")
ax.set_title("Resulting interest burden of the average household", loc="left", fontsize=10.5)
fig.tight_layout(); fig.savefig("outputs/fig7_scenarios.png", dpi=200); plt.close(fig)

# Fig 8: NPL fan
fig, axs = plt.subplots(1, 2, figsize=(10.5, 4.3), sharey=True)
for ax, key, title in [(axs[0], "system", "All ADIs (APRA)"), (axs[1], "peer", "Mid-tier peer group (other domestic banks)")]:
    y = SERIES[key]; y = y[y.index >= "2021-12-31"]; ax.plot(y.index, y, color=st.INK2, lw=2)
    f = fan[(fan.series == key)]
    ids = [pd.Timestamp("2026-06-30")] + list(HOR)
    sev = f[f.scenario == "D. Severe"]; hold = f[f.scenario == "A. Hold"]
    ax.fill_between(ids, [y.iloc[-1]] + list(hold.p10), [y.iloc[-1]] + list(hold.p90), color="#e3e3e3", lw=0)
    ax.fill_between(ids, [y.iloc[-1]] + list(sev.p10), [y.iloc[-1]] + list(sev.p90), color=st.BAND2, alpha=0.8, lw=0)
    for sc in CASH:
        g = f[f.scenario == sc]; ax.plot(ids, [y.iloc[-1]] + list(g.p50), color=COL[sc], lw=1.8, ls=LS_[sc])
    ends = {sc: float(f[(f.scenario == sc)].p50.iloc[-1]) for sc in CASH}; prev = -9; adj = {}
    for sc in sorted(ends, key=ends.get): v = max(ends[sc], prev + 0.075); adj[sc] = v; prev = v
    for sc in CASH: ax.text(pd.Timestamp("2029-01-20"), adj[sc], f"{sc[3:]} {ends[sc]:.2f}%", fontsize=8.5, va="center")
    ax.axvline(pd.Timestamp("2027-09-30"), color=st.GREY, lw=0.8, ls=":")
    ax.set_xlim(pd.Timestamp("2021-12-31"), pd.Timestamp("2030-03-31")); ax.set_title(title, loc="left", fontsize=10.5); st.clean(ax, "y")
    ax.text(pd.Timestamp("2027-08-15"), 0.46, "Scenarios diverge\nafter 2027Q3", fontsize=8, color=st.INK2, ha="right")
axs[0].set_ylabel("Non-performing housing loans, % (90+ days)"); axs[0].set_ylim(0.4, 1.5)
fig.suptitle("Arrears ratio to 2028Q4: lines are medians; bands are 80% ranges for Hold (grey) and Severe (orange)", x=0.01, ha="left", fontsize=10.5)
fig.tight_layout(rect=(0, 0, 1, 0.95)); fig.savefig("outputs/fig8_npl_fan.png", dpi=200); plt.close(fig)

# Fig 9: provisions and hardship workload (hypothetical lender)
fig, axs = plt.subplots(1, 2, figsize=(10.5, 4.0)); sc_list = list(CASH); xx = np.arange(len(sc_list))
ax = axs[0]; v50 = [lend[s]["prov_p50_m"]["0.2"] for s in sc_list]; lo = [lend[s]["prov_p50_m"]["0.1"] for s in sc_list]; hi = [lend[s]["prov_p50_m"]["0.3"] for s in sc_list]
ax.bar(xx, v50, color=[FILL[s] for s in sc_list], width=0.55)
ax.errorbar(xx, v50, yerr=[np.array(v50) - np.array(lo), np.array(hi) - np.array(v50)], fmt="none", ecolor=st.INK2, capsize=4, lw=1.2)
for i, v in enumerate(v50): ax.text(i + 0.33, v, f"${v:.0f}m", fontsize=8.5, va="center")
ax.set_xticks(xx); ax.set_xticklabels([s[3:] for s in sc_list]); ax.set_ylabel("Extra provisions at the peak, $m"); st.clean(ax, "y")
ax.set_title(f"Extra provisions, ${BOOK_BN:.0f}bn book (LGD 10-30%)", loc="left", fontsize=10)
ax = axs[1]; w = 0.36; o50 = [lend[s]["officers_p50"] for s in sc_list]; o90 = [lend[s]["officers_p90"] for s in sc_list]
ax.bar(xx - w / 2, o50, width=w, color=st.BLUE); ax.bar(xx + w / 2, o90, width=w, color=st.LIGHT)
for i in range(len(sc_list)): ax.text(i - w / 2, o50[i] + 0.15, f"{o50[i]:.1f}", ha="center", fontsize=8.5); ax.text(i + w / 2, o90[i] + 0.15, f"{o90[i]:.1f}", ha="center", fontsize=8.5)
ax.set_xticks(xx); ax.set_xticklabels([s[3:] for s in sc_list]); ax.set_ylabel("Extra hardship officers"); st.clean(ax, "y")
ax.set_title("Extra hardship officers (dark: median, light: P90)", loc="left", fontsize=10)
ax.set_ylim(0, max(o90) * 1.25)
fig.tight_layout(); fig.savefig("outputs/fig9_lender_impact.png", dpi=200); plt.close(fig)

# Fig 10: risk by LVR band and the price of that risk
fig, axs = plt.subplots(1, 2, figsize=(10.5, 4.0)); bands = list(lv.keys()); xx = np.arange(len(bands)); labs = ["<60%", "60-80%", "80-90%", "95%+"]
ax = axs[0]; ax.bar(xx, [lv[b][0] for b in bands], color=[st.LIGHT, st.LIGHT, st.BLUE, st.ORANGE], width=0.55)
for i, b in enumerate(bands): ax.text(i, lv[b][0] + 0.12, f"{lv[b][0]:.1f}%", ha="center", fontsize=9)
ax.set_xticks(xx); ax.set_xticklabels(labs); ax.set_xlabel("Loan-to-value ratio (LVR) band"); ax.set_ylabel("Non-performing share of loans, %"); st.clean(ax, "y"); ax.set_ylim(0, 7)
ax.set_title("Arrears climb steeply above 80% LVR (2026Q2)", loc="left", fontsize=10)
ax = axs[1]; p20 = [price[b]["premium_bp"]["0.2"] for b in bands]; p10 = [price[b]["premium_bp"]["0.1"] for b in bands]; p30 = [price[b]["premium_bp"]["0.3"] for b in bands]
ax.bar(xx, p20, color=[st.LIGHT, st.LIGHT, st.BLUE, st.ORANGE], width=0.55)
ax.errorbar(xx, p20, yerr=[np.array(p20) - np.array(p10), np.array(p30) - np.array(p20)], fmt="none", ecolor=st.INK2, capsize=4, lw=1.2)
for i, v in enumerate(p20): ax.text(i + 0.3, v + 2, f"{v:.0f}bp", fontsize=9, va="bottom")
ax.set_xticks(xx); ax.set_xticklabels(labs); ax.set_xlabel("Loan-to-value ratio (LVR) band"); ax.set_ylabel("Extra annual credit cost vs <80% LVR, bp"); st.clean(ax, "y")
ax.set_title("Credit-cost premium vs <80% LVR, bp (LGD 20%)", loc="left", fontsize=10)
fig.tight_layout(); fig.savefig("outputs/fig10_lvr_pricing.png", dpi=200); plt.close(fig)

# Fig 11: what moves the answer
fig, ax = plt.subplots(figsize=(9.5, 4.2)); items = sorted(tor.items(), key=lambda kv: abs(kv[1] - base)); vals = [v - base for _, v in items]
ax.barh(range(len(items)), vals, color=[st.ORANGE if v > 0 else st.BLUE for v in vals], height=0.6); ax.axvline(0, color=st.INK2, lw=0.8)
for i, v in enumerate(vals): ax.text(v + (0.004 if v >= 0 else -0.004), i, ("~0" if abs(v) < 0.005 else f"{v:+.2f}"), va="center", ha="left" if v >= 0 else "right", fontsize=8.5)
ax.set_yticks(range(len(items))); ax.set_yticklabels([k for k, _ in items], fontsize=9); ax.set_xlim(-0.13, 0.17)
ax.set_xlabel(f"Change in the 2028Q4 arrears ratio, points (central Hawkish path = {base:.2f}%)"); st.clean(ax, "x")
ax.set_title("What moves the answer", loc="left", fontsize=11)
fig.tight_layout(); fig.savefig("outputs/fig11_sensitivity.png", dpi=200); plt.close(fig)
print("saved")
