"""마크다운 렌더 공용 유틸 — 피드 데이터를 안전하게 링크로 만든다."""
from urllib.parse import urlparse

_SAFE_SCHEMES = ("http", "https")


def safe_md_link(title: str, link: str) -> str:
    """제목·링크를 안전한 마크다운 링크 문자열로.

    - link가 http/https 스킴이 아니면(javascript: 등) 링크 없이 제목만.
    - 제목의 '['']'는 이스케이프해 링크 구조 주입을 막는다.
    - link의 괄호는 %28/%29로 인코딩해 URL이 중간에 끊기지 않게 한다.
    """
    safe_title = (title or "").replace("[", "\\[").replace("]", "\\]")
    url = (link or "").strip()
    if urlparse(url).scheme.lower() not in _SAFE_SCHEMES:
        return safe_title
    url = url.replace("(", "%28").replace(")", "%29")
    return f"[{safe_title}]({url})"
