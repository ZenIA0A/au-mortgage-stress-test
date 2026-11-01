"""Step 1: build tidy quarterly datasets from the raw real data (RBA A2, F5, E2; APRA property exposures; BIS house prices; OECD unemployment)."""
import pandas as pd
from common import *

# ---------- cash rate target (RBA A2): step series, monthly then quarter-end
a2 = load_rba("rba_a02_policy_changes.csv")["ARBAMPCNCRT"]
a2 = pd.to_numeric(a2, errors="coerce").dropna()
a2 = a2[a2.index >= "2009-01-01"]
months = pd.date_range("2009-01-31", "2026-10-31", freq="ME")
cash_m = a2.reindex(a2.index.union(months)).ffill().reindex(months)     # target in force at each month end
cash_m.name = "cash_rate"
cash_m.to_csv("data/cash_rate_monthly.csv")

# ---------- RBA F5 lending rates
f5 = load_rba("rba_f05_lending_rates.csv")
rates = f5[["FILRHLBVS", "FILRHLBVD", "FILRHLBVO", "FILRHL3YF", "FILRHLBVSI"]].rename(columns={
    "FILRHLBVS": "std_var_oo", "FILRHLBVD": "disc_var_oo", "FILRHLBVO": "std_io_oo", "FILRHL3YF": "fixed3y_oo", "FILRHLBVSI": "std_var_inv"})
rates = rates["2009":]
mrate = pd.concat([cash_m, rates], axis=1, sort=True)
mrate.to_csv("data/rates_monthly.csv")

# ---------- quarterly panel (index = quarter end)
qe = lambda s: s.resample("QE").last()
Q = pd.DataFrame(index=pd.date_range("2009-03-31", "2026-06-30", freq="QE"))
Q["cash_rate"] = qe(mrate.cash_rate); Q["cash_rate_avg"] = mrate.cash_rate.resample("QE").mean()
for c in ["std_var_oo", "disc_var_oo", "fixed3y_oo"]:
    Q[c] = qe(mrate[c])
e2 = load_rba("rba_e02_household_ratios.csv")
Q["housing_debt_to_income"] = e2["BHFDDIH"].reindex(Q.index); Q["household_debt_to_income"] = e2["BHFDDIT"].reindex(Q.index)
Q["household_debt_to_assets"] = e2["BHFDA"].reindex(Q.index)

def fred(path, name):
    s = pd.read_csv(path, sep=r"\s+", skiprows=1, header=None, names=["d", name], parse_dates=["d"]).set_index("d")[name]
    s.index = s.index + pd.offsets.QuarterEnd(0); return s
hp = fred("data/raw_pastes/bis_house_prices_nominal_QAUN628BIS.txt", "house_price_index")
hc = fred("data/raw_pastes/bis_household_credit_pct_gdp_QAUHAM770A.txt", "household_credit_pct_gdp")
au = pd.read_csv("data/oecd_au_unemployment_quarterly.csv", index_col=0, parse_dates=True).iloc[:, 0]; au.index = au.index + pd.offsets.QuarterEnd(0)
Q["house_price_index"] = hp.reindex(Q.index); Q["household_credit_pct_gdp"] = hc.reindex(Q.index); Q["unemployment"] = au.reindex(Q.index)

# ---------- derived burden measures
# interest-to-income ratio on the housing debt stock: housing debt/income (E2, per cent) x discounted variable rate (what most borrowers pay)
Q["interest_burden"] = Q.housing_debt_to_income * Q.disc_var_oo / 100          # per cent of annual disposable income
Q["interest_burden_std"] = Q.housing_debt_to_income * Q.std_var_oo / 100
Q.to_csv("data/macro_quarterly.csv")

# ---------- APRA: all ADIs and four sub-sectors
groups = {"All ADIs": "1", "Major banks": "4", "Other domestic banks": "5", "Foreign subsidiary banks": "6", "Mutual ADIs": "7"}
S = "Loan performance - credit outstanding | "
rows = []
for g, n in groups.items():
    b, c = read_apra_tab(f"Tab {n}b"), read_apra_tab(f"Tab {n}c")
    def find(df, label, sect=""):
        m = [x for x in df.columns if x.split(" | ")[-1] == label and sect in x]
        assert len(m) >= 1, (g, label, sect); return df[m[0]]
    tot = b["Credit outstanding | Total credit oustanding"]
    lvr = lambda lab: b[f"Term loans by loan-to-valuation ratio (LVR) | {lab}"]
    nplb = lambda lab: b[f"Non-performing term loans by LVR | {lab}"]
    d = pd.DataFrame(index=b.index)
    d["group"] = g
    d["credit_outstanding_m"] = tot
    d["npl_m"] = b[S + "Non-performing loans"]; d["past_due_30_89_m"] = b[S + "Loans 30-89 days past due"]
    d["npl_ratio"] = d.npl_m / tot * 100; d["past_due_ratio"] = d.past_due_30_89_m / tot * 100
    d["npl_new_m"] = find(b, "New non-performing loans during the quarter")
    d["npl_oo_m"] = b[S + "Owner-occupied"]; d["npl_inv_m"] = b[S + "Investment"]
    d["oo_credit_m"] = b["Credit outstanding | Owner-occupied"]; d["inv_credit_m"] = b["Credit outstanding | Investment"]
    d["npl_ratio_oo"] = d.npl_oo_m / d.oo_credit_m * 100; d["npl_ratio_inv"] = d.npl_inv_m / d.inv_credit_m * 100
    d["io_share"] = b["Credit outstanding - term loans - selected characteristics | Interest-only"] / tot * 100
    d["funded_le3y_share"] = b["Credit outstanding - term loans - selected characteristics | Funded ≤ 3 years ago"] / tot * 100
    d["investor_share"] = d.inv_credit_m / tot * 100
    termtot = sum(lvr(l) for l in ["LVR < 60%", "60% ≤ LVR < 80%", "80% ≤ LVR < 90%", "90% ≤ LVR < 95%", "LVR ≥ 95%"])
    d["lvr_ge90_share"] = (lvr("90% ≤ LVR < 95%") + lvr("LVR ≥ 95%")) / termtot * 100
    d["lvr_80_90_share"] = lvr("80% ≤ LVR < 90%") / termtot * 100
    for lab, nm in [("LVR < 60%", "lt60"), ("60% ≤ LVR < 80%", "60_80"), ("80% ≤ LVR < 90%", "80_90"), ("LVR ≥ 95%", "ge95")]:
        d[f"credit_lvr_{nm}_m"] = lvr(lab); d[f"npl_lvr_{nm}_m"] = nplb(lab)
    # new lending
    nl = find(c, "New loans funded")
    d["new_loans_m"] = nl
    d["new_dti_ge6_share"] = find(c, "Debt-to-income ≥ 6x") / nl * 100
    d["new_dti_4_6_share"] = find(c, "Debt-to-income ≥ 4x < 6x") / nl * 100
    d["new_io_share"] = find(c, "Interest-only", "Term loans funded") / nl * 100
    d["new_exceptions_share"] = find(c, "Exceptions to serviceability policy") / nl * 100
    nlt = sum(find(c, l, "Term loans by loan-to-valuation ratio (LVR)") for l in ["LVR < 60%", "60% ≤ LVR < 80%", "80% ≤ LVR < 90%", "90% ≤ LVR < 95%", "LVR ≥ 95%"])
    d["new_lvr_ge90_share"] = (find(c, "90% ≤ LVR < 95%", "Term loans by loan-to-valuation ratio (LVR)") + find(c, "LVR ≥ 95%", "Term loans by loan-to-valuation ratio (LVR)")) / nlt * 100
    d["new_var_rate"] = find(c, "Weighted average variable rate of new loans funded")
    d["new_assess_rate"] = find(c, "Weighted average assessment rate used for serviceability")
    rows.append(d)
A = pd.concat(rows); A.index.name = "quarter_end"
A.to_csv("data/apra_panel_quarterly.csv")
print(A[A.group == "All ADIs"][["npl_ratio", "past_due_ratio", "io_share", "lvr_ge90_share", "new_dti_ge6_share", "new_var_rate", "new_assess_rate"]].round(2).tail(6))
print(A.groupby("group").npl_ratio.agg(["first", "min", "max", "last"]).round(2))
print(A.isna().sum()[A.isna().sum() > 0])
