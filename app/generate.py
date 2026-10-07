import re
from openai import OpenAI
from app import config
from app.retrieve import retrieve

client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)

SYSTEM_PROMPT = """You are a helpful assistant that answers questions using ONLY the provided context.
Rules:
- If the context does not contain the answer, say: "I don't have enough information in the documents to answer that."
- Do not use outside knowledge.
- Cite the source after each claim in exactly this format: (filename, page N), using the file name and page number from the context headers.
- Only recommend a technique for a problem if the context explicitly links them. Do not repurpose advice meant for a different problem.
- Keep the answer clear and concise."""


def answer(question: str, user_id: int):
    results = retrieve(question, user_id)
    if not results:
        return "I don't have information about that in the documents.", []

    context = "\n\n".join(
        f"[{meta['source']}, page {meta['page']}]\n{text}" for text, meta, _ in results
    )
    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ],
    )
    text = response.choices[0].message.content or ""
    cited = set(re.findall(r"(?:page|p\.)\s*(\d+)", text))
    sources = sorted({(m["source"], m["page"]) for _, m, _ in results if str(m["page"]) in cited})
    return text, sources