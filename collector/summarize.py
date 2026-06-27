import os
from .models import Item

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai/"

def _default_client():
    try:
        from dotenv import load_dotenv
        load_dotenv()  # 프로젝트 루트의 .env에서 GEMINI_API_KEY 로드 (있으면)
    except ImportError:
        pass
    from openai import OpenAI
    return OpenAI(api_key=os.environ["GEMINI_API_KEY"], base_url=GEMINI_BASE)

PROMPT = (
    "다음 콘텐츠를 한국어로 3줄 이내로 핵심만 요약하고, 마지막 줄에 "
    "관련 주제 태그를 #해시태그 형식으로 3개 이하 붙여라. "
    "원문에 있는 내용만 사용하고, 없는 사실은 절대 지어내지 마라.\n\n"
    "제목: {title}\n출처: {source}\n내용:\n{body}"
)

def summarize_item(item: Item, client=None, model: str = "gemini-2.5-flash") -> Item:
    client = client or _default_client()
    body = (item.raw_text or item.title)[:6000]
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": PROMPT.format(
            title=item.title, source=item.source_name, body=body)}],
    )
    item.summary = resp.choices[0].message.content.strip()
    return item
