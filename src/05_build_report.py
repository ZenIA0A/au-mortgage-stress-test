"""Step 5: build the decision report (docx) from the saved results, so every number in the text comes from the analysis outputs."""
import json
import pandas as pd
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BS = json.load(open("outputs/burden_stats.json")); MS = json.load(open("outputs/model_stats.json")); SS = json.load(open("outputs/scenario_stats.json"))
FAN = pd.read_csv("outputs/scenario_npl_fan.csv"); A = pd.read_csv("data/apra_panel_quarterly.csv", index_col=0, parse_dates=True)
sysA = A[A.group == "All ADIs"]
SC = ["A. Hold", "B. Ease", "C. Hawkish", "D. Severe"]
CASH_END = {"A. Hold": 4.60, "B. Ease": 4.10, "C. Hawkish": 5.10, "D. Severe": 5.60}
f1 = lambda x: f"{x:.1f}"; f2 = lambda x: f"{x:.2f}"
def fan(series, sc, q, k="p50"): return float(FAN[(FAN.series == series) & (FAN.scenario == sc) & (FAN.quarter == q)][k].iloc[0])
def rng80(series, sc, q): return f"{f2(fan(series, sc, q, 'p10'))} to {f2(fan(series, sc, q, 'p90'))}"

doc = Document()
sec = doc.sections[0]; sec.page_width, sec.page_height = Cm(21), Cm(29.7)
sec.left_margin = sec.right_margin = Cm(2.2); sec.top_margin = Cm(2.0); sec.bottom_margin = Cm(2.0)
st = doc.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(10.5); st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
st.paragraph_format.space_after = Pt(6); st.paragraph_format.line_spacing = 1.12
for name, size in (("Heading 1", 15), ("Heading 2", 12)):
    h = doc.styles[name]; h.font.name = "Calibri"; h.font.size = Pt(size); h.font.bold = True; h.font.color.rgb = RGBColor(0, 0, 0)
    h.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri"); h.paragraph_format.space_before = Pt(14 if size == 15 else 10); h.paragraph_format.space_after = Pt(5); h.paragraph_format.keep_with_next = True

# footer with page numbers
def add_field(run, instr):
    for t, txt in (("begin", None), (None, instr), ("end", None)):
        if t:
            el = OxmlElement("w:fldChar"); el.set(qn("w:fldCharType"), t); run._r.append(el)
        else:
            el = OxmlElement("w:instrText"); el.set(qn("xml:space"), "preserve"); el.text = txt; run._r.append(el)
fp = sec.footer.paragraphs[0]; fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = fp.add_run("Australian mortgage stress test  |  page "); r.font.size = Pt(8.5); r2 = fp.add_run(); r2.font.size = Pt(8.5); add_field(r2, "PAGE")

def P(text, bold=False, italic=False, size=None, color=None, after=None, align=None):
    p = doc.add_paragraph(); r = p.add_run(text); r.bold = bold; r.italic = italic
    if size: r.font.size = Pt(size)
    r.font.color.rgb = RGBColor(0, 0, 0)
    if after is not None: p.paragraph_format.space_after = Pt(after)
    if align: p.alignment = align
    return p
def RICH(parts):
    p = doc.add_paragraph()
    for t, b in parts:
        r = p.add_run(t); r.bold = b
    return p
def B(text, lead=None):
    p = doc.add_paragraph(style="List Bullet"); p.paragraph_format.space_after = Pt(3)
    if lead: p.add_run(lead).bold = True
    p.add_run(text); return p
def FIG(path, caption, width=16.4):
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.keep_with_next = True; p.paragraph_format.space_after = Pt(2)
    p.add_run().add_picture(path, width=Cm(width))
    P(caption, italic=True, size=9, color=(80, 80, 80), after=10)
def shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr(); sh = OxmlElement("w:shd"); sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), fill); tcPr.append(sh)
def TABLE(header, rows, widths, align_right_from=1, bold_first_col=False, size=9):
    t = doc.add_table(rows=1, cols=len(header)); t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER; t.autofit = False
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]; c.text = ""; r = c.paragraphs[0].add_run(h); r.bold = True; r.font.size = Pt(size); shade(c, "E8E8E8")
        c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT if i >= align_right_from else WD_ALIGN_PARAGRAPH.LEFT
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""; r = cells[i].paragraphs[0].add_run(str(v)); r.font.size = Pt(size); r.bold = bold_first_col and i == 0
            cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT if i >= align_right_from else WD_ALIGN_PARAGRAPH.LEFT
    for ri, row in enumerate(t.rows):
        trPr = row._tr.get_or_add_trPr(); trPr.append(OxmlElement("w:cantSplit"))
        for i, w in enumerate(widths): row.cells[i].width = Cm(w)
        if ri < len(t.rows) - 1:
            for c in row.cells:
                for p in c.paragraphs: p.paragraph_format.keep_with_next = True
        for c in row.cells:
            for p in c.paragraphs: p.paragraph_format.space_after = Pt(1); p.paragraph_format.space_before = Pt(1)
    for i, w in enumerate(widths): t.columns[i].width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    return t

ecl, lmi = SS["ecl"], SS["lmi"]; wins, spur = MS["oos_wins"], MS["spurious_checks"]
lend, asm, prc, tor, rev, trg = SS["lender"], SS["assumptions"], SS["pricing"], SS["tornado"], SS["reverse_stress"], SS["trigger_pastdue"]
nl, fit, oos, tp = SS["new_lending_standards"], MS["fit"], MS["oos_rmse"], MS["turning_point"]
npl_now, pd_now = float(sysA.npl_ratio.iloc[-1]), float(sysA.past_due_ratio.iloc[-1]); npl_low = float(sysA.npl_ratio["2022":].min()); npl_peak = float(sysA.npl_ratio["2024":].max())
hold = FAN[(FAN.series == "system") & (FAN.scenario == "A. Hold")]; dip_q = hold.loc[hold.p50.idxmin(), "quarter"]; dip_v = hold.p50.min()
hawk_dip = FAN[(FAN.series == "system") & (FAN.scenario == "C. Hawkish")].p50.min()

# ======================================================= title
P("Australian mortgage stress test", bold=True, size=22, after=2)
P("The 2026 RBA hiking cycle, and what a mid-tier lender should do about it", size=13, after=2)
P("Thai Anh Lai  |  November 2026", size=9.5, after=4)
P("Decision paper for the Head of Credit Risk. Real RBA and APRA data to the June 2026 quarter, plus the 30 September 2026 cash-rate decision. "
  "The lender is hypothetical: its size and cost parameters are assumptions, labelled as such. Everything about the market is real.", italic=True, size=9.5, color=(80, 80, 80), after=10)

doc.add_heading("The short answer", 1)
RICH([("What is going on. ", True), (f"The RBA has raised the cash rate four times in 2026, from {BS['cash_low_2025']:.2f}% to {BS['cash_now']:.2f}% on 30 September. Lenders passed on about {BS['passthrough_disc']['cumulative']*100:.0f}% of each move to discounted variable rates, most of it in the first month. "
      f"The average household now spends about {BS['burden_after_sep26']:.1f}% of its income on interest, up from {BS['burden_low_2025'][1]:.1f}% in {BS['burden_low_2025'][0]} and close to the {BS['burden_peak'][1]:.1f}% peak of {BS['burden_peak'][0]}. "
      f"Arrears are still calm: {npl_now:.2f}% of housing loans are 90+ days past due (low {npl_low:.2f}% in 2022, peak {npl_peak:.2f}% in 2025), and {pd_now:.2f}% are 30 to 89 days past due.", False)])
RICH([("What the data say about timing. ", True), (f"Across the 19 quarters since COVID support ended, arrears follow the interest burden with a lag of about five quarters (correlation {MS['best_corr_npl_level']:.2f}). "
      f"Out of sample, the model was {MS['oos_gain_h4_vs_naive_pct']:.0f}% more accurate than a no-change forecast four quarters ahead and beat it in {wins['4']['wins']} of {wins['4']['n']} such forecasts (sign test p = {wins['4']['p_one_sided']:.3f}); but those {wins['4']['n']} forecasts overlap in time and come from one cycle, so this is encouraging, not conclusive. Two things follow. First, the 2026 hikes will not show up in arrears until late 2027. "
      f"Second, the burden fell during 2025, so arrears are expected to ease first: the system ratio dips to about {dip_v:.2f}% around {dip_q} before the hikes start to bite.", False)])
RICH([("How big can it get. ", True), (f"System arrears reach {f2(fan('system','A. Hold','2028Q4'))}% by end-2028 if the cash rate holds at 4.60%, {f2(fan('system','C. Hawkish','2028Q4'))}% if it rises to 5.10%, and {f2(fan('system','D. Severe','2028Q4'))}% in a severe case (5.60% plus unemployment rising to 6%). "
      f"For comparison the 2022-23 hikes lifted the ratio by about 0.4 points. The reason this cycle looks milder is arithmetic: the burden jumped by 5 points in 2022-23, while the remaining scenarios add 0.3 to 1.5 points.", False)])
RICH([("What it means for a mid-tier lender ", True), (f"(hypothetical, ${asm['book_bn']:.0f}bn mortgage book, mix like APRA's other domestic banks). Extra provisions at the peak are ${lend['A. Hold']['prov_p50_m']['0.2']:.0f}m in Hold and ${lend['D. Severe']['prov_p50_m']['0.2']:.0f}m in Severe at a 20% loss given default; "
      f"extra hardship staffing is {lend['A. Hold']['officers_p50']:.0f} officers in Hold and {lend['D. Severe']['officers_p90']:.0f} in the Severe 90th percentile. Counting loans 30 to 89 days past due as stage 2 under AASB 9 adds only about 15% to 20%. These are small numbers. The question is therefore not 'how much do we provision' but 'where is the risk concentrated and are we paid for it'.", False)])
RICH([("An independent check points the same way. ", True), ("The RBA's October 2026 Financial Stability Review, which uses loan-level data this paper does not have, estimates that about 2% of variable-rate owner-occupier borrowers have a cash-flow shortfall, that the median borrower holds more than a year of repayments in offset and redraw balances, and that in a very adverse scenario (unemployment 6.3%, cash rate 5.6%) about 5% of mortgagors would be at higher risk of default, only a little above the 2023 peak. A modest rise, driven by the labour market rather than rates, is also what this model says.", False)])
doc.add_heading("Recommendation", 2)
B(" Do not tighten the whole book. The model gives no support for a blunt response, and the roughly 83% of housing credit with LVR below 80% is not where the arrears are (0.6% to 0.8% non-performing against 2.0% at 80-90% LVR and 5.9% at 95%+).", "1. No across-the-board tightening.")
B(f" New lending has loosened while rates rose: exceptions to policy {nl['new_exceptions_share']['a_year_ago']:.1f}% to {nl['new_exceptions_share']['latest']:.1f}% of approvals, loans at 90%+ LVR {nl['new_lvr_ge90_share']['a_year_ago']:.1f}% to {nl['new_lvr_ge90_share']['latest']:.1f}%, interest-only {nl['new_io_share']['a_year_ago']:.1f}% to {nl['new_io_share']['latest']:.1f}% (all ADIs, past year). "
  "Set our own exceptions cap at the 2025 low and stop the drift.", "2. Hold standards where they were a year ago.")
B(f" Before insurance, a loan at 80-90% LVR costs about {prc['bands']['80% ≤ LVR < 90%']['premium_bp']['0.2']:.0f}bp a year more in expected credit cost than one below 80%, and 95%+ about {prc['bands']['LVR ≥ 95%']['premium_bp']['0.2']:.0f}bp. Most high-LVR loans carry lenders mortgage insurance or a government guarantee, which leaves the lender with roughly {lmi['bands']['80% ≤ LVR < 90%']['net_of_lmi_bp']['0.8']:.0f}bp and {lmi['bands']['LVR ≥ 95%']['net_of_lmi_bp']['0.8']:.0f}bp (assumed 80% insured, 90% recovered). So the premium belongs on the uninsured part: LMI waivers and other low-deposit loans where the lender keeps the loss.", "3. Price the uninsured high-LVR segment.")
B(f" Fund {lend['A. Hold']['officers_p90']:.0f} additional hardship officers for 2027 and pre-approve a further {lend['D. Severe']['officers_p90']-lend['A. Hold']['officers_p90']:.0f} that release on the triggers in section 8. The demand arrives from late 2027, so training can start in early 2027.", "4. Staff hardship ahead of the curve.")
B(" Review the model every quarter against the next APRA release; the first real test of the five-quarter lag is the 2027 dip.", "5. Treat the model as a hypothesis under test.")

# ======================================================= 1 data
doc.add_heading("1. Data, and what is real and what is assumed", 1)
P("All market inputs are published statistics. The only invented items are the lender's characteristics, listed in the second table. Nothing in the analysis is simulated except the Monte Carlo draws around the fitted model.")
TABLE(["Input", "Source", "Used for"], [
    ["Cash rate decisions, monthly", "RBA table A2; Sep 2026 decision from RBA announcement coverage", "Scenario starting point"],
    ["Housing debt to household income; household interest payments", "RBA table E2 (household finances)", "Interest burden"],
    ["Discounted and standard variable owner-occupier rates, fixed rates", "RBA table F5 (indicator lending rates)", "Pass-through, burden"],
    ["Mortgage arrears by lender type, by LVR band; new lending standards", "APRA quarterly authorised deposit-taking institution property exposures, June 2026", "Arrears model, risk by LVR, drift in standards"],
    ["House prices; household credit to GDP", "BIS via FRED", "Robustness checks"],
    ["Australian unemployment rate", "OECD via FRED", "Robustness and severe overlay"],
], [6.0, 6.5, 3.9], align_right_from=9)
TABLE(["Assumed (hypothetical lender)", "Value", "Why / sensitivity"], [
    ["Residential mortgage book", f"${asm['book_bn']:.0f}bn", "About 13% of the other-domestic-bank group ($455bn). Results scale linearly."],
    ["Behaves like", "APRA 'Other domestic banks'", "Real group data: arrears 0.77%, similar slope to the system."],
    ["Average loan", f"${asm['avg_loan_k']:.0f}k", "Converts dollars of arrears into numbers of customers."],
    ["Loss given default", "20% (10% to 30%)", "Not in APRA data. Shown as ranges everywhere."],
    ["Time a loan spends 90+ days past due", f"{asm['time_in_npl_years']} years", "Turns a stock of arrears into an annual cost for pricing."],
    ["Cases per hardship officer", f"{asm['cases_per_officer']}", "Operational assumption; replace with own data."],
], [6.0, 4.0, 6.4], align_right_from=9)

# ======================================================= 2 burden
doc.add_heading("2. The 2026 hikes and what they do to household budgets", 1)
P(f"The RBA raised the cash rate in February, March, May and September 2026, taking it from {BS['cash_low_2025']:.2f}% to {BS['cash_now']:.2f}%. Regressing monthly changes in the discounted variable owner-occupier rate on current and lagged changes in the cash rate "
  f"(200 months) gives a pass-through of {BS['passthrough_disc']['cumulative']:.2f} (standard error {BS['passthrough_disc']['se']:.2f}), almost all of it in the first month. For standard variable rates it is {BS['passthrough_std']['cumulative']:.2f}. Pass-through is not the uncertain part.")
FIG("outputs/fig1_rates.png", "Figure 1. Cash rate and mortgage rates. Real data, RBA tables A2 and F5.")
P(f"The interest burden is housing debt to income ({BS['hdti_latest']:.0f}% in 2026Q2) multiplied by the discounted variable rate. It rose from {BS['burden_trough'][1]:.1f}% in {BS['burden_trough'][0]} to {BS['burden_peak'][1]:.1f}% in {BS['burden_peak'][0]}, "
  f"fell to {BS['burden_low_2025'][1]:.1f}% after the 2025 cuts, and is {BS['burden_latest'][1]:.1f}% in 2026Q2, about {BS['burden_after_sep26']:.1f}% after the September increase. It is an average over all households with housing debt: it ignores fixed-rate loans and offset balances, which dampen the burden for some households, and it hides the distribution, which is where the stress shows.")
FIG("outputs/fig2_burden.png", "Figure 2. Interest payments on housing debt as a share of household income. The orange point is an estimate for the September 2026 hike (RBA E2 data stop at June).")
pm = BS["payment_600k"]; ks = list(pm.keys())
P(f"In dollars, a $600,000, 30-year loan at the discounted variable rate costs ${pm[ks[0]]:,.0f} a month at the 2021 low, ${pm[ks[1]]:,.0f} at the 2023 peak, ${pm[ks[2]]:,.0f} in September 2025 and about ${pm[ks[4]]:,.0f} now.")
FIG("outputs/fig3_repayment.png", "Figure 3. Monthly repayment on a $600,000, 30-year loan (calculated from RBA rates).", 15.0)

# ======================================================= 3 arrears model
doc.add_heading("3. How arrears respond to the burden", 1)
P("Mortgage stress is a cash-flow problem first and a credit problem later. Borrowers first absorb higher payments from savings and offset balances, then fall behind, and only after 90 days does a loan count as non-performing. The data show this waterfall. "
  f"The change in the 30 to 89 day past-due ratio leads the change in the 90+ day ratio by two quarters (correlation {MS['pastdue_to_npl_change_corr'][2][1]:.2f}). The interest burden leads the 90+ day ratio by about five quarters.")
FIG("outputs/fig4_burden_vs_arrears.png", "Figure 4. Interest burden and mortgage arrears, all authorised deposit-taking institutions. Real data (RBA E2, F5; APRA).")
FIG("outputs/fig5_leadlag.png", "Figure 5. Correlation between the 90+ day arrears ratio and the burden lagged by 0 to 10 quarters (2021Q4 to 2026Q2). The 30-89 day ratio peaks sooner.")
P(f"The fitted relationship is simple: arrears ratio = {fit['const']:.2f} + {fit['slope']:.3f} x (burden five quarters earlier), so one more point of income going to interest raises the system arrears ratio by about 6 basis points after five quarters. "
  f"The slope is {fit['slope']:.3f} with a standard error of {fit['slope_hac_se']:.3f} (Newey-West), {fit['r2']:.2f} of the variation explained, on {fit['n']} quarters. The lag is not pinned down exactly:")
TABLE(["Lag (quarters)", "Slope", "Std error", "R squared", "Quarters"],
      [[x["lag"], f"{x['slope']:.3f}", f"{x['hac_se']:.3f}", f"{x['r2']:.2f}", x["n"]] for x in MS["lag_sensitivity"]], [3.2, 3, 3, 3, 3])
P("Lags of four to six quarters fit about equally well, so the scenario engine draws the lag from four, five and six rather than fixing it.")

# ======================================================= 4 validation
doc.add_heading("4. Does it work? Validation and limits", 1)
P("Nineteen quarters is a short sample and one cycle. A model that fits in-sample proves little, so the test that matters is out of sample: at each origin from 2023Q4 the model is re-estimated using only data available then and asked for the arrears ratio one to five quarters ahead.")
rows = []
for h in ["1", "2", "3", "4", "5"]:
    o = oos[h]; rows.append([h, MS["oos_n"][h], f2(o["naive"]), f2(o["ar1"]), f2(o["burden"]), f2(o["burden_ecm"])])
TABLE(["Quarters ahead", "Forecasts", "Last value", "AR(1)", "Burden model", "Burden + last value"], rows, [3.0, 2.4, 2.6, 2.4, 3.0, 3.4])
P(f"Typical error in percentage points of the arrears ratio. The burden model is the best or tied-best from two quarters out and {MS['oos_gain_h4_vs_naive_pct']:.0f}% better than assuming no change at four quarters ahead. Adding the last observed value to the model makes it worse from three quarters out, a sign of overfitting with so few observations, so the simpler model is the one used.")
rows = [[h, wins[h]["n"], wins[h]["wins"], f"{wins[h]['p_one_sided']:.3f}"] for h in ["1", "2", "3", "4", "5"]]
TABLE(["Quarters ahead", "Forecasts", "Burden model closer than 'no change'", "Sign test p (one-sided)"], rows, [3.0, 2.6, 5.4, 4.0])
P(f"Counting wins, forecast by forecast, tells the same story more honestly than an average: at one quarter ahead the model is a coin flip ({wins['1']['wins']} of {wins['1']['n']}), and from three quarters out it wins nearly every time. The forecasts overlap and the sample is one cycle, so the p-values overstate the evidence; they are a check that the average is not driven by one lucky quarter.")
FIG("outputs/fig6_out_of_sample.png", "Figure 6. Left: forecast errors by horizon, rolling origin. Right: a model fitted only to data up to 2024Q4 and asked to predict the 2025-26 fall in arrears after the rate cuts.")
P(f"The harder test is the turning point. Fitted only on data to 2024Q4, the model predicted that arrears would peak and fall after the 2025 rate cuts; its error over the next {tp['n_test']} quarters was {tp['rmse_model']:.3f} points against {tp['rmse_naive_last_train_value']:.3f} for assuming no change. That is evidence for the mechanism, not proof, because there is only one turning point to test.")
R = MS["robustness"]
P(f"Robustness. Adding unemployment lifts the explained variation to {R['+ unemployment']['r2']:.2f}: each extra point of unemployment is associated with {R['+ unemployment']['coefs']['u'][0]:.3f} points more arrears, but the estimate is imprecise (standard error {R['+ unemployment']['coefs']['u'][1]:.3f}, and unemployment moved little in the sample), so it is used only in the Severe scenario and flagged as an assumption. House-price growth adds little ({R['+ house price growth']['coefs']['hp4'][0]:.3f} per point). The burden coefficient stays between {min(v['coefs']['x'][0] for v in R.values()):.3f} and {max(v['coefs']['x'][0] for v in R.values()):.3f} in all four variants.")
G = MS["groups"]; rows = [["All ADIs", f"{sysA.credit_outstanding_m.iloc[-1]/1000:,.0f}", f2(npl_now), f"{fit['slope']:.3f} ({fit['slope_hac_se']:.3f})", f"{fit['r2']:.2f}", "", ""]]
for g, v in G.items():
    rows.append([g, f"{v['credit_bn']:,.0f}", f2(v["npl_now"]), f"{v['slope']:.3f} ({v['se']:.3f})", f"{v['r2']:.2f}", f1(v["investor_share"]), f1(v["io_share"])])
TABLE(["Lender group (APRA)", "Housing credit $bn", "Arrears now, %", "Slope (std err)", "R squared", "Investor share %", "Interest-only %"], rows, [3.9, 2.2, 2.0, 2.6, 1.7, 2.0, 2.0], size=8.5)
P("Major banks, other domestic banks and mutuals show the same relationship, with slopes of 0.04 to 0.06. Foreign subsidiary banks show none (slope zero, a small and lumpy group), a reminder that a system model cannot be applied to any single lender without checking it against that lender's own history.")
doc.add_heading("Is the relationship spurious?", 2)
P("Two series that both trend over the same few years can correlate strongly by accident. Three checks:")
B(f" the relationship survives in changes, which removes shared trends: the quarterly change in arrears on the change in burden five quarters earlier has a slope of {spur['quarterly change']['slope']:.3f} (standard error {spur['quarterly change']['se']:.3f}), weaker in fit (R squared {spur['quarterly change']['r2']:.2f}) as quarterly changes are noisy. Four-quarter changes give a slope of {spur['four-quarter change']['slope']:.3f}, steeper than the level fit, so if anything the level model understates the short-run response.", "Changes, not levels:")
B(f" if the link were a coincidence of timing, the burden five quarters after each arrears reading could fit as well. It fits with the wrong sign (slope {spur['placebo: burden 5 quarters later']['slope']:.2f}), which is consistent with the direction of time in the model, though it also shows how easily trending series produce large correlations.", "Placebo:")
B(f" a Dickey-Fuller test on the residuals of the level fit gives t = {spur['residual_df_t']:.2f}, just beyond the usual 5% critical value of about {spur['eg_crit_5pct_asymptotic']:.2f}. With 19 observations the test has little power and small-sample critical values are stricter, so this is weak support, not proof, that the two series move together in the long run.", "Residuals:")
P("Verdict: the evidence is consistent with a real, lagged effect of the interest burden on arrears, and not with a pure trend coincidence, but one cycle cannot settle it. The model is used to organise decisions, with that caveat attached.", italic=True)
doc.add_heading("What the model cannot tell us", 2)
B(" Only one hiking cycle and one easing episode, and the first 12 quarters are dominated by the post-COVID recovery.", "Short sample.")
B(f" Residuals are autocorrelated (Durbin-Watson {fit['durbin_watson']:.1f}), so the Monte Carlo simulates persistent errors rather than independent ones; standard errors use the Newey-West correction.", "Serial correlation.")
B(f" The burden is capped at {SS['in_sample_burden_max']:.1f}% in the sample. The Severe scenario reaches {SS['peak_burden']['D. Severe']:.1f}%, so the model is extrapolating there. Section 6 shows the answer if the relationship steepens.", "Extrapolation.")
B(" It is tempting to assume borrower buffers have thinned since 2022-23. The RBA's loan-level evidence says the opposite for the median borrower (more than a year of repayments in offset and redraw, stronger than before the pandemic). The risk is in the tail: about 2% of variable-rate owner-occupiers are in cash-flow shortfall, and aggregate data cannot say which lenders hold them.", "Buffers.")
B(" System averages say nothing about a lender's own mix, serviceability policy or collections performance.", "Aggregation.")

# ======================================================= 5 scenarios
doc.add_heading("5. Scenarios", 1)
P("Four cash-rate paths. They are scenarios, not forecasts, and no probability is attached to them. The first two quarters are shared (4.60% after the September decision).")
sb = SS["burden_by_scenario"]
TABLE(["Scenario", "Cash rate path", "Cash rate end-2027", "Burden end-2027, % of income"], [
    ["A. Hold", "No change from 4.60%", "4.60%", f1(sb["A. Hold"]["2027Q4"])],
    ["B. Ease", "Two 25bp cuts in 2027Q2 and Q3", "4.10%", f1(sb["B. Ease"]["2027Q4"])],
    ["C. Hawkish", "Two more 25bp hikes by 2027Q1", "5.10%", f1(sb["C. Hawkish"]["2027Q4"])],
    ["D. Severe", "A 25bp hike every quarter to 2027Q3, plus unemployment rising from 4.4% to 6.0% by end-2027 (assumption)", "5.60%", f1(sb["D. Severe"]["2027Q4"])],
], [2.6, 8.0, 2.8, 3.0], align_right_from=2)
FIG("outputs/fig7_scenarios.png", "Figure 7. Cash-rate scenarios and the interest burden they imply (pass-through 0.87, debt-to-income held at the 2026Q2 level; sensitivity in section 6).")
P("Results come from 4,000 Monte Carlo draws per scenario. Each draw takes a lag (4, 5 or 6 quarters), model parameters from a moving-block bootstrap of the fit, a pass-through coefficient drawn around the measured value, and an autocorrelated residual that starts from the latest observed gap between model and data. The Severe scenario adds the unemployment effect with its wide uncertainty.")
FIG("outputs/fig8_npl_fan.png", "Figure 8. Arrears ratio to 2028Q4. Left: all ADIs. Right: the peer group used for the hypothetical lender. Real history; scenario medians and 80% ranges are model output.")
rows = []
for sc in SC:
    rows.append([sc, f2(fan("system", sc, "2027Q3")), f"{f2(fan('system', sc, '2028Q4'))}  ({rng80('system', sc, '2028Q4')})", f"{f2(fan('peer', sc, '2028Q4'))}  ({rng80('peer', sc, '2028Q4')})"])
TABLE(["Scenario", "All ADIs 2027Q3 (same in all)", "All ADIs 2028Q4, median (80% range)", "Peer group 2028Q4, median (80% range)"], rows, [2.8, 3.8, 4.9, 4.9])
P(f"Two points matter more than the differences between scenarios. First, until 2027Q3 every scenario is the same, because arrears in that period depend on burdens that have already happened; the system ratio drifts down to about {dip_v:.2f}% and back to {f2(fan('system','A. Hold','2027Q3'))}%. Decisions taken today change the arrears path only from late 2027. "
  f"Second, even the Severe scenario moves the system ratio by roughly 0.2 points, to {f2(fan('system','D. Severe','2028Q4'))}%, because the whole relationship is a slope of 0.06. If that understates tail behaviour, the problem is in the tail and not in the average.")
doc.add_heading("Reverse stress test", 2)
P(f"What would it take to reach 1.25% system arrears by end-2028 (about 0.15 points above the 2025 peak)? On the fitted relationship, a burden of {rev['1.25']['burden_needed']:.1f}% of income, which needs a cash rate near {rev['1.25']['cash_rate_needed']:.1f}% (with debt-to-income unchanged), or an unemployment rise of about {rev['1.25']['unemployment_rise_needed_pts_at_C']:.1f} points on top of the Hawkish path. "
  f"Reaching 1.5% needs a cash rate near {rev['1.5']['cash_rate_needed']:.0f}% or about {rev['1.5']['unemployment_rise_needed_pts_at_C']:.0f} points more unemployment. Neither is plausible through interest rates alone: a credit event at that scale in this model is a labour-market event.")

# ======================================================= 6 sensitivity
doc.add_heading("6. What moves the answer", 1)
FIG("outputs/fig11_sensitivity.png", "Figure 9. Change in the 2028Q4 system arrears ratio (central Hawkish path, deterministic) when one assumption changes.", 15.0)
P(f"The biggest swings are unemployment (+{tor['values']['Unemployment +1.5 points']-tor['base']:.2f} points for a 1.5 point rise) and the uncertainty about the slope itself (-{tor['base']-tor['values']['Slope at 5th pct of bootstrap']:.2f} to +{tor['values']['Slope at 95th pct of bootstrap']-tor['base']:.2f}). Lag, pass-through, rising household debt and even doubling the slope above the sample maximum change the result by 0.02 points or less. "
  "The conclusion that system arrears rise only modestly is robust to every model choice tested here. It is not robust to a labour-market shock, which the data cannot say much about.")

# ======================================================= 7 lender
doc.add_heading("7. What it means for the lender", 1)
ln = SS["lender_now"]
P(f"The hypothetical lender holds ${asm['book_bn']:.0f}bn of mortgages and behaves like APRA's 'other domestic banks': {ln['npl_ratio']:.2f}% non-performing today, which is about ${ln['npl_stock_m']:,.0f}m or {ln['npl_loans']:,} loans at an average of ${asm['avg_loan_k']:.0f}k. "
  "The table shows the peak of each simulated path over 2026Q3 to 2028Q4, so it includes noise and is higher than the 2028Q4 median.")
rows = []
for sc in SC:
    l = lend[sc]; rows.append([sc, f"{l['peak_npl_p50']:.2f} / {l['peak_npl_p90']:.2f}", f"{l['d_stock_p50_m']:.0f} / {l['d_stock_p90_m']:.0f}",
                              f"{l['prov_p50_m']['0.1']:.0f} / {l['prov_p50_m']['0.2']:.0f} / {l['prov_p50_m']['0.3']:.0f}", f"{l['officers_p50']:.1f} / {l['officers_p90']:.1f}"])
TABLE(["Scenario", "Peak arrears %, median / 90th", "Extra 90+ day loans, $m, median / 90th", "Extra provisions $m, median, LGD 10 / 20 / 30%", "Extra hardship officers, median / 90th"], rows, [2.4, 3.2, 3.8, 4.2, 3.0], size=8.5)
FIG("outputs/fig9_lender_impact.png", "Figure 10. Hypothetical lender: extra provisions and hardship officers at the peak of each scenario. All lender parameters are assumptions.")
doc.add_heading("Provisions under AASB 9: stage 2 and timing", 2)
rows = []
for sc in SC:
    e = ecl["by_scenario"][sc]["p50"]; rows.append([sc, f"{e['stage3_only_m']}", f"{e['with_stage2_m']['0.2']} / {e['with_stage2_m']['0.3']} / {e['with_stage2_m']['0.4']}"])
TABLE(["Scenario (median path)", "Stage 3 only, $m", "Plus stage 2, $m (lifetime PD 20 / 30 / 40%)"], rows, [4.0, 4.0, 7.0])
P(f"AASB 9 presumes, unless the lender can show otherwise, that a loan more than 30 days past due has had a significant increase in credit risk (stage 2) and must carry a lifetime expected loss. In the peer group the 30-89 day balance has been {ecl['stage2_to_stage3_ratio']:.2f} times the 90+ day balance on average since 2021 (range {ecl['ratio_range'][0]:.2f} to {ecl['ratio_range'][1]:.2f}). "
  "Moving those loans into stage 2 at an assumed lifetime default probability of 20% to 40% and the same 20% loss given default adds about 15% to 20% to the extra provisions. The size does not change the conclusion. The timing does: AASB 9 provisions are forward-looking and probability-weighted across scenarios, so a lender that raises the weight on Hawkish or Severe will book provisions in 2026, well before the arrears arrive in 2027 and 2028. The P&L impact comes early even though the losses come late.")
P(f"Even in the Severe 90th percentile the extra provisions are ${lend['D. Severe']['prov_p90_m']['0.3']:.0f}m at a 30% loss given default on a ${asm['book_bn']:.0f}bn book, about {lend['D. Severe']['prov_p90_m']['0.3']/(asm['book_bn']*1000)*1e4:.0f} basis points. The staffing numbers count only loans that reach 90 days; they exclude customers in earlier arrears and those who ask for hardship help before missing a payment, so they are a floor.")

# ======================================================= 8 options
doc.add_heading("8. Decision options", 1)
doc.add_heading("Where the risk sits: loan-to-value ratio", 2)
FIG("outputs/fig10_lvr_pricing.png", "Figure 11. Left: real APRA data, non-performing loans as a share of loans by LVR band. Right: illustrative annual credit-cost premium vs loans below 80% LVR (assumed loss given default and 1.5 years in default).")
b = prc["bands"]
P(f"Real APRA data: non-performing shares are {b['LVR < 60%']['npl_now']:.1f}% below 60% LVR, {b['60% ≤ LVR < 80%']['npl_now']:.1f}% at 60-80%, {b['80% ≤ LVR < 90%']['npl_now']:.1f}% at 80-90% and {b['LVR ≥ 95%']['npl_now']:.1f}% at 95% and above. "
  f"On the stated assumptions that is a premium of about {b['80% ≤ LVR < 90%']['premium_bp']['0.2']:.0f}bp a year at 80-90% LVR (range {b['80% ≤ LVR < 90%']['premium_bp']['0.1']:.0f} to {b['80% ≤ LVR < 90%']['premium_bp']['0.3']:.0f}) and {b['LVR ≥ 95%']['premium_bp']['0.2']:.0f}bp at 95%+ (range {b['LVR ≥ 95%']['premium_bp']['0.1']:.0f} to {b['LVR ≥ 95%']['premium_bp']['0.3']:.0f}), "
  f"rising by about a fifth in the Severe scenario. The figures are cross-section snapshots, not controlled for loan age, income or location, so they overstate how much LVR alone causes. "
  "There may also be reverse causality: where the bands reflect current rather than origination LVR, a loan in arrears drifts to a higher LVR, so some of the gradient would be arrears causing high LVR rather than the other way round.")
rows = []
for band, lab_ in (("80% ≤ LVR < 90%", "80-90% LVR"), ("LVR ≥ 95%", "95%+ LVR")):
    v = lmi["bands"][band]; rows.append([lab_, f"{v['uninsured_bp']:.0f}", f"{v['net_of_lmi_bp']['0.6']:.0f} / {v['net_of_lmi_bp']['0.8']:.0f} / {v['net_of_lmi_bp']['0.95']:.0f}"])
TABLE(["Band", "Premium before insurance, bp", "Lender's own premium if 60 / 80 / 95% of loans insured, bp"], rows, [3.4, 4.6, 7.0])
P("Loans above 80% LVR are usually covered by lenders mortgage insurance paid for by the borrower, or by a government guarantee. If 80% of the band is insured and claims recover 90% of the loss (both assumptions), the lender's own expected loss on an 80-90% LVR loan is about 5bp, not 17bp. Pricing the whole band would charge insured borrowers twice. The premium matters for the uninsured part of the band: LMI waivers for selected professions and other low-deposit products where the lender keeps the loss. The lender's own mix of insured and uninsured high-LVR loans is the first number to get.", italic=False)
doc.add_heading("New-lending standards are drifting the wrong way", 2)
lab = {"new_exceptions_share": "Exceptions to policy, % of approvals", "new_lvr_ge90_share": "New loans at LVR 90%+, %", "new_io_share": "New interest-only loans, %", "new_dti_ge6_share": "New loans at debt-to-income 6+, %"}
TABLE(["Share of new lending, all ADIs", "Year ago", "2025 low", "2026Q2"], [[lab[k], f1(nl[k]["a_year_ago"]), f1(nl[k]["low_2025"]), f1(nl[k]["latest"])] for k in lab], [8.0, 2.6, 2.6, 2.6])
P(f"About {nl['funded_le3y_share']['latest']:.0f}% of the stock was funded in the past three years, so changes in new lending standards reshape the book quickly. The serviceability test is still conservative: new loans are assessed at {SS['new_lending_assess']['assess_rate']:.2f}% against an actual variable rate of {SS['new_lending_assess']['var_rate']:.2f}%, a buffer of about 2.8 points.")
doc.add_heading("Options compared", 2)
TABLE(["Option", "What it does", "Evidence", "Cost / risk", "Verdict"], [
    ["1. Do nothing", "Keep current policy and staffing.", "Arrears low and flat to 2027Q3; provisions rise little.", "Standards drift continues; hardship team under-sized if Severe.", "Not recommended."],
    ["2. Broad tightening", "Cut LVR and DTI limits across the book, higher buffer.", "Model: arrears ratio moves 0.1 to 0.2 points even in Severe. About 83% of housing credit is below 80% LVR.", "Gives up volume and margin where risk is low; share loss to peers.", "Not recommended."],
    ["3. Targeted standards", "Cap exceptions at 2025 low (about 4.7%); stop growth of 90%+ LVR and interest-only share.", "Real APRA: risk concentrated above 80% LVR; new-lending drift visible.", "Some volume lost at the margin; needs policy-exception reporting.", "Recommended."],
    ["4. Risk-based pricing", f"Add about {b['80% ≤ LVR < 90%']['premium_bp']['0.2']:.0f}bp at 80-90% LVR and {b['LVR ≥ 95%']['premium_bp']['0.2']:.0f}bp at 95%+ on uninsured loans only.", "Premium follows the real arrears gradient; LMI removes most of it for insured loans.", "Competitive pressure on waiver products; re-estimate with own loss data.", "Recommended, uninsured only."],
    ["5. Hardship capacity", f"Fund {lend['A. Hold']['officers_p90']:.0f} officers in 2027; pre-approve {lend['D. Severe']['officers_p90']-lend['A. Hold']['officers_p90']:.0f} more on triggers.", "Arrears reach the lender from late 2027; hardship lead time is months.", "Small fixed cost; low regret.", "Recommended."],
    ["6. Early outreach", "Contact borrowers whose payment-to-income rose most since 2022 before they miss a payment.", "Past-due leads 90+ day arrears by two quarters.", "Needs loan-level data; customer-contact limits.", "Pilot in 2027H1."],
], [2.4, 3.9, 3.8, 3.5, 2.8], align_right_from=9, size=8.5)

# ======================================================= 9 monitoring
doc.add_heading("9. Monitoring triggers", 1)
P("Two of the six indicators are at amber today (past-due change and the burden after the September hike). " + f"A trigger is useful only if it fires before the loss. The one trigger that can be tested on history is the 30-89 day past-due ratio: it rose by 0.10 points or more over two quarters {trg['n_signals']} times in {trg['n_quarters']} quarters, and both times the 90+ day ratio rose by at least 0.05 points within two quarters. "
  f"But it caught only {trg['npl_rises_flagged']} of {trg['npl_rises_total']} rises, so it confirms a turn; it does not warn early. The latest reading is {trg['past_due_change_2q_latest']:+.2f}: amber, not yet red. The other thresholds below are judgement, not estimates, and are marked as such.")
TABLE(["Indicator", "Amber", "Red", "Latest", "Action on red"], [
    ["30-89 day past-due ratio, 2-quarter change (APRA, tested)", "+0.07", "+0.10", f"{trg['past_due_change_2q_latest']:+.2f}", "Release pre-approved hardship staff; start early outreach."],
    ["Interest burden, % of income (RBA E2)", "9.5", f"{SS['in_sample_burden_max']:.1f} (previous peak)", f"{BS['burden_after_sep26']:.1f} (est.)", "Re-run scenarios with Severe weights."],
    ["Cash rate", "5.10%", "5.35%", f"{BS['cash_now']:.2f}%", "Move to Hawkish staffing and pricing."],
    ["Own arrears ratio vs scenario fan", "Above median", "Above 90th percentile, two quarters", "n/a (hypothetical)", "Review segment mix and collections."],
    ["Unemployment rate (judgement)", "+0.5 point in six months", "+1.0 point", "4.4% (OECD, 2026Q2)", "Apply Severe overlay to provisioning."],
    ["Exceptions to policy, % of approvals (judgement)", "5.5", "6.0", f"{nl['new_exceptions_share']['latest']:.1f}", "Freeze exceptions authority."],
], [5.2, 2.2, 3.2, 2.6, 3.4], align_right_from=9, size=8.5)

# ======================================================= 10 limits
doc.add_heading("10. Model risk and what would improve this", 1)
B(" The lender, its size, the loss given default and the staffing ratio are assumptions. The market evidence is real, but conclusions about one institution need that institution's loan-level history.", "Hypothetical lender.")
B(" The 2026 hikes are real. The cash-rate scenarios are not forecasts, and the 30 September decision comes from published news coverage rather than the RBA data files, which stop at June or earlier.", "Scenarios.")
B(" The OECD unemployment series reads 4.4% in 2026Q2 against 4.1% in some news coverage of the ABS release; the OECD series is used consistently.", "Unemployment source.")
B(" Residential APRA data start in 2019. An older APRA history file would add the 2011-15 cycle; RBA CPI and ABS wage and labour-force data would help the unemployment overlay; loan-level data (payment-to-income, buffers, LMI status) would show where the 2% of borrowers in shortfall sit in our own book.", "Next steps.")
B(" a sustained rise in unemployment of 1 point or more, the 30-89 day ratio rising 0.10 points in two quarters, or arrears in 2027 failing to dip as the model expects would each mean the burden model is understating risk, and the Severe overlay should become the planning case.", "What would change my mind.")
B(" The model describes the relationship of arrears with interest burden since 2021, and it is a short, single-cycle fit. It is a way to organise decisions, not a forecast to be believed to two decimals.", "How to read this.")

doc.add_heading("Sources", 1)
for s in [
    "Reserve Bank of Australia, statistical tables A2 (monetary policy changes), E2 (household finances) and F5 (indicator lending rates), historical series, user-supplied downloads.",
    "Australian Prudential Regulation Authority, Quarterly authorised deposit-taking institution property exposures, June 2026 (residential mortgage arrears, LVR bands, new-lending standards).",
    "Bank for International Settlements, residential property prices (Australia) and credit to households (Australia), via FRED series QAUN628BIS and QAUHAM770A.",
    "OECD, registered unemployment rate for Australia, via FRED (harmonised, quarterly).",
    "Reserve Bank of Australia, Financial Stability Review, October 2026, chapter 2 (Resilience of Australian households and businesses): https://www.rba.gov.au/publications/fsr/2026/oct/resilience-of-australian-households-and-businesses.html",
    "RBA cash-rate decisions of 2026 (including 30 September 2026): RBA announcements as reported by Forbes Advisor Australia and the Commonwealth Bank mortgage-rate news pages.",
]: B(s)

doc.save("docs/AU_mortgage_stress_test_report.docx"); print("saved docs/AU_mortgage_stress_test_report.docx")
