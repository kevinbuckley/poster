# pip install openai>=1.40
import os
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

resp = client.responses.create(
    model="gpt-4o-mini",                        # 4o or 4o-mini support Web Search
    input=[{"role": "user",
            "content": "Give me a concise, source-cited wrap of today's SPY move and drivers. "
                       "Prefer reputable finance outlets. Include 2-4 links."}],
    tools=[{"type": "web_search"}],             # <-- enable Web Search tool
    tool_choice="auto",                         # let the model decide when to search
)

# ---- Print the answer text
text_chunks = []
for item in resp.output:
    for part in getattr(item, "content", []) or []:
        if getattr(part, "type", None) == "output_text":
            text_chunks.append(part.text)
print("\n".join(text_chunks).strip())

# ---- Print any links the tool returned (defensive parsing: schema can vary)
def extract_links(r):
    links = set()
    for item in r.output:
        # Some SDK builds attach citations/references at the item or part level
        if getattr(item, "references", None):
            for ref in item.references:
                url = getattr(ref, "url", None)
                if url: links.add(url)
        for part in getattr(item, "content", []) or []:
            # Newer schema: references on parts
            for ref in getattr(part, "references", []) or []:
                url = getattr(ref, "url", None)
                if url: links.add(url)
            # Tool results sometimes arrive as structured blocks
            if getattr(part, "type", None) == "tool_result":
                for ref in getattr(part, "references", []) or []:
                    url = getattr(ref, "url", None)
                    if url: links.add(url)
    return sorted(links)

links = extract_links(resp)
if links:
    print("\nSources:")
    for u in links:
        print("-", u)