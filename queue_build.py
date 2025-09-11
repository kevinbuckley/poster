import json
import os
from datetime import datetime, timezone
from typing import List, Dict, Any

from dotenv import load_dotenv
from openai import OpenAI


def generate_queue(topics: List[str]) -> Dict[str, Any]:
    """Generate a queue of tweets for many topics using ONE LLM call."""
    load_dotenv()
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

    # Build concise batch prompt to minimize tokens
    topic_lines = []
    for idx, t in enumerate(topics, start=1):
        topic_lines.append(f"{idx}. {t}")
    batch_prompt = (
        "Generate tweet content for the topics below.\n"
        "For EACH topic, output a JSON object with keys: topic, tweet, summary, citations (array of URLs).\n"
        "Constraints: tweet ≤260 chars, no emojis/hashtags/links; summary ≤3 short paragraphs, conversational.\n"
        "Return a JSON array ONLY (no extra text).\n\n"
        + "\n".join(topic_lines)
    )

    try:
        resp = client.responses.create(
            model="gpt-5-nano",
            input=[
                {"role": "system", "content": "You are a financial analyst. Return JSON only."},
                {"role": "user", "content": batch_prompt},
            ],
            tools=[{"type": "web_search"}],
            tool_choice="auto",
        )

        # Extract text from response
        text_chunks: List[str] = []
        for item in getattr(resp, "output", []) or []:
            for part in getattr(item, "content", []) or []:
                if getattr(part, "type", None) == "output_text":
                    text_chunks.append(getattr(part, "text", ""))
        raw_json = "\n".join([t for t in text_chunks if t]).strip()

        data = json.loads(raw_json)
        items = []
        now_iso = datetime.now(timezone.utc).isoformat()
        for obj in data:
            items.append(
                {
                    "topic": obj.get("topic", ""),
                    "tweet": obj.get("tweet", ""),
                    "summary": obj.get("summary", ""),
                    "citations": obj.get("citations", []) or [],
                    "created_at": now_iso,
                }
            )
        return {"queue": items, "generated_at": now_iso}
    except Exception as exc:
        # Fallback: minimal structure to avoid breaking workflows
        now_iso = datetime.now(timezone.utc).isoformat()
        return {
            "queue": [
                {
                    "topic": t,
                    "tweet": "Generation failed; will retry later.",
                    "summary": "",
                    "citations": [],
                    "created_at": now_iso,
                }
                for t in topics
            ],
            "generated_at": now_iso,
            "error": str(exc),
        }


def write_queue_file(queue: Dict[str, Any], path: str = "queue.json") -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)


def main() -> None:
    # Hardcoded initial topics; extend as needed
    topics = [
        "US Markets. Focus on major indices (S&P 500, Nasdaq, Dow) and primary drivers. Give a concise, objective summary of the topic using web search. Look at recent news and events. Look at the week ahead and predict the most important events.",
        "SPY Market. Proivde an options trading recommendation for SPY with specific strike prices and dates.",
    ]
    queue_data = generate_queue(topics)
    write_queue_file(queue_data, "queue.json")
    print("Queue written to queue.json with", len(queue_data.get("queue", [])), "items")


if __name__ == "__main__":
    main()


