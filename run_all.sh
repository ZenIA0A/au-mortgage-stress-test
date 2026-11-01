#!/usr/bin/env bash
# Reproduce every number, figure and the report. Run from the project folder: bash run_all.sh
set -e
cd "$(dirname "$0")"
mkdir -p outputs docs
python3 src/01_prepare.py            # parse RBA and APRA files into tidy quarterly panels (data/*.csv)
python3 src/02_burden_and_cycles.py  # pass-through, interest burden, repayment examples (figures 1 to 3)
python3 src/03_arrears_model.py      # lead-lag, rolling-origin validation, robustness, lender groups (figures 4 to 6)
python3 src/04_scenarios.py          # scenarios, Monte Carlo, lender impact, pricing, sensitivity (figures 7 to 11)
python3 src/05_build_report.py       # docs/AU_mortgage_stress_test_report.docx (convert to PDF with LibreOffice if wanted)
