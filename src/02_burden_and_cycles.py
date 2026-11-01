"""Step 2: how much heavier is the repayment burden? Pass-through of the cash rate, interest burden, and the 2022-23 vs 2026 cycles."""
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from common import *
import style as st

st.setup()
M = pd.read_csv("data/rates_monthly.csv", index_col=0, parse_dates=True)
Q = pd.read_csv("data/macro_quarterly.csv", index_col=0, parse_dates=True)
S = {}

# ---------- 1. pass-through: monthly change in mortgage rate on current and lagged changes in the cash rate (2010 onward)
def passthrough(col, lags=4):
    d = M[["cash_rate", col]].loc["2010":].dropna().diff().dropna()
    X = np.column_stack([np.ones(len(d))] + [d.cash_rate.shift(k).fillna(0).values for k in range(lags)])
    b, *_ = np.linalg.lstsq(X, d[col].values, rcond=None)
    res = d[col].values - X @ b; n, p = X.shape
    cov = np.linalg.inv(X.T @ X) * (res @ res) / (n - p)
    cum = b[1:].sum(); se = np.sqrt(np.ones(lags) @ cov[1:, 1:] @ np.ones(lags))
    return dict(coef=[round(float(x), 2) for x in b[1:]], cumulative=round(float(cum), 2), se=round(float(se), 2), n=int(n))
S["passthrough_disc"] = passthrough("disc_var_oo"); S["passthrough_std"] = passthrough("std_var_oo")
print("pass-through discounted:", S["passthrough_disc"], "\nstandard:", S["passthrough_std"])
# spread of the discounted rate over the cash rate
sp = (M.disc_var_oo - M.cash_rate).loc[:"2026-08"].dropna()
S["spread_disc_latest"] = round(float(sp.iloc[-1]), 2); S["spread_disc_2019"] = round(float(sp["2019"].mean()), 2); S["spread_disc_2023_2025"] = round(float(sp["2023-06":"2025-06"].mean()), 2)

# ---------- 2. burden across the two cycles
b = Q.interest_burden.dropna()
S["burden_trough"] = [quarter_label(b["2020":].idxmin()), round(float(b["2020":].min()), 2)]
S["burden_peak"] = [quarter_label(b.idxmax()), round(float(b.max()), 2)]
S["burden_low_2025"] = [quarter_label(b["2024-12":].idxmin()), round(float(b["2024-12":].min()), 2)]
S["burden_latest"] = [quarter_label(b.index[-1]), round(float(b.iloc[-1]), 2)]
S["burden_2019q1"] = round(float(b.loc["2019-03-31"]), 2)
S["burden_2011q1"] = round(float(b.loc["2011-03-31"]), 2)
hdti = float(Q.housing_debt_to_income.dropna().iloc[-1])
S["hdti_latest"] = round(hdti, 1)
# effect of the 30 Sep 2026 hike (+25bp, F5 data stop before it): assume full pass-through
S["burden_after_sep26"] = round(S["burden_latest"][1] + 0.25 * S["passthrough_disc"]["cumulative"] * hdti / 100, 2)
S["cash_peak_2023"] = float(Q.cash_rate["2022":].max()); S["cash_trough"] = float(Q.cash_rate["2020":].min()); S["cash_now"] = 4.60; S["cash_low_2025"] = float(Q.cash_rate["2025"].min())

# ---------- 3. what it means for a $600,000 30-year principal-and-interest loan (illustrative borrower, real rates)
def pmt(r, loan=600000, years=30):
    i = r / 100 / 12; n = years * 12; return loan * i / (1 - (1 + i) ** -n)
pts = {"Dec 2021 (cash rate 0.10%)": Q.disc_var_oo.loc["2021-12-31"], "Dec 2023 (4.35%)": Q.disc_var_oo.loc["2023-12-31"],
       "Sep 2025 (3.60%)": Q.disc_var_oo.loc["2025-09-30"], "Jun 2026 (4.35%)": Q.disc_var_oo.loc["2026-06-30"]}
pts["After 30 Sep 2026 hike (4.60%)"] = Q.disc_var_oo.loc["2026-06-30"] + 0.25 * S["passthrough_disc"]["cumulative"]
pay = {k: round(pmt(v), 0) for k, v in pts.items()}; S["payment_600k"] = pay; S["rate_points"] = {k: round(float(v), 2) for k, v in pts.items()}
print(json.dumps(S, indent=1))
json.dump(S, open("outputs/burden_stats.json", "w"), indent=1)

# ---------- figures
# Fig 1: cash rate and mortgage rates
fig, ax = plt.subplots(figsize=(9.5, 4.4))
r = M.loc["2019":]
ax.step(r.index, r.cash_rate, where="post", color=st.INK2, lw=1.8)
ax.plot(r.index, r.disc_var_oo, color=st.BLUE, lw=2.2); ax.plot(r.index, r.std_var_oo, color=st.LIGHT, lw=1.8); ax.plot(r.index, r.fixed3y_oo, color=st.GREY, lw=1.6, ls="--")
x1 = r.index[-1] + pd.Timedelta(days=25)
ax.text(x1, r.std_var_oo.dropna().iloc[-1], f"Standard variable {r.std_var_oo.dropna().iloc[-1]:.2f}%", fontsize=8.5, va="center")
ax.text(x1, r.fixed3y_oo.dropna().iloc[-1] + 0.2, f"3-year fixed {r.fixed3y_oo.dropna().iloc[-1]:.2f}%", fontsize=8.5, va="center")
ax.text(x1, r.disc_var_oo.dropna().iloc[-1] - 0.25, f"Discounted variable {r.disc_var_oo.dropna().iloc[-1]:.2f}%", fontsize=8.5, va="center")
ax.text(x1, 4.6, "Cash rate 4.60%\n(after 30 Sep hike)", fontsize=8.5, va="center", color=st.INK2)
ax.set_xlim(pd.Timestamp("2019-01-01"), pd.Timestamp("2028-01-01")); ax.set_ylim(0, 10); ax.set_ylabel("Per cent a year"); st.clean(ax, "y")
ax.set_title("Mortgage rates moved one for one with the cash rate: four hikes in 2026 so far", loc="left", fontsize=11)
fig.tight_layout(); fig.savefig("outputs/fig1_rates.png", dpi=200); plt.close(fig)

# Fig 2: interest burden
fig, ax = plt.subplots(figsize=(9.5, 4.4)); bb = b["2009":]
ax.plot(bb.index, bb, color=st.BLUE, lw=2.2)
ax.scatter([pd.Timestamp("2026-09-30")], [S["burden_after_sep26"]], color=st.ORANGE, zorder=5, s=36)
ax.annotate(f"After the 30 Sep hike\n~{S['burden_after_sep26']:.1f}% (estimate)", (pd.Timestamp("2026-09-30"), S["burden_after_sep26"]), (pd.Timestamp("2022-09-30"), 11.2), fontsize=8.5, arrowprops=dict(arrowstyle="-", color=st.GREY, lw=0.8))
pk = b.idxmax(); ax.annotate(f"Peak {b.max():.1f}%\n({quarter_label(pk)})", (pk, b.max()), (pd.Timestamp("2018-06-30"), 10.4), fontsize=8.5, arrowprops=dict(arrowstyle="-", color=st.GREY, lw=0.8))
lo = b["2020":].idxmin(); ax.annotate(f"Low {b['2020':].min():.1f}%\n({quarter_label(lo)})", (lo, b["2020":].min()), (pd.Timestamp("2019-06-30"), 3.2), fontsize=8.5, arrowprops=dict(arrowstyle="-", color=st.GREY, lw=0.8))
ax.set_ylim(2.5, 12); ax.set_xlim(pd.Timestamp("2009-01-01"), pd.Timestamp("2027-01-01")); ax.set_ylabel("Interest payments, % of annual household income"); st.clean(ax, "y")
ax.set_title("Interest burden on housing debt: back near the 2023 to 2024 peak", loc="left", fontsize=11)
fig.tight_layout(); fig.savefig("outputs/fig2_burden.png", dpi=200); plt.close(fig)

# Fig 3: monthly repayment on $600k loan
fig, ax = plt.subplots(figsize=(9.5, 3.8)); names = list(pay); vals = list(pay.values())
ax.bar(range(len(vals)), vals, color=[st.GREY, st.BLUE, st.GREY, st.BLUE, st.ORANGE], width=0.6)
for i, v in enumerate(vals): ax.text(i, v + 70, f"${v:,.0f}\n({list(S['rate_points'].values())[i]:.2f}%)", ha="center", fontsize=8.5)
ax.set_xticks(range(len(vals))); ax.set_xticklabels([n.replace(" (", "\n(") for n in names], fontsize=8.5); ax.set_ylim(0, max(vals) * 1.22)
ax.set_ylabel("Monthly repayment, $"); st.clean(ax, "y")
ax.set_title("Monthly repayment on a $600,000, 30-year loan at the discounted variable rate", loc="left", fontsize=11)
fig.tight_layout(); fig.savefig("outputs/fig3_repayment.png", dpi=200); plt.close(fig)
