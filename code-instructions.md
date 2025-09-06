Got it. Here’s a single self-contained Markdown file you can paste straight into Cursor.

It includes:
	•	📂 Project structure
	•	🔑 example.env
	•	📜 requirements.txt
	•	📝 poster.py with clean functions, logging, and DRY_RUN flag
	•	🎨 Jinja prompt template
	•	⚙️ GitHub Actions workflow

⸻


# 📈 Daily Market Wrap Bot

This guide walks step-by-step through building a Python app that posts a **daily market + news wrap** to Twitter, powered by **Polygon (free tier)**, **Gemini 2.5 Flash-Lite**, and **GitHub Actions**.

---

## 1. Project Layout

market-wrap-bot/
├─ poster.py
├─ prompt_template.j2
├─ requirements.txt
├─ .gitignore
├─ .env              # secrets (never commit)
├─ example.env       # safe template
└─ .github/
└─ workflows/
└─ daily-tweet.yml

---

## 2. Dependencies

`requirements.txt`
```txt
python-dotenv==1.*
tweepy==4.*
Jinja2==3.*
polygon-api-client==1.*
google-generativeai==0.7.*
```

⸻

3. Example Environment File

example.env

# Polygon API
POLYGON_API_KEY=your_polygon_key

# Google Gemini
GOOGLE_API_KEY=your_gemini_key

# X (Twitter) API
X_CONSUMER_KEY=your_consumer_key
X_CONSUMER_SECRET=your_consumer_secret
X_ACCESS_TOKEN=your_access_token
X_ACCESS_TOKEN_SECRET=your_access_token_secret

# Dry run toggle: set to 1 to log instead of posting
DRY_RUN=1

.gitignore

.env


⸻

4. Jinja Prompt Template

prompt_template.j2

Generate a concise daily market wrap tweet.
Data:
- S&P500 proxy (SPY): {{ spy_change }}%
- Nasdaq proxy (QQQ): {{ qqq_change }}%
- Dow proxy (DIA): {{ dia_change }}%
- Top news: {{ headline }}

Constraints:
- ≤260 characters
- No emojis, hashtags, or links
Output: tweet text only.


⸻

5. Main Script

poster.py

"""
poster.py
---------
Fetches daily market performance (SPY, QQQ, DIA) and a top headline from Polygon,
generates a tweet with Gemini, and posts it to Twitter via Tweepy.
"""

import os
import logging
import datetime
from dotenv import load_dotenv
import tweepy
from polygon import RESTClient
import google.generativeai as genai
from jinja2 import Template

# -------------------------------------------------------------------
# Setup and Config
# -------------------------------------------------------------------
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

POLY_KEY = os.environ["POLYGON_API_KEY"]
GEMINI_KEY = os.environ["GOOGLE_API_KEY"]
DRY_RUN = os.getenv("DRY_RUN", "0") == "1"

poly = RESTClient(api_key=POLY_KEY)

genai.configure(api_key=GEMINI_KEY)
gemini_model = genai.GenerativeModel("gemini-2.5-flash-lite")

auth = tweepy.OAuth1UserHandler(
    os.environ["X_CONSUMER_KEY"],
    os.environ["X_CONSUMER_SECRET"],
    os.environ["X_ACCESS_TOKEN"],
    os.environ["X_ACCESS_TOKEN_SECRET"],
)
twitter_client = tweepy.API(auth)


# -------------------------------------------------------------------
# Data Fetching
# -------------------------------------------------------------------
def pct_change(symbol: str) -> float:
    """Return % change between yesterday and today for a symbol."""
    today = datetime.date.today()
    prev_day = today - datetime.timedelta(days=2)
    bars = poly.get_aggs(symbol, 1, "day", prev_day, today)
    if len(bars) < 2:
        raise RuntimeError(f"Not enough data for {symbol}")
    return round(((bars[-1].c - bars[-2].c) / bars[-2].c) * 100, 2)


def get_news() -> str:
    """Fetch the top headline from Polygon."""
    news = poly.list_news(ticker="SPY", limit=1)
    for n in news:
        return n.title
    return "No major news today."


# -------------------------------------------------------------------
# Prompt Handling
# -------------------------------------------------------------------
def render_prompt(spy: float, qqq: float, dia: float, headline: str) -> str:
    """Render the Jinja template with market data and headline."""
    with open("prompt_template.j2") as f:
        template = Template(f.read())
    return template.render(
        spy_change=spy,
        qqq_change=qqq,
        dia_change=dia,
        headline=headline,
    )


def clamp_tweet(text: str, max_len: int = 280) -> str:
    """Trim or clamp tweet text to 280 characters."""
    text = " ".join(text.strip().split())
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


# -------------------------------------------------------------------
# Posting Logic
# -------------------------------------------------------------------
def generate_tweet(prompt: str) -> str:
    """Call Gemini to generate tweet text."""
    resp = gemini_model.generate_content(prompt)
    text = resp.text or ""
    return clamp_tweet(text)


def post_tweet(text: str) -> None:
    """Post the tweet to Twitter, or log if DRY_RUN is enabled."""
    if DRY_RUN:
        logging.info("[DRY RUN] Tweet would be: %s", text)
    else:
        twitter_client.update_status(status=text)
        logging.info("Tweet posted: %s", text)


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------
def main():
    logging.info("Fetching market data…")
    spy = pct_change("SPY")
    qqq = pct_change("QQQ")
    dia = pct_change("DIA")
    headline = get_news()

    prompt = render_prompt(spy, qqq, dia, headline)
    logging.info("Prompt:\n%s", prompt)

    logging.info("Generating tweet with Gemini…")
    tweet = generate_tweet(prompt)

    if not tweet:
        raise RuntimeError("Generated empty tweet")

    post_tweet(tweet)


if __name__ == "__main__":
    main()


⸻

6. GitHub Actions Workflow

.github/workflows/daily-tweet.yml

name: daily-market-wrap
on:
  schedule:
    - cron: "0 14 * * 1-5"   # 10:00 AM ET weekdays (14:00 UTC)
  workflow_dispatch:

jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - run: python poster.py
        env:
          POLYGON_API_KEY: ${{ secrets.POLYGON_API_KEY }}
          GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
          X_CONSUMER_KEY: ${{ secrets.X_CONSUMER_KEY }}
          X_CONSUMER_SECRET: ${{ secrets.X_CONSUMER_SECRET }}
          X_ACCESS_TOKEN: ${{ secrets.X_ACCESS_TOKEN }}
          X_ACCESS_TOKEN_SECRET: ${{ secrets.X_ACCESS_TOKEN_SECRET }}
          DRY_RUN: ${{ secrets.DRY_RUN }}


⸻

7. Local Testing

pip install -r requirements.txt
cp example.env .env
# fill in your real keys
python poster.py

	•	Set DRY_RUN=1 to log without posting.
	•	Remove or set DRY_RUN=0 to post live.

⸻

8. Deployment Notes
	•	Polygon free tier: 5 requests/min, 20k/month.
	•	Each run uses ~4 requests.
	•	Gemini “flash-lite”: negligible cost (< fractions of a cent per call).
	•	GitHub Actions: free for public repos.

⸻

✅ Done — pushing this repo and adding secrets in GitHub will get you daily weekday tweets at 10:00 AM ET.

---

Do you also want me to include a **unit test file** (`tests/test_prompt.py`) so you can run CI dry-runs on pull requests?