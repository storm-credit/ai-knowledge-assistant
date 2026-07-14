import json, os
from typing import Dict, List
from .models import Item
from .mdutil import safe_md_link
from .state import load_json_or_backup

def _empty():
    return {"items": [], "sources": [], "overview": "", "related": [], "new_since_synth": 0}

class TopicStore:
    def __init__(self, path: str):
        self.path = path
        # corrupt JSON이면 .bak 백업 후 빈 상태로 시작 (cron 영구 사망 방지)
        data = load_json_or_backup(path, {})
        self.data: Dict[str, dict] = data if isinstance(data, dict) else {}

    def topic_names(self) -> List[str]:
        return list(self.data.keys())

    def add_item(self, topic: str, item: Item) -> bool:
        t = self.data.setdefault(topic, _empty())
        if any(i["id"] == item.id for i in t["items"]):
            return False
        t["items"].append({"id": item.id, "title": item.title, "link": item.link,
                           "source": item.source_name, "date": item.published or "",
                           "summary": item.summary or ""})
        if item.source_name not in t["sources"]:
            t["sources"].append(item.source_name)
        t["new_since_synth"] += 1
        return True

    def needs_resynth(self, topic: str, threshold: int = 5) -> bool:
        return self.data.get(topic, {}).get("new_since_synth", 0) >= threshold

    def set_structure(self, topic: str, overview: str, themes: list,
                      orphans: list, related: list, window: list = None) -> None:
        """window: 합성에 실제로 넘긴 항목 리스트. 응답의 번호는 이 리스트 기준으로 매핑
        (미지정 시 전체 items — 윈도우 없이 합성한 기존 경로 호환)."""
        t = self.data[topic]
        items = window if window is not None else t["items"]
        def to_ids(idxs):
            return [items[i-1]["id"] for i in idxs if isinstance(i, int) and 1 <= i <= len(items)]
        t["overview"] = overview
        t["themes"] = [{"name": th["name"], "intro": th.get("intro", ""),
                        "item_ids": to_ids(th.get("indexes", []))} for th in themes]
        t["orphans"] = to_ids(orphans)
        t["related"] = related
        t["new_since_synth"] = 0
        t["synth_fail"] = 0          # 성공 → 실패 카운터 리셋
        t["synthesized"] = True

    def record_synth_failure(self, topic: str) -> None:
        """합성이 빈 구조를 반환한 실패 1회 기록. 2회 연속이면 new_since_synth를
        리셋해 threshold만큼 새 항목이 쌓일 때까지 재시도를 미룬다 (콜 낭비 방지)."""
        t = self.data[topic]
        t["synth_fail"] = t.get("synth_fail", 0) + 1
        if t["synth_fail"] >= 2:
            t["new_since_synth"] = 0

    def synth_backoff(self, topic: str) -> bool:
        return self.data.get(topic, {}).get("synth_fail", 0) >= 2

    def prune_topic(self, topic: str, max_items: int = 200) -> int:
        """(#23) 주제의 items가 max_items 초과 시 오래된 것부터(리스트 앞쪽) 잘라내고,
        themes/orphans의 item_ids 중 사라진 id 참조도 정리한다. 명시 호출 전용(자동 실행 없음).
        반환값: 잘라낸 항목 수."""
        t = self.data.get(topic)
        if not t:
            return 0
        items = t.get("items", [])
        if len(items) <= max_items:
            return 0
        dropped = len(items) - max_items
        t["items"] = items[-max_items:]
        kept = {it["id"] for it in t["items"]}
        for th in t.get("themes", []):
            th["item_ids"] = [i for i in th.get("item_ids", []) if i in kept]
        t["orphans"] = [i for i in t.get("orphans", []) if i in kept]
        # 남은 항목 기준으로 sources 재계산 — 잘려나간 출처가 '📌 N개 출처'에 남지 않게
        remaining = {it["source"] for it in t["items"]}
        t["sources"] = [s for s in t.get("sources", []) if s in remaining]
        return dropped

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)


import re as _re

MEMO_START = "<!-- memo:start -->"
MEMO_END = "<!-- memo:end -->"
DEFAULT_MEMO = "여기에 메모·정정을 적으세요. 자동 갱신해도 보존됩니다."

def _extract_memo(text: str):
    i = text.find(MEMO_START); j = text.find(MEMO_END)
    if i != -1 and j != -1 and j > i:
        return text[i + len(MEMO_START):j].strip()
    return None

def _replace_memo(text: str, memo: str) -> str:
    i = text.find(MEMO_START); j = text.find(MEMO_END)
    if i != -1 and j != -1 and j > i:
        return text[:i + len(MEMO_START)] + "\n" + memo + "\n" + text[j:]
    return text

def _render_item(lines: list, it: dict) -> None:
    date = (it.get("date") or "")[:10]
    lines.append(f"### {safe_md_link(it['title'], it['link'])}")
    lines.append(f"{it['source']} · {date}")
    summ = (it.get("summary") or "").strip()
    if summ:
        lines.append("")
        lines.append(summ)
    lines.append("")

def render_page(topic: str, t: dict) -> str:
    lines = [f"# {topic}", "", "> [!abstract] 개요"]
    ov = (t.get("overview") or "").strip()
    for ln in (ov.splitlines() or [""]):
        lines.append(f"> {ln}" if ln else ">")
    lines.append(f"> 📌 {len(t['sources'])}개 출처 · {len(t['items'])}건")
    lines.append("")

    by_id = {it["id"]: it for it in t["items"]}
    themes = t.get("themes") or []
    if themes:
        used = set()
        for th in themes:
            resolved = [by_id[iid] for iid in th.get("item_ids", []) if iid in by_id]
            if not resolved:
                continue   # 해결되는 항목이 하나도 없으면 헤딩 생략
            lines.append(f"## {th['name']}")
            if th.get("intro"):
                lines.append(th["intro"]); lines.append("")
            for iid in th.get("item_ids", []):
                it = by_id.get(iid)
                if it:
                    used.add(iid); _render_item(lines, it)
        orphan_ids = t.get("orphans") or []
        orphans = [by_id[i] for i in orphan_ids if i in by_id and i not in used]
        # themes/orphans에서 빠진 항목도 단신으로 흡수
        for iid, it in by_id.items():
            if iid not in used and it not in orphans and iid not in orphan_ids:
                orphans.append(it)
        if orphans:
            lines.append("## 짚어둘 단신")
            for it in orphans:
                date = (it.get("date") or "")[:10]
                lines.append(f"- {safe_md_link(it['title'], it['link'])} · {it['source']} · {date}")
            lines.append("")
    else:
        # 테마 없으면 기존 평면 렌더(폴백)
        lines.append("## 관련 소식"); lines.append("")
        for it in reversed(t["items"]):
            _render_item(lines, it)

    lines += ["## ✍️ 내 메모", MEMO_START, DEFAULT_MEMO, MEMO_END, ""]

    if t.get("related"):
        lines += ["## 관련 주제", " · ".join(f"[[{r}]]" for r in t["related"]), ""]
    return "\n".join(lines).rstrip() + "\n"

def page_filename(topic: str) -> str:
    """주제명 → 페이지 파일명. Windows 금지문자를 _로 치환 (웹측 링크 생성과 공유)."""
    safe = _re.sub(r'[\\/:*?"<>|]', "_", topic).strip() or "untitled"
    return f"{safe}.md"

def write_pages(store: "TopicStore", out_dir: str) -> list:
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    current = set()
    for topic, t in store.data.items():
        fname = page_filename(topic)
        current.add(fname)
        p = os.path.join(out_dir, fname)
        content = render_page(topic, t)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                old = f.read()
            old_memo = _extract_memo(old)
            if old_memo is not None and old_memo != DEFAULT_MEMO:
                content = _replace_memo(content, old_memo)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        paths.append(p)
    # 스테일 정리: 현재 주제도, 목차(00-목차.md)도 아닌 .md 파일 삭제 (분류 체계 바뀔 때 고아 파일 방지)
    for fn in os.listdir(out_dir):
        if fn.endswith(".md") and fn not in current and fn != "00-목차.md":
            fp = os.path.join(out_dir, fn)
            try:
                with open(fp, encoding="utf-8") as f:
                    text = f.read()
            except OSError:
                continue
            # 외부/사용자 파일(메모 마커 없음)은 건드리지 않음
            if MEMO_START not in text:
                continue
            # 사용자가 편집한 메모(기본/빈값 아님)가 있으면 보존
            memo = _extract_memo(text)
            if memo not in (None, "", DEFAULT_MEMO):
                continue
            # 우리가 생성했고 메모가 기본/빈값인 스테일 페이지만 삭제
            try:
                os.remove(fp)
            except OSError:
                pass
    return paths

def render_index(store: "TopicStore") -> str:
    lines = ["# 📚 목차", ""]
    topics = sorted(store.data.items(), key=lambda kv: len(kv[1]["items"]), reverse=True)
    for topic, t in topics:
        lines.append(f"- [[{topic}]] — {len(t['items'])}건 · {len(t['sources'])}개 출처")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"

def write_index(store: "TopicStore", out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    p = os.path.join(out_dir, "00-목차.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write(render_index(store))
    return p
