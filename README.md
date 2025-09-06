# Daily Market Wrap Bot — Local Quickstart

Requirements
- Python 3.11+
- X (Twitter) developer app with Read + Write permissions
- Polygon API key, Google (Gemini) API key

Setup
1) Create venv and install deps
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Configure environment
```bash
cp example.env .env
# Edit .env with your real keys
```

3) Run
- Safe dry run (no posting):
```bash
export MOCK_MODE=1 DRY_RUN=1
python poster.py
```
- Live post (be careful):
```bash
export MOCK_MODE=0 DRY_RUN=0
python poster.py
```

Environment variables
- POLYGON_API_KEY, GOOGLE_API_KEY
- X_CONSUMER_KEY, X_CONSUMER_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET
- DRY_RUN (1 logs only), MOCK_MODE (1 bypasses external APIs)

CI (optional)
- See `.github/workflows/daily-tweet.yml`. Add the same secrets in your repo and enable the schedule.
