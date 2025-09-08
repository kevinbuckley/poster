import os

import openai
import pydantic
from dotenv import load_dotenv

import logging

logger = logging.getLogger(__name__)


summary_prompt = """
<Topic>
{topic}
</Topic>

<Instructions>
Only return the NewsTopicWrap object. Do not return anything else.
Do not prompt the user for anything.
Use the web_search tool to get the latest news and events.
</Instructions>

<Tweet>
Constraints: <=260 chars, no emojis/hashtags/links. Return tweet text only.
</Tweet>

<Summary>
Constraints: 3 paragraphs max. 100 word minimum. Use conversational tone.
</Summary>

<Citations>
Return a list of citations with full source URLs.
</Citations>
"""

us_market_wrap_topic = """US Markets. Focus on major indices (S&P 500, Nasdaq, Dow) and primary drivers. Give a concise, objective 
summary of the topic using web search. Look at recent news and events. Look at the week ahead and predict the most important events.
"""


class NewsTopicWrap(pydantic.BaseModel):
    tweet: str
    summary: str
    citations: list[str]


class Generator:
    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

    def generate_summary(self, topic: str=us_market_wrap_topic) -> NewsTopicWrap:
        resp = self.openai_client.responses.parse(
            model="gpt-5-nano",
            input=[{"role": "user", "content": summary_prompt.format(topic=topic)}],
            tools=[{"type": "web_search"}],
            reasoning={ "effort": "low"},
            text_format=NewsTopicWrap,
            tool_choice="auto",
        )

        logger.debug(resp)

        if not resp.output:
            raise RuntimeError("No output from OpenAI")
        if not isinstance(resp.output_parsed, NewsTopicWrap):
            raise RuntimeError("Output is not a MarketWrap")

        return resp.output_parsed



if __name__ == "__main__":
    print("Generating summary...")
    load_dotenv()
    generator = Generator()
    market_wrap = generator.generate_summary()

    print("Tweet:")
    print(market_wrap.tweet)
    print("Summary:")
    print(market_wrap.summary)

    print("Citations:")
    for citation in market_wrap.citations:
        print(citation)
