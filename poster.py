"""
poster.py
---------
Generates a concise daily market wrap tweet using OpenAI Responses API + Web Search,
then posts it to Twitter via Tweepy. No Polygon/Gemini usage.
"""

import os
import logging
from dotenv import load_dotenv
import tweepy
from openai import OpenAI

# -------------------------------------------------------------------
# Setup and Config
# -------------------------------------------------------------------
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

DRY_RUN = os.getenv("DRY_RUN", "0") == "1"

# Twitter API clients
auth = tweepy.OAuth1UserHandler(
    os.environ["X_CONSUMER_KEY"],
    os.environ["X_CONSUMER_SECRET"],
    os.environ["X_ACCESS_TOKEN"],
    os.environ["X_ACCESS_TOKEN_SECRET"],
)
twitter_client = tweepy.API(auth)
twitter_client_v2 = tweepy.Client(
    consumer_key=os.environ["X_CONSUMER_KEY"],
    consumer_secret=os.environ["X_CONSUMER_SECRET"],
    access_token=os.environ["X_ACCESS_TOKEN"],
    access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
)

# OpenAI client
openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))


# -------------------------------------------------------------------
# Text Helpers
# -------------------------------------------------------------------
def clamp_tweet(text: str, max_len: int = 280) -> str:
    text = " ".join((text or "").strip().split())
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def generate_tweet_text() -> str:
    """Use OpenAI Responses API with web_search to generate the tweet text."""
    user_msg = (
        "Give a concise, objective daily US market wrap tweet. Focus on major indices (S&P 500, Nasdaq, Dow) "
        "and primary drivers. Constraints: <=260 chars, no emojis/hashtags/links. Return tweet text only."
    )
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        if DRY_RUN:
            return clamp_tweet("Markets mixed today; generating tweet disabled (no OPENAI_API_KEY set).")
        raise RuntimeError("OPENAI_API_KEY not set")
    try:
        resp = openai_client.responses.create(
            model="gpt-4o-mini",
            input=[{"role": "user", "content": user_msg}],
            tools=[{"type": "web_search"}],
            tool_choice="auto",
            temperature=0.5,
        )
        text_chunks = []
        for item in getattr(resp, "output", []) or []:
            for part in getattr(item, "content", []) or []:
                if getattr(part, "type", None) == "output_text":
                    text_chunks.append(getattr(part, "text", ""))
        text = "\n".join([t for t in text_chunks if t]).strip()
        return clamp_tweet(text)
    except Exception as exc:
        logging.error("OpenAI generation failed: %s", exc)
        if DRY_RUN:
            return clamp_tweet("Markets steady; awaiting live API to generate final tweet.")
        return ""

# -------------------------------------------------------------------
# Prompt Handling
# -------------------------------------------------------------------
## Posting Logic


def post_tweet(text: str) -> None:
    """Post the tweet to Twitter, or log if DRY_RUN is enabled."""
    if DRY_RUN:
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


def main():
    logging.info("Generating tweet with OpenAI + Web Search…")
    tweet = generate_tweet_text()
    if not tweet:
        raise RuntimeError("Generated empty tweet")
    post_tweet(tweet)


if __name__ == "__main__":
    main()


