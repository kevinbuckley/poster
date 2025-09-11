# News Topic Poster Bot — Local Quickstart

A Twitter bot that generates and posts content about various topics using OpenAI and web search.

## Requirements
- Python 3.12+
- X (Twitter) developer app with Read + Write permissions
- OpenAI API key

## Setup
1) Install dependencies using uv:
```bash
uv sync
```

2) Configure environment:
```bash
cp example.env .env
# Edit .env with your real keys
```

## Usage

The bot supports multiple topics via command line arguments:

### Available Topics
- `us-markets` - US Markets focus
- `world-markets` - World Markets focus  
- `nfl` - NFL focus
- `nba` - NBA focus
- `mlb` - MLB focus
- `tech-news` - Tech News focus

### Running the Bot

**Safe dry run (no posting):**
```bash
DRY_RUN=1 uv run python poster.py <topic>
```

**Live post (be careful):**
```bash
DRY_RUN=0 uv run python poster.py <topic>
```

**Examples:**
```bash
# Generate NFL content (dry run)
DRY_RUN=1 uv run python poster.py nfl

# Generate tech news content (live)
DRY_RUN=0 uv run python poster.py tech-news

# Show help
uv run python poster.py --help
```

## Environment Variables
- `OPENAI_API_KEY` - Your OpenAI API key
- `X_CONSUMER_KEY`, `X_CONSUMER_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET` - Twitter API credentials
- `DRY_RUN` - Set to "1" to log tweets without posting (default: "0")

## Local testing for the queue workflows

The queue system uses two scripts:
- `queue_build.py`: one LLM call generates multiple tweets and writes `queue.json`
- `queue_post.py`: posts the first tweet from `queue.json`, removes it, and rewrites the file

### 1) Prepare environment
```bash
source .venv/bin/activate || true
export OPENAI_API_KEY=your_key
export DRY_RUN=1
```

### 2) Build the queue (single LLM call for N topics)
```bash
python queue_build.py
cat queue.json  # verify a queue array exists
```

### 3) Post from the queue
- Default account (unprefixed env vars `X_*`):
```bash
python queue_post.py --account-prefix ""
```
- Prefixed account (e.g., BRAND2_X_* in env):
```bash
python queue_post.py --account-prefix BRAND2
```

Re-run `queue_post.py` to post the next item and so on. With `DRY_RUN=1`, no live posting occurs but the queue is still popped so you can test the flow.

## CI/CD (optional)
- `.github/workflows/build-queue.yml`: builds and pushes `queue.json` to `workflow-state` at 10:00 AM ET
- `.github/workflows/post-from-queue.yml`: posts at 10:02 and 10:05 AM ET and updates the queue
