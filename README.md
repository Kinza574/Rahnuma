# Rahnuma — University Field Advisor

**Live app:** https://rahnuma.streamlit.app/

Rahnuma is a rule-based expert system for Pakistani Matric, Inter and O/A-Level students.
It asks about studies, interests, skills, entry tests and budget, checks admission rules
(PMDC, PEC, HEC, PNMC, PCATP), recommends up to three university fields and lists matching universities.

- Our own forward-chaining inference engine with MYCIN certainty factors (no rule library).
- 90 rules stored as data in `knowledge_base/rules.json` (55 compute, 35 decision, 209 leaf conditions).
- Streamlit interface: Guided Counselling, Counsellor Desk, Knowledge Base, Knowledge Acquisition, About.

Screenshots of every page (desktop 1366px and phone 390px) are made during testing and kept in a local
`screenshots/` folder, which is not committed to Git.

---

## Project layout

```
app.py                  entry point (top navigation)
knowledge_base/         rules, thresholds, questions, fields, universities, market data + loader
engine/                 working memory, conditions, inference, actions, certainty, explanation, consult
ui/                     theme, components, session state
views/                  one file per page
samples/                5 sample students with expected results
tests/                  pytest tests (engine, rules, eligibility, samples, data, UI)
tools/make_pdf.py       builds docs/code_explanation.pdf from the code
tools/pdf_text.py       dev tool: extract text from an admission PDF (needs requirements-dev.txt)
```

## Run locally on Windows (PowerShell)

You need Python 3.12 (`py -3.12 --version` should work).

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
pytest -q
```

If PowerShell says running scripts is disabled when you activate the virtual environment, run this once and try again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

The app opens at http://localhost:8501.

To rebuild the code explanation PDF:

```powershell
python tools/make_pdf.py
```

## Deploy on Streamlit Community Cloud

1. Push the project to a GitHub repository (see "Push to GitHub" below).
2. Go to https://share.streamlit.io and sign in with GitHub.
3. Click **Create app** (or **New app**) and choose **Deploy a public app from GitHub**.
4. Pick the repository, the branch (`main`) and the main file path `app.py`.
5. Open **Advanced settings** and choose **Python 3.12**. No secrets are needed.
6. Click **Deploy**. The first build installs `requirements.txt` and takes a few minutes.
7. When it is running, put the public URL in this README and in `APP_URL` in `ui/theme.py` (this app runs at https://rahnuma.streamlit.app/).

To read the logs: open the app on share.streamlit.io, click **Manage app** (bottom right of the app),
and the log panel shows the build and runtime messages. Use **Reboot app** from the same menu after a change
that does not redeploy by itself.

Note: Streamlit Cloud does not keep files after a restart. Changes made on the Knowledge Acquisition page
apply to the current session only; download the JSON to keep them.

## Push to GitHub

```powershell
git remote add origin https://github.com/<your-user>/rahnuma.git
git branch -M main
git push -u origin main
```

Create the empty repository on GitHub first (no README, no .gitignore), then run the commands above.

## Data and limitations

- University data (`knowledge_base/universities.json`, as of 2026-11-13): 48 universities, 234 programme
  offerings, 76 verified on an official page. Unverified rows show "Not yet verified".
- Job-market data (`knowledge_base/market_data.json`) is broad and partly estimated; estimates are labelled.
- Rules simplify real admission policies and merit cut-offs change every year.

For guidance only — always confirm admission criteria with the university.
