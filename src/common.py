"""Shared loaders for the Australian mortgage stress-test project (real data, see data/SOURCES.md)."""
import pandas as pd
import openpyxl

D = "data/"

def read_apra_tab(sheet, path=D + "apra_property_exposures_jun2026.xlsx"):
    """Return DataFrame (index = quarter end, columns = 'Section | Label') for one APRA table, '*' (masked) as NaN."""
    ws = openpyxl.load_workbook(path, data_only=True, read_only=True)[sheet]
    rows = list(ws.iter_rows(values_only=True))
    hdr = next(i for i, r in enumerate(rows) if r[2] is not None and hasattr(r[2], "year"))
    dates = [pd.Timestamp(x) for x in rows[hdr][2:] if x is not None]
    out, section = {}, ""
    for r in rows[hdr + 1:]:
        lab = r[0]
        if lab is None: continue
        lab = " ".join(str(lab).split())
        vals = r[2:2 + len(dates)]
        if all(v is None for v in vals):
            section = lab; continue
        out[f"{section} | {lab}"] = pd.to_numeric(pd.Series(list(vals), index=dates), errors="coerce")
    return pd.DataFrame(out)

def load_rba(name):
    return pd.read_csv(D + name, index_col=0, parse_dates=True)

def quarter_label(ts):
    return f"{ts.year}Q{(ts.month - 1) // 3 + 1}"
