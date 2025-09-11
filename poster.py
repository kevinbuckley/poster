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


def _get_env_with_prefix(prefix: str | None, var_suffix: str) -> str | None:
    """Read env var with optional prefix convention: '{PREFIX}_{SUFFIX}'.

    If prefix is falsy/empty, read just '{SUFFIX}'. This keeps backward-compat
    with existing unprefixed variables such as 'X_CONSUMER_KEY'.
    """
    key = f"{prefix}_{var_suffix}" if prefix else var_suffix
    return os.environ.get(key)


def _load_twitter_credentials(prefix: str | None):
    """Load credentials for a given account prefix.

    Expected suffix names (kept for backward compatibility with existing envs):
    - X_CONSUMER_KEY
    - X_CONSUMER_SECRET
    - X_ACCESS_TOKEN
    - X_ACCESS_TOKEN_SECRET

    With a prefix 'ALT', variables become: 'ALT_X_CONSUMER_KEY', ...
    """
    consumer_key = _get_env_with_prefix(prefix, "X_CONSUMER_KEY")
    consumer_secret = _get_env_with_prefix(prefix, "X_CONSUMER_SECRET")
    access_token = _get_env_with_prefix(prefix, "X_ACCESS_TOKEN")
    access_secret = _get_env_with_prefix(prefix, "X_ACCESS_TOKEN_SECRET")
    if not all([consumer_key, consumer_secret, access_token, access_secret]):
        return None
    return {
        "consumer_key": consumer_key,
        "consumer_secret": consumer_secret,
        "access_token": access_token,
        "access_secret": access_secret,
    }


def get_responder_topic(primary_topic: str) -> str:
    """Get responder topic based on primary topic for conversation mode."""
    responder_mapping = {
        "us-markets": "Market Analysis. Provide contrarian or analytical perspective on market movements, challenge assumptions, or offer deeper insights.",
        "us-markets-weekly-wrap": "Weekly Market Review. Add your own take on the week's performance, highlight what others missed, or provide alternative interpretation.",
        "us-markets-next-week-events": "Market Outlook. Share your predictions, concerns, or different angle on upcoming events.",
        "world-markets": "Global Market Commentary. Offer international perspective or challenge the US-centric view.",
        "nfl": "Sports Analysis. Provide expert commentary, stats, or contrarian takes on the games and performances.",
        "nba": "Basketball Analysis. Share insights, player analysis, or different perspective on the games.",
        "mlb": "Baseball Analysis. Offer expert commentary, stats, or contrarian takes on the games and performances.",
        "tech-news": "Tech Commentary. Provide deeper analysis, challenge hype, or offer contrarian tech perspectives.",
        "us-options": "Options Analysis. Provide expert options commentary, risk assessment, or alternative strategies."
    }
    return responder_mapping.get(primary_topic, "General Commentary. Provide thoughtful response and analysis.")

# Text Helpers
def clamp_tweet(text: str, max_len: int = 280) -> str:
    text = " ".join((text or "").strip().split())
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def get_twitter_clients(account_prefix: str | None = None):
    """Get Twitter API clients for specified account prefix (None for unprefixed).

    Example prefixes: 'ALT', 'BRAND2'. This will read 'ALT_X_CONSUMER_KEY', etc.
    If prefix is None/empty, it reads unprefixed vars for backward compatibility.
    """
    creds = _load_twitter_credentials(account_prefix)
    if not creds:
        raise RuntimeError(f"Missing Twitter credentials for prefix '{account_prefix or ''}'")

    auth = tweepy.OAuth1UserHandler(
        creds["consumer_key"],
        creds["consumer_secret"],
        creds["access_token"],
        creds["access_secret"],
    )
    twitter_client = tweepy.API(auth)
    twitter_client_v2 = tweepy.Client(
        consumer_key=creds["consumer_key"],
        consumer_secret=creds["consumer_secret"],
        access_token=creds["access_token"],
        access_token_secret=creds["access_secret"],
    )
    return twitter_client, twitter_client_v2


def post_tweet(text: str, account_prefix: str | None = None) -> str | None:
    """Post the tweet to Twitter, or log if DRY_RUN is enabled. Returns tweet ID."""
    if DRY_RUN:
        logging.info("[DRY RUN] Tweet would be (prefix=%s): %s", account_prefix or "", text)
        return "dry_run_tweet_id"

    twitter_client, twitter_client_v2 = get_twitter_clients(account_prefix)

    # Try v2 first
    if twitter_client_v2 is not None:
        try:
            resp = twitter_client_v2.create_tweet(text=text)
            tweet_id = None
            if hasattr(resp, "data"):
                data_obj = resp.data
                if isinstance(data_obj, dict):
                    tweet_id = data_obj.get("id")
                else:
                    tweet_id = getattr(data_obj, "id", None)
            logging.info("Tweet posted via v2 (prefix=%s): %s", account_prefix or "", getattr(resp, "data", resp))
            return tweet_id
        except Exception as exc:
            logging.warning("v2 create_tweet failed (prefix=%s) (%s). Falling back to v1.1.", account_prefix or "", exc)

    # Fallback to v1.1
    if twitter_client is not None:
        try:
            resp = twitter_client.update_status(status=text)
            tweet_id = resp.id_str if hasattr(resp, "id_str") else None
            logging.info("Tweet posted via v1.1 (prefix=%s): %s", account_prefix or "", text)
            return tweet_id
        except Exception as exc:
            logging.error("Failed to post tweet (prefix=%s): %s", account_prefix or "", exc)
            return None

    return None


def post_reply_tweet(text: str, reply_to_tweet_id: str, account_prefix: str | None = None) -> str | None:
    """Post a reply tweet to Twitter."""
    if DRY_RUN:
        logging.info("[DRY RUN] Reply tweet would be (prefix=%s): %s", account_prefix or "", text)
        return "dry_run_reply_id"

    twitter_client, twitter_client_v2 = get_twitter_clients(account_prefix)

    # Try v2 first
    if twitter_client_v2 is not None:
        try:
            resp = twitter_client_v2.create_tweet(text=text, in_reply_to_tweet_id=reply_to_tweet_id)
            tweet_id = None
            if hasattr(resp, "data"):
                data_obj = resp.data
                if isinstance(data_obj, dict):
                    tweet_id = data_obj.get("id")
                else:
                    tweet_id = getattr(data_obj, "id", None)
            logging.info("Reply posted via v2 (prefix=%s): %s", account_prefix or "", getattr(resp, "data", resp))
            return tweet_id
        except Exception as exc:
            logging.warning("v2 create_tweet reply failed (prefix=%s) (%s). Falling back to v1.1.", account_prefix or "", exc)

    # Fallback to v1.1
    if twitter_client is not None:
        try:
            resp = twitter_client.update_status(status=text, in_reply_to_status_id=reply_to_tweet_id)
            tweet_id = resp.id_str if hasattr(resp, "id_str") else None
            logging.info("Reply posted via v1.1 (prefix=%s): %s", account_prefix or "", text)
            return tweet_id
        except Exception as exc:
            logging.error("Failed to post reply (prefix=%s): %s", account_prefix or "", exc)
            return None

    return None


def check_secondary_twitter_api_keys():
    """Check if secondary Twitter API keys are set."""
    if os.getenv("X2_CONSUMER_KEY") is None or os.getenv("X2_CONSUMER_SECRET") is None or os.getenv("X2_ACCESS_TOKEN") is None or os.getenv("X2_ACCESS_TOKEN_SECRET") is None:
        return False
    return True


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


def generate_response_tweet(original_tweet: str, responder_topic: str) -> NewsTopicWrap:
    """Generate a response tweet that replies to the original tweet."""
    generator = Generator()
    
    # Create response prompt that includes the original tweet
    response_prompt = f"{responder_topic}\n\nRespond to this tweet: '{original_tweet}'\nMake it conversational and add your own perspective."
    
    attempts = 0
    market_wrap: NewsTopicWrap | None = None
    while attempts < 5:
        market_wrap = generator.generate_summary(response_prompt)
        tweet_text = market_wrap.tweet or ""
        if len(tweet_text) <= MAX_TWEET_LEN:
            break
        attempts += 1
        logging.info(
            "Response tweet too long (%d chars > %d). Regenerating (%d/5)…",
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
    parser.add_argument(
        "--conversation",
        action="store_true",
        help="Enable conversation mode with two accounts (primary posts, secondary responds)"
    )
    
    args = parser.parse_args()
    
    topic_description = TOPICS[args.topic]
    logging.info(f"Generating tweet with OpenAI + Web Search for topic: {args.topic}\ntopic_description: {topic_description}")
    
    # Generate and post primary tweet
    market_wrap = generate_market_wrap(topic=topic_description)
    print_market_wrap(market_wrap)    
    primary_tweet_id = post_tweet(market_wrap.tweet, account="primary")
    
    # If conversation mode is enabled, generate and post response
    if args.conversation and primary_tweet_id:
        logging.info("Generating response tweet...")
        responder_topic = get_responder_topic(args.topic)
        response_wrap = generate_response_tweet(market_wrap.tweet, responder_topic)
        
        print(f"\n{'='*50}")
        print("RESPONSE TWEET:")
        print_market_wrap(response_wrap)
        
        reply_tweet_id = post_reply_tweet(response_wrap.tweet, primary_tweet_id, account="secondary")
        if reply_tweet_id:
            logging.info("Conversation posted successfully!")
        else:
            logging.warning("Failed to post response tweet")
    elif args.conversation:
        logging.warning("Conversation mode enabled but primary tweet failed, skipping response")


if __name__ == "__main__":
    main()


