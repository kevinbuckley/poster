import json
import os
import sys
import argparse
from typing import Dict, Any

from dotenv import load_dotenv

from poster import post_tweet, post_reply_tweet, clamp_tweet


def load_queue(path: str = "queue.json") -> Dict[str, Any]:
    if not os.path.exists(path):
        return {"queue": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_queue(data: Dict[str, Any], path: str = "queue.json") -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def pop_and_post(account_prefix: str | None = None, path: str = "queue.json") -> bool:
    load_dotenv()
    dry_run = os.getenv("DRY_RUN", "0") == "1"
    data = load_queue(path)
    queue = data.get("queue", [])
    thread_root_id = data.get("thread_root_id")
    if not queue:
        print("Queue empty; nothing to post.")
        return False
    item = queue.pop(0)
    tweet_text = clamp_tweet(item.get("tweet", ""))

    # If we already have a thread root, reply to it; otherwise create the root
    if thread_root_id:
        tweet_id = post_reply_tweet(tweet_text, reply_to_tweet_id=thread_root_id, account_prefix=account_prefix)
    else:
        tweet_id = post_tweet(tweet_text, account_prefix=account_prefix)
        # Initialize thread root if first post succeeded
        if tweet_id and not dry_run:
            thread_root_id = tweet_id

    save_payload = {
        "queue": queue,
        "last_posted": item,
    }
    if thread_root_id:
        save_payload["thread_root_id"] = thread_root_id
    if dry_run:
        save_payload["dry_run"] = True

    save_queue(save_payload)
    print("Posted tweet id:", tweet_id)
    return tweet_id is not None


def main() -> None:
    parser = argparse.ArgumentParser(description="Post next tweet from queue")
    parser.add_argument("--account-prefix", default="", help="Env var prefix for the Twitter account (e.g., BRAND2)")
    args = parser.parse_args()
    prefix = args.account_prefix if args.account_prefix else None
    ok = pop_and_post(account_prefix=prefix)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()


