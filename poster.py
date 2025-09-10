import os
import logging
import argparse
from dotenv import load_dotenv  

import tweepy
from openai import OpenAI

from generator import NewsTopicWrap, Generator


load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
DRY_RUN = os.getenv("DRY_RUN", "0") == "1"
MAX_TWEET_LEN = 280


# Topic definitions
TOPICS = {
    "us-markets": """US Markets. Focus on major indices (S&P 500, Nasdaq, Dow) and primary drivers. Give a concise, objective 
summary of the topic using web search. Look at recent news and events. Look at the week ahead and predict the most important events.""",
    
    "us-markets-weekly-wrap": """US Markets Weekly Wrap. Summarize the last 5 trading days: approximate weekly performance for the S&P 500, Nasdaq, and Dow; notable sector leaders/laggards; key macro data and earnings that moved markets; noteworthy breadth/volatility. Use web search to verify facts. Be concise and objective.""",
    
    "us-markets-next-week-events": """US Markets Next Week. Preview the coming week’s main catalysts: economic releases (e.g., CPI, PPI, jobs, PMIs, Fed/FOMC), major earnings/IPO/events, and other potential movers. Include consensus/expectations when available. Use web search for the next 7 calendar days. Be concise and objective.""",
    "us-options": """SPY Market. Proivde an options trading 
    recommendation for SPY with specific strike prices and dates.""",
    "world-markets": """World Markets. Focus on international markets, major global indices, currency movements, and geopolitical events 
affecting global markets. Include European, Asian, and emerging market performance. Look at recent news and events.""",
    
    "nfl": """NFL. Focus on top performances, injuries, and games. Who is everyone talking about today? Always use specific teams and players.""",
    
    "nba": """NBA. Focus on top performances, injuries, trades, and games. Who is everyone talking about today? Always use specific teams and players.""",
    
    "mlb": """MLB. Focus on top performances, injuries, trades, and games. Who is everyone talking about today? Always use specific teams and players.""",
    
    "tech-news": """Tech News. Focus on major technology companies, product launches, earnings, acquisitions, and industry trends. 
Include AI, software, hardware, and startup news. Look at recent developments and what's trending in tech."""
}


def check_twitter_api_keys():
    if os.getenv("X_CONSUMER_KEY") is None or os.getenv("X_CONSUMER_SECRET") is None or os.getenv("X_ACCESS_TOKEN") is None or os.getenv("X_ACCESS_TOKEN_SECRET") is None:
        return False

    return True

# Text Helpers
def clamp_tweet(text: str, max_len: int = 280) -> str:
    text = " ".join((text or "").strip().split())
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def post_tweet(text: str) -> None:
    """Post the tweet to Twitter, or log if DRY_RUN is enabled."""
    if DRY_RUN:
        logging.info("[DRY RUN] Tweet would be: %s", text)
        return

    if not check_twitter_api_keys():
        logging.error("Twitter API keys not set. Tweet would be: %s", text)
        return

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


def print_market_wrap(market_wrap: NewsTopicWrap):
    # Add ANSI color codes for colored terminal output
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"

    print(f"{CYAN}Tweet:{RESET}")
    print(f"{GREEN}{market_wrap.tweet}{RESET}")
    print(f"\n{CYAN}Summary:{RESET}")
    print(f"{market_wrap.summary}")
    print(f"\n{CYAN}Citations:{RESET}")
    for citation in market_wrap.citations:
        print(f"{YELLOW}{citation}{RESET}")
    print(f"{RESET}")
    print("\n")


def generate_market_wrap(topic: str):
    generator = Generator()
    attempts = 0
    market_wrap: NewsTopicWrap | None = None
    while attempts < 5:
        market_wrap = generator.generate_summary(topic)
        tweet_text = market_wrap.tweet or ""
        if len(tweet_text) <= MAX_TWEET_LEN:
            break
        attempts += 1
        logging.info(
            "Tweet too long (%d chars > %d). Regenerating (%d/5)…",
            len(tweet_text),
            MAX_TWEET_LEN,
            attempts,
        )
    # Final safety: if still too long after retries, clamp to fit
    if market_wrap and len(market_wrap.tweet or "") > MAX_TWEET_LEN:
        market_wrap.tweet = clamp_tweet(market_wrap.tweet, MAX_TWEET_LEN)
    return market_wrap

# good default call is python poster.py us-markets
def main():
    parser = argparse.ArgumentParser(description="Generate and post tweets about various topics")
    parser.add_argument(
        "topic", 
        choices=list(TOPICS.keys()),
        help="Topic to generate content about"
    )
    
    args = parser.parse_args()
    
    topic_description = TOPICS[args.topic]
    logging.info(f"Generating tweet with OpenAI + Web Search for topic: {args.topic}\ntopic_description: {topic_description}")
    
    market_wrap = generate_market_wrap(topic=topic_description)
    print_market_wrap(market_wrap)    
    post_tweet(market_wrap.tweet)


if __name__ == "__main__":
    main()


