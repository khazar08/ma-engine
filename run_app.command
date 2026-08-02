#!/bin/bash
# Double-click this file (macOS) to launch the M&A engine web app.
cd "$(dirname "$0")"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
else
  source .venv/bin/activate
fi
exec streamlit run app.py
