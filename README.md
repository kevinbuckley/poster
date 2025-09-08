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

## CI/CD (optional)
- See `.github/workflows/daily-tweet.yml`. Add the same secrets in your repo and enable the schedule.
- Update the workflow to specify the desired topic: `uv run python poster.py <topic>`
