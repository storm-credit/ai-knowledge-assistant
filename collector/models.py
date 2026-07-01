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
    categories: List[str] = field(default_factory=list)   # 고정 카테고리 분류 결과
    learning: bool = False   # 학습형 출처면 True → 요약 대신 학습 카드로 재가공
