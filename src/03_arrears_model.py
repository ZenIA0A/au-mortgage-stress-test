"""Step 3: does the repayment burden predict mortgage arrears, and how well? Lead-lag evidence, rolling-origin out-of-sample test,
robustness checks and differences between lender groups. Small sample (19 post-COVID quarters), so every claim is tested out of sample."""
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from common import *
import style as st
from scipy.stats import binomtest
import matplotlib.dates as mdates

st.setup()
A = pd.read_csv("data/apra_panel_quarterly.csv", index_col=0, parse_dates=True); Q = pd.read_csv("data/macro_quarterly.csv", index_col=0, parse_dates=True)
a = A[A.group == "All ADIs"]
B, U, HP = Q.interest_burden, Q.unemployment, np.log(Q.house_price_index) * 100
START = pd.Timestamp("2021-12-31")      # after COVID payment deferrals ended; policy support distorts arrears before this
L_BASE = 5
S = {}

def ols(y, X):
    X = np.column_stack([np.ones(len(y))] + list(X)); b = np.linalg.lstsq(X, y, rcond=None)[0]; return b, y - X @ b
def hac_se(y, X, lags=4):
    Xm = np.column_stack([np.ones(len(y))] + list(X)); b = np.linalg.lstsq(Xm, y, rcond=None)[0]; e = y - Xm @ b
    XtXi = np.linalg.inv(Xm.T @ Xm); u = Xm * e[:, None]; Sg = u.T @ u
    for l in range(1, lags + 1):
        w = 1 - l / (lags + 1); G = u[l:].T @ u[:-l]; Sg += w * (G + G.T)
    return b, np.sqrt(np.diag(XtXi @ Sg @ XtXi))
rm = lambda e: float(np.sqrt(np.mean(np.square(e))))

# ---------- 1. lead-lag evidence (post-COVID sample)
npl, pdr = a.npl_ratio, a.past_due_ratio
rows = []
for k in range(0, 11):
    lv = pd.concat([npl, B.shift(k).reindex(a.index)], axis=1).dropna(); lv = lv[lv.index >= START]
    d4 = pd.concat([npl.diff(4), B.diff(4).shift(k).reindex(a.index)], axis=1).dropna(); d4 = d4[d4.index >= START]
    pl = pd.concat([pdr, B.shift(k).reindex(a.index)], axis=1).dropna(); pl = pl[pl.index >= START]
    p4 = pd.concat([pdr.diff(4), B.diff(4).shift(k).reindex(a.index)], axis=1).dropna(); p4 = p4[p4.index >= START]
    rows.append(dict(lag=k, npl_level_corr=lv.corr().iloc[0, 1], npl_change_corr=d4.corr().iloc[0, 1], npl_n=len(lv), npl_change_n=len(d4),
                     pastdue_level_corr=pl.corr().iloc[0, 1], pastdue_change_corr=p4.corr().iloc[0, 1]))
LL = pd.DataFrame(rows); LL.round(2).to_csv("outputs/leadlag_burden_arrears.csv", index=False)
print(LL.round(2).to_string(index=False))
S["best_lag_npl_level"] = int(LL.loc[LL.npl_level_corr.idxmax(), "lag"]); S["best_corr_npl_level"] = round(float(LL.npl_level_corr.max()), 2)
S["best_lag_npl_change"] = int(LL.loc[LL.npl_change_corr.idxmax(), "lag"]); S["best_corr_npl_change"] = round(float(LL.npl_change_corr.max()), 2)
S["best_lag_pd_change"] = int(LL.loc[LL.pastdue_change_corr.idxmax(), "lag"]); S["best_corr_pd_change"] = round(float(LL.pastdue_change_corr.max()), 2)
# stage migration: past-due (30-89 days) leading non-performing (90+ days)
mig = []
for k in range(0, 7):
    x = pd.concat([npl.diff(4), pdr.diff(4).shift(k)], axis=1).dropna(); x = x[x.index >= START]; mig.append((k, round(float(x.corr().iloc[0, 1]), 2), len(x)))
S["pastdue_to_npl_change_corr"] = mig

# ---------- 2. rolling-origin out-of-sample test
idx = a.index[a.index >= START]; y = npl.reindex(idx); xB = B.shift(L_BASE).reindex(idx)
def forecasts(y, xlag_full, origin_i, h, model):
    """Forecast y at position origin_i+h using only observations up to origin_i. xlag_full = burden lagged L, aligned with y (known beyond origin if L >= h)."""
    tr = slice(0, origin_i + 1); yt = y.values
    if model == "naive": return yt[origin_i]
    if model == "ar1":                                  # iterated AR(1)
        b, _ = ols(yt[1:origin_i + 1], [yt[:origin_i]]); v = yt[origin_i]
        for _ in range(h): v = b[0] + b[1] * v
        return v
    xt = xlag_full.values
    if model == "burden":
        b, _ = ols(yt[tr], [xt[tr]]); return b[0] + b[1] * xt[origin_i + h]
    if model == "burden_ecm":                           # direct: y_{t+h} on y_t and burden lag
        n = origin_i + 1 - h
        if n < 6: return np.nan
        b, _ = ols(yt[h:origin_i + 1], [yt[:n], xt[h:origin_i + 1]]); return b[0] + b[1] * yt[origin_i] + b[2] * xt[origin_i + h]
MODELS = ["naive", "ar1", "burden", "burden_ecm"]
res = []
for i in range(8, len(idx)):                      # first origin = 9th quarter in sample (2023Q4)
    for h in range(1, 6):
        if i + h >= len(idx): continue
        for m in MODELS:
            res.append(dict(origin=idx[i], h=h, model=m, pred=forecasts(y, xB, i, h, m), actual=y.values[i + h]))
OOS = pd.DataFrame(res); OOS["err"] = OOS.actual - OOS.pred; OOS.to_csv("outputs/oos_forecasts.csv", index=False)
tab = OOS.pivot_table(index="h", columns="model", values="err", aggfunc=rm)[MODELS]; tab.round(3).to_csv("outputs/oos_rmse.csv")
cnt = OOS[OOS.model == "naive"].groupby("h").size()
print("Out-of-sample RMSE (percentage points of NPL ratio)\n", tab.round(3), "\norigins", cnt.to_dict())
S["oos_rmse"] = {int(h): {m: round(float(tab.loc[h, m]), 3) for m in MODELS} for h in tab.index}; S["oos_n"] = {int(h): int(n) for h, n in cnt.items()}
S["oos_gain_h4_vs_naive_pct"] = round(float((1 - tab.loc[4, "burden"] / tab.loc[4, "naive"]) * 100), 0)

# how often did the burden model beat 'no change', forecast by forecast? (one-sided sign test)
wins = {}
for h in range(1, 6):
    a_ = OOS[(OOS.h == h) & (OOS.model == "burden")].set_index("origin").err.abs(); b_ = OOS[(OOS.h == h) & (OOS.model == "naive")].set_index("origin").err.abs()
    w = int((a_ < b_).sum()); n_ = int(len(a_)); wins[h] = dict(wins=w, n=n_, p_one_sided=round(float(binomtest(w, n_, 0.5, alternative="greater").pvalue), 3))
S["oos_wins"] = wins; print("wins vs naive", wins)

# ---------- 3. the full-sample fit, with HAC standard errors; sensitivity to the lag; robustness with unemployment and house prices
sub = pd.DataFrame({"y": npl, "x": B.shift(L_BASE), "u": U, "hp4": HP.diff(4)}).reindex(a.index); sub = sub[sub.index >= START].dropna(subset=["y", "x"])
b, se = hac_se(sub.y.values, [sub.x.values]); fitted = b[0] + b[1] * sub.x.values; r2 = 1 - ((sub.y.values - fitted) ** 2).sum() / ((sub.y.values - sub.y.mean()) ** 2).sum()
S["fit"] = dict(const=round(float(b[0]), 3), slope=round(float(b[1]), 4), slope_hac_se=round(float(se[1]), 4), r2=round(float(r2), 2), n=len(sub), resid_sd=round(float(np.std(sub.y.values - fitted, ddof=2)), 3), lag=L_BASE)
dw = float(np.sum(np.diff(sub.y.values - fitted) ** 2) / np.sum((sub.y.values - fitted) ** 2)); S["fit"]["durbin_watson"] = round(dw, 2)
print("fit:", S["fit"])
sens = []
for L in range(3, 8):
    s2 = pd.DataFrame({"y": npl, "x": B.shift(L)}).reindex(a.index); s2 = s2[s2.index >= START].dropna()
    bb, ss = hac_se(s2.y.values, [s2.x.values]); ff = bb[0] + bb[1] * s2.x.values
    sens.append(dict(lag=L, slope=bb[1], hac_se=ss[1], r2=1 - ((s2.y.values - ff) ** 2).sum() / ((s2.y.values - s2.y.mean()) ** 2).sum(), n=len(s2)))
S["lag_sensitivity"] = [{k: (round(float(v), 3) if k != "lag" and k != "n" else int(v)) for k, v in r.items()} for r in sens]
rob = {}
for name, cols in {"burden only": ["x"], "+ unemployment": ["x", "u"], "+ house price growth": ["x", "hp4"], "+ both": ["x", "u", "hp4"]}.items():
    s3 = sub.dropna(subset=cols); bb, ss = hac_se(s3.y.values, [s3[c].values for c in cols]); ff = np.column_stack([np.ones(len(s3))] + [s3[c].values for c in cols]) @ bb
    rob[name] = dict(n=len(s3), coefs={c: [round(float(bb[i + 1]), 3), round(float(ss[i + 1]), 3)] for i, c in enumerate(cols)}, r2=round(float(1 - ((s3.y.values - ff) ** 2).sum() / ((s3.y.values - s3.y.mean()) ** 2).sum()), 2))
S["robustness"] = rob; print(json.dumps(rob, indent=1))
# does the model trained BEFORE the 2025 rate cuts predict the 2025 fall in arrears? (training sample ends 2024Q4)
tr = sub[sub.index <= "2024-12-31"]; bt, _ = ols(tr.y.values, [tr.x.values]); te = sub[sub.index > "2024-12-31"]
pred = bt[0] + bt[1] * te.x.values; turn = pd.DataFrame({"actual": te.y, "predicted": pred}, index=te.index); turn.round(3).to_csv("outputs/turning_point_test.csv")
S["turning_point"] = dict(rmse_model=round(rm(te.y.values - pred), 3), rmse_naive_last_train_value=round(rm(te.y.values - tr.y.values[-1]), 3), peak_actual=quarter_label(sub.y.idxmax()), n_test=len(te))
print(turn.round(2), S["turning_point"])

# ---------- 3b. is the level relationship spurious? Two trending series can correlate by accident.
spur = {}
for nm, k in (("quarterly change", 1), ("four-quarter change", 4)):
    s5 = pd.DataFrame({"y": npl.diff(k), "x": B.diff(k).shift(L_BASE).reindex(a.index)}); s5 = s5[s5.index >= START].dropna()
    bb, ss = hac_se(s5.y.values, [s5.x.values]); ff = bb[0] + bb[1] * s5.x.values
    spur[nm] = dict(slope=round(float(bb[1]), 3), se=round(float(ss[1]), 3), r2=round(float(1 - ((s5.y.values - ff) ** 2).sum() / ((s5.y.values - s5.y.mean()) ** 2).sum()), 2), n=len(s5))
# placebo: the burden five quarters AFTER the arrears observation should not 'predict' it if the relationship is causal in time
s6 = pd.DataFrame({"y": npl, "x": B.shift(-L_BASE).reindex(a.index)}); s6 = s6[s6.index >= START].dropna()
bb, ss = hac_se(s6.y.values, [s6.x.values]); ff = bb[0] + bb[1] * s6.x.values
spur["placebo: burden 5 quarters later"] = dict(slope=round(float(bb[1]), 3), se=round(float(ss[1]), 3), r2=round(float(1 - ((s6.y.values - ff) ** 2).sum() / ((s6.y.values - s6.y.mean()) ** 2).sum()), 2), n=len(s6))
# Engle-Granger style check on the residuals of the level fit (Dickey-Fuller t-statistic, no lags)
e = sub.y.values - fitted; de = np.diff(e); bb, ss = hac_se(de, [e[:-1]], lags=0)
spur["residual_df_t"] = round(float(bb[1] / ss[1]), 2); spur["eg_crit_5pct_asymptotic"] = -3.34
S["spurious_checks"] = spur; print("spurious checks", json.dumps(spur, indent=1))

# ---------- 4. lender groups: same relationship, different sensitivity and different mix
G = {}
for g in ["Major banks", "Other domestic banks", "Foreign subsidiary banks", "Mutual ADIs"]:
    d = A[A.group == g]; s4 = pd.DataFrame({"y": d.npl_ratio, "x": B.shift(L_BASE).reindex(d.index)}); s4 = s4[s4.index >= START].dropna()
    bb, ss = hac_se(s4.y.values, [s4.x.values]); ff = bb[0] + bb[1] * s4.x.values
    G[g] = dict(slope=round(float(bb[1]), 3), se=round(float(ss[1]), 3), r2=round(float(1 - ((s4.y.values - ff) ** 2).sum() / ((s4.y.values - s4.y.mean()) ** 2).sum()), 2),
                npl_now=round(float(d.npl_ratio.iloc[-1]), 2), npl_low=round(float(d.npl_ratio[d.index >= START].min()), 2), npl_peak=round(float(d.npl_ratio[d.index >= START].max()), 2),
                io_share=round(float(d.io_share.iloc[-1]), 1), investor_share=round(float(d.investor_share.iloc[-1]), 1), lvr_ge90_share=round(float(d.lvr_ge90_share.iloc[-1]), 1) if not np.isnan(d.lvr_ge90_share.iloc[-1]) else None,
                funded_le3y_share=round(float(d.funded_le3y_share.iloc[-1]), 1), new_dti_ge6=round(float(d.new_dti_ge6_share.iloc[-1]), 1), credit_bn=round(float(d.credit_outstanding_m.iloc[-1] / 1000), 0))
S["groups"] = G; print(pd.DataFrame(G).T.to_string())

# ---------- 5. risk by loan-to-value ratio (real: non-performing term loans / term loans in each LVR band, all ADIs, latest quarter and 2022 to 2026 average)
rr = {}
for nm, lab in [("lt60", "LVR < 60%"), ("60_80", "60% ≤ LVR < 80%"), ("80_90", "80% ≤ LVR < 90%")]:
    cr, npb = a[f"credit_lvr_{nm}_m"], a[f"npl_lvr_{nm}_m"]; rr[lab] = [float(npb.iloc[-1] / cr.iloc[-1] * 100), float((npb / cr * 100)[a.index >= START].mean())]
cr95 = a["credit_lvr_ge95_m"]; np95 = a["npl_lvr_ge95_m"]; rr["LVR ≥ 95%"] = [float(np95.iloc[-1] / cr95.iloc[-1] * 100), float((np95 / cr95 * 100)[a.index >= START].mean())]
S["npl_by_lvr"] = {k: [round(v[0], 2), round(v[1], 2)] for k, v in rr.items()}; print(S["npl_by_lvr"])
json.dump(S, open("outputs/model_stats.json", "w"), indent=1, default=float)

# ---------- parameters for the scenario engine: block-bootstrap the fit
rng = np.random.default_rng(7); resid = sub.y.values - fitted; n = len(sub); draws = []
for _ in range(4000):
    blocks = [rng.integers(0, n - 3) for _ in range(int(np.ceil(n / 4)))]; e = np.concatenate([resid[s:s + 4] for s in blocks])[:n]
    yb = fitted + e; bb, _ = ols(yb, [sub.x.values]); draws.append([bb[0], bb[1], np.std(yb - (bb[0] + bb[1] * sub.x.values), ddof=2)])
pd.DataFrame(draws, columns=["const", "slope", "sigma"]).to_csv("outputs/param_draws.csv", index=False)
S["bootstrap_slope_90"] = [round(float(np.quantile([d[1] for d in draws], q)), 4) for q in (0.05, 0.95)]
json.dump(S, open("outputs/model_stats.json", "w"), indent=1, default=float)

# ---------- figures
# Fig 4: burden vs arrears timelines (two panels, shared axis)
fig, axs = plt.subplots(2, 1, figsize=(9.5, 6.0), sharex=True)
ax = axs[0]; bb4 = B["2019":"2026"].dropna(); ax.plot(bb4.index, bb4, color=st.BLUE, lw=2.2); ax.set_ylabel("% of income")
ax.set_title("Interest payments on housing debt, % of household income", loc="left", fontsize=10.5); st.clean(ax, "y")
ax = axs[1]; ax.plot(a.index, a.npl_ratio, color=st.ORANGE, lw=2.2); ax.plot(a.index, a.past_due_ratio, color=st.GREY, lw=1.8)
ax.text(a.index[-1] + pd.Timedelta(days=20), a.npl_ratio.iloc[-1], f"Non-performing\n(90+ days) {a.npl_ratio.iloc[-1]:.2f}%", fontsize=8.5, va="center")
ax.text(a.index[-1] + pd.Timedelta(days=20), a.past_due_ratio.iloc[-1] - 0.04, f"30-89 days past due {a.past_due_ratio.iloc[-1]:.2f}%", fontsize=8.5, va="center")
ax.set_ylim(0, 1.3); ax.set_ylabel("% of housing loans"); ax.set_xlim(pd.Timestamp("2019-01-01"), pd.Timestamp("2027-12-31")); st.clean(ax, "y")
ax.set_title("Mortgage arrears, all authorised deposit-taking institutions (APRA)", loc="left", fontsize=10.5)
for axx in axs: axx.axvspan(pd.Timestamp("2022-05-01"), pd.Timestamp("2023-11-30"), color=st.SHADE, zorder=0)
axs[1].text(pd.Timestamp("2022-06-01"), 1.22, "2022-23 hikes", fontsize=8, color=st.INK2)
fig.tight_layout(); fig.savefig("outputs/fig4_burden_vs_arrears.png", dpi=200); plt.close(fig)

# Fig 5: lead-lag
fig, ax = plt.subplots(figsize=(9.5, 3.8)); w = 0.38
ax.bar(LL.lag - w / 2, LL.npl_level_corr, width=w, color=st.BLUE, label="Non-performing loans (90+ days)")
ax.bar(LL.lag + w / 2, LL.pastdue_level_corr, width=w, color=st.GREY, label="30-89 days past due")
ax.axhline(0, color=st.INK2, lw=0.8); ax.set_xticks(LL.lag); ax.set_ylim(-0.2, 1.18); ax.set_xlabel("Burden lagged by this many quarters"); ax.set_ylabel("Correlation")
ax.legend(frameon=False, fontsize=8.5, loc="upper left", ncol=2); st.clean(ax, "y")
ax.set_title("Arrears follow the interest burden with a lag of about five quarters (90+ days)", loc="left", fontsize=11)
fig.tight_layout(); fig.savefig("outputs/fig5_leadlag.png", dpi=200); plt.close(fig)

# Fig 6: out-of-sample test
fig, axs = plt.subplots(1, 2, figsize=(10.5, 4.0), gridspec_kw=dict(width_ratios=[1.1, 1]))
ax = axs[0]; cols = {"naive": st.GREY, "ar1": st.LIGHT, "burden": st.BLUE, "burden_ecm": st.ORANGE}
nm = {"naive": "Last value", "ar1": "AR(1)", "burden": "Burden model", "burden_ecm": "Burden + last value"}
for m in MODELS:
    ax.plot(tab.index, tab[m], color=cols[m], lw=2.4 if m == "burden" else 1.7, marker="o", ms=4)
    ax.text(5.12, tab.loc[5, m], nm[m], fontsize=8.5, va="center")
ax.set_xlim(0.8, 7.3); ax.set_xticks(range(1, 6)); ax.set_ylim(0, None); ax.set_xlabel("Quarters ahead"); ax.set_ylabel("Forecast error (RMSE), points"); st.clean(ax, "y")
ax.set_title("Out-of-sample error of the NPL ratio forecast", loc="left", fontsize=10.5)
ax = axs[1]; ax.plot(sub.index, sub.y, color=st.INK2, lw=2); ax.plot(turn.index, turn.predicted, color=st.ORANGE, lw=2.2, ls="--")
ax.axvline(pd.Timestamp("2024-12-31"), color=st.GREY, lw=0.8, ls=":")
ax.text(turn.index[2], turn.predicted.iloc[2] + 0.07, "Predicted (model fitted\nonly to data to 2024Q4)", fontsize=8.5); ax.text(sub.index[1], 0.7, "Actual", fontsize=8.5)
ax.xaxis.set_major_locator(mdates.YearLocator()); ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y")); ax.set_ylim(0.55, 1.3); ax.set_ylabel("NPL ratio, %"); st.clean(ax, "y"); ax.set_title("Did it see the fall after the 2025 rate cuts?", loc="left", fontsize=10.5)
fig.tight_layout(); fig.savefig("outputs/fig6_out_of_sample.png", dpi=200); plt.close(fig)
