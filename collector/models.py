from dataclasses import dataclass, field
from typing import List

@dataclass
class Item:
    source_name: str
    source_type: str   # "youtube" | "newsletter"
    id: str            # 중복제거용 고유 ID
    title: str
    link: str
    published: str
    raw_text: str = ""     # 요약 대상 원문(설명/자막)
    summary: str = ""      # 채워질 요약
    tags: List[str] = field(default_factory=list)
