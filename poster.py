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
import requests

# -------------------------------------------------------------------
# Setup and Config
# -------------------------------------------------------------------
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

DRY_RUN = os.getenv("DRY_RUN", "0") == "1"
MOCK_MODE = os.getenv("MOCK_MODE", "0") == "1"

poly = None
gemini_model = None
twitter_client = None
twitter_client_v2 = None

if not MOCK_MODE:
    POLY_KEY = os.environ["POLYGON_API_KEY"]
    GEMINI_KEY = os.environ["GOOGLE_API_KEY"]
    poly = RESTClient(api_key=POLY_KEY)

    genai.configure(api_key=GEMINI_KEY)
    gemini_model = genai.GenerativeModel("gemini-2.5-flash")

    auth = tweepy.OAuth1UserHandler(
        os.environ["X_CONSUMER_KEY"],
        os.environ["X_CONSUMER_SECRET"],
        os.environ["X_ACCESS_TOKEN"],
        os.environ["X_ACCESS_TOKEN_SECRET"],
    )
    twitter_client = tweepy.API(auth)

    # X API v2 client (user context)
    twitter_client_v2 = tweepy.Client(
        consumer_key=os.environ["X_CONSUMER_KEY"],
        consumer_secret=os.environ["X_CONSUMER_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )
else:
    logging.info("Running in MOCK_MODE; no external API calls will be made.")


# -------------------------------------------------------------------
# Data Fetching
# -------------------------------------------------------------------
def pct_change(symbol: str) -> float:
    """Return % change between yesterday and today for a symbol."""
    if MOCK_MODE:
        mock_changes = {"SPY": 0.72, "QQQ": -0.38, "DIA": 0.15}
        return mock_changes.get(symbol.upper(), 0.0)
    try:
        today = datetime.date.today()
        prev_day = today - datetime.timedelta(days=2)
        bars = poly.get_aggs(symbol, 1, "day", prev_day, today)
        if len(bars) < 2:
            raise RuntimeError(f"Not enough data for {symbol}")
        # Support both explicit and shorthand attribute names
        last_close = getattr(bars[-1], "close", getattr(bars[-1], "c", None))
        prev_close = getattr(bars[-2], "close", getattr(bars[-2], "c", None))
        if last_close is None or prev_close is None:
            raise AttributeError("Agg close fields not found")
        return round(((last_close - prev_close) / prev_close) * 100, 2)
    except Exception as exc:
        logging.warning("Failed to fetch %s change from Polygon (%s). Falling back to 0.0%%", symbol, exc)
        return 0.0


def get_news() -> str:
    """Fetch the last 5 general-market headlines from Polygon and join them."""
    if MOCK_MODE:
        return "Stocks steady as investors assess jobs data and Fed outlook."
    # Prefer HTTP Reference News API for broad headlines
    try:
        titles = fetch_latest_news_titles_http(limit=5)
        if titles:
            return "; ".join(titles)
    except Exception as exc:
        logging.warning("HTTP news fetch failed (%s)", exc)
    # Fallback to SDK if available
    try:
        if poly is not None and hasattr(poly, "list_news"):
            news = poly.list_news(limit=5)
            for n in news:
                title = getattr(n, "title", getattr(n, "headline", None))
                if title:
                    return title
    except Exception as exc:
        logging.warning("SDK list_news failed (%s)", exc)
    return "No major news today."


def fetch_latest_news_titles_http(query: str | None = None, limit: int = 5) -> list[str]:
    """Fetch latest general-market news titles via Polygon HTTP Reference News API."""
    api_key = os.environ["POLYGON_API_KEY"]
    params = {
        "limit": str(limit),
        "order": "desc",
        "sort": "published_utc",
        "apiKey": api_key,
    }
    if query:
        params["query"] = query
    url = "https://api.polygon.io/v2/reference/news"
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results") or []
    titles: list[str] = []
    for item in results:
        title = item.get("title")
        if title:
            titles.append(title)
    return titles

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
    if MOCK_MODE:
        return clamp_tweet(prompt)
    try:
        resp = gemini_model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.5,
            },
        ) 
        text = getattr(resp, "text", "") or ""
        return clamp_tweet(text)
    except Exception as exc:
        logging.warning("Gemini generation failed (%s). Falling back to prompt.", exc)
        return clamp_tweet(prompt)


def post_tweet(text: str) -> None:
    """Post the tweet to Twitter, or log if DRY_RUN is enabled."""
    if DRY_RUN or MOCK_MODE:
        logging.info("[DRY RUN] Tweet would be: %s", text)
        return

    # Try v2 first
    if twitter_client_v2 is not None:
        try:
            resp = twitter_client_v2.create_tweet(text=text)
            logging.info("Tweet posted via v2: %s", getattr(resp, "data", resp))
            return
        except Exception as exc:
            logging.warning("v2 create_tweet failed (%s). Falling back to v1.1.", exc)

    # Fallback to v1.1
    if twitter_client is not None:
        twitter_client.update_status(status=text)
        logging.info("Tweet posted via v1.1: %s", text)


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

    if MOCK_MODE:
        tweet = clamp_tweet(
            f"SPY {spy:+.2f}%, QQQ {qqq:+.2f}%, DIA {dia:+.2f}%. Top: {headline}"
        )
    else:
        logging.info("Generating tweet with Gemini…")
        tweet = generate_tweet(prompt)

    if not tweet:
        raise RuntimeError("Generated empty tweet")

    post_tweet(tweet)


if __name__ == "__main__":
    main()


