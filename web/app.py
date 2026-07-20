"""Local web viewer for the AI knowledge wiki.

Serves the themed topic pages and daily digests from ``notes/`` with a clean
dark UI. Run with:  ``python -m web.app``  then open http://127.0.0.1:5000
"""
from __future__ import annotations

import os
from urllib.parse import quote

from flask import Flask, abort, render_template_string, request

from web import render
from collector import qa
from collector.llm import QuotaExhausted

app = Flask(__name__)

# accent colours cycled across topic cards
ACCENTS = ["#7aa2f7", "#bb9af7", "#7dcfff", "#9ece6a", "#e0af68", "#f7768e"]

BASE_CSS = """
:root{
  --bg:#0f1115; --panel:#1a1d24; --panel-2:#20242d; --border:#2a2f3a;
  --text:#e6e8ec; --muted:#9aa0aa; --link:#7aa2f7; --accent:#7aa2f7;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Malgun Gothic","Apple SD Gothic Neo",sans-serif;
  line-height:1.7;-webkit-font-smoothing:antialiased}
a{color:var(--link);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:860px;margin:0 auto;padding:32px 20px 80px}
.topbar{position:sticky;top:0;z-index:10;background:rgba(15,17,21,.82);
  backdrop-filter:blur(8px);border-bottom:1px solid var(--border)}
.topbar .inner{max-width:860px;margin:0 auto;padding:14px 20px;display:flex;
  align-items:center;gap:18px}
.brand{font-weight:700;font-size:15px;letter-spacing:.2px}
.brand span{color:var(--muted);font-weight:500}
.nav{margin-left:auto;display:flex;gap:16px;font-size:14px}
.nav a{color:var(--muted)}
.nav a:hover{color:var(--text);text-decoration:none}
h1.page{font-size:26px;margin:8px 0 4px;letter-spacing:-.3px}
.sub{color:var(--muted);font-size:14px;margin-bottom:26px}
/* #21 홈 상단 '오늘' 하이라이트 배너 */
.today-banner{display:block;background:linear-gradient(180deg,var(--panel-2),var(--panel));
  border:1px solid var(--border);border-left:3px solid var(--accent);border-radius:14px;
  padding:16px 20px;margin:4px 0 28px;transition:border-color .12s ease}
.today-banner:hover{border-color:var(--accent);text-decoration:none}
.today-banner .tb-label{color:var(--accent);font-size:13px;font-weight:700;letter-spacing:.3px;
  font-variant-numeric:tabular-nums}
.today-banner .tb-title{color:var(--text);font-size:18px;font-weight:650;margin:5px 0 8px;line-height:1.4}
.today-banner .tb-more{color:var(--muted);font-size:13px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:16px}
.card{display:block;background:var(--panel);border:1px solid var(--border);
  border-radius:14px;padding:18px 18px 16px;transition:transform .12s ease,border-color .12s ease}
.card:hover{transform:translateY(-2px);border-color:var(--accent);text-decoration:none}
.card .dot{width:26px;height:26px;border-radius:8px;background:var(--accent);
  opacity:.9;margin-bottom:12px}
.card .t{font-size:17px;font-weight:650;color:var(--text)}
.card .m{color:var(--muted);font-size:13px;margin-top:6px}
/* #20 오늘 업데이트 뱃지 — 학습 뱃지(초록)와 구분되는 파랑 */
.badge-new{font-size:10px;font-weight:700;letter-spacing:.5px;color:#7aa2f7;
  background:rgba(122,162,247,.14);border:1px solid rgba(122,162,247,.4);
  border-radius:99px;padding:1px 7px;margin-left:8px;vertical-align:2px}
/* #19 topbar 검색 */
.searchbox{display:flex}
.searchbox input{background:var(--panel-2);border:1px solid var(--border);
  border-radius:8px;color:var(--text);font-size:13px;padding:5px 10px;
  width:140px;outline:none}
.searchbox input:focus{border-color:var(--accent)}
.searchbox input::placeholder{color:var(--muted)}
@media (max-width:600px){
  .topbar .inner{gap:10px}
  .nav{gap:10px}
  .searchbox input{width:84px}
}
/* #19 검색 결과 목록 */
.hits{list-style:none;padding:0;margin:0}
.hits li{border-bottom:1px solid var(--border)}
.hits a{display:block;padding:13px 4px;color:var(--text)}
.hits a:hover{text-decoration:none}
.hits a:hover .ht{color:var(--link)}
.hits .ht{font-weight:650;font-size:15px}
.hits .hs{color:var(--muted);font-size:13.5px;margin-top:3px;overflow-wrap:anywhere}
.daily-list{list-style:none;padding:0;margin:0}
.daily-list li{border-bottom:1px solid var(--border)}
.daily-list a{display:flex;gap:14px;align-items:baseline;padding:13px 4px;color:var(--text)}
.daily-list a:hover{text-decoration:none;color:var(--link)}
.daily-list .d{font-variant-numeric:tabular-nums;color:var(--muted);font-size:14px;min-width:96px}
/* rendered markdown */
.doc{overflow-wrap:anywhere}
.doc h2{font-size:15px;margin:38px 0 10px;padding-bottom:8px;font-weight:700;
  color:var(--muted);text-transform:none;border-bottom:1px solid var(--border);
  letter-spacing:.3px}
.doc h2+p{color:var(--muted);font-size:14px;margin:-2px 0 4px}
.doc p{margin:8px 0}
.doc ul{margin:8px 0;padding-left:20px}
.doc li{margin:5px 0}
/* each article is its own card */
.doc .article{background:var(--panel);border:1px solid var(--border);
  border-radius:12px;padding:15px 18px 16px;margin:12px 0}
.doc .article:hover{border-color:#39404e}
.doc .article h3{font-size:16px;margin:0 0 3px;font-weight:650;line-height:1.45}
.doc .article h3 a{color:var(--text)}
.doc .article h3 a:hover{color:var(--link)}
.doc .article h3+p{color:var(--muted);font-size:12.5px;margin:0 0 10px;
  font-variant-numeric:tabular-nums}
.doc .article p,.doc .article li{color:#c8ccd4;font-size:14.5px}
/* learning-card labels + code */
.doc .article strong{color:var(--text);font-weight:700}
/* 학습 카드: 좌측 보더 강조 + 우상단 '학습' 뱃지 */
.doc .article--learning{position:relative;border-left:3px solid #9ece6a}
.doc .article--learning::before{content:"학습";position:absolute;top:13px;right:14px;
  font-size:11px;font-weight:650;color:#9ece6a;background:rgba(158,206,106,.12);
  border:1px solid rgba(158,206,106,.35);border-radius:99px;padding:1px 8px;line-height:1.5}
.doc .article--learning h3{padding-right:52px}
.doc code{background:#12151c;border:1px solid var(--border);border-radius:5px;
  padding:1px 5px;font-size:13px;font-family:"Cascadia Code",Consolas,monospace;color:#9ece6a}
.doc pre{background:#12151c;border:1px solid var(--border);border-radius:10px;
  padding:14px 16px;overflow-x:auto;margin:10px 0}
.doc pre code{background:none;border:none;padding:0;color:#d6dae2;font-size:13px;line-height:1.6}
/* B: '짚어둘 단신' 접이식 — 기본 접힘, 요약은 클릭 가능 */
.briefs{margin:12px 0}
.briefs summary{cursor:pointer;color:var(--muted);font-size:14px;font-weight:650;
  list-style:none;padding:8px 0;user-select:none}
.briefs summary::-webkit-details-marker{display:none}
.briefs summary::before{content:"▸ ";color:var(--accent)}
.briefs[open] summary::before{content:"▾ "}
.briefs summary:hover{color:var(--text)}
.briefs ul{margin:4px 0 8px}
.callout{background:var(--panel);border:1px solid var(--border);border-left:3px solid var(--accent);
  border-radius:10px;padding:14px 16px;margin:14px 0}
.callout-title{font-weight:650;font-size:14px;margin-bottom:6px}
.callout-body{color:var(--muted);font-size:14px}
hr{border:none;border-top:1px solid var(--border);margin:24px 0}
/* 데일리 이전/다음 내비 */
.daynav{display:flex;justify-content:space-between;gap:12px;margin-top:32px;
  padding-top:16px;border-top:1px solid var(--border);font-size:14px}
/* Q&A */
.askform{display:flex;gap:8px;margin:0 0 24px}
.askform input{flex:1;background:var(--panel-2);border:1px solid var(--border);
  border-radius:10px;color:var(--text);font-size:15px;padding:11px 14px;outline:none}
.askform input:focus{border-color:var(--accent)}
.askform button{background:var(--accent);color:#0f1115;border:none;border-radius:10px;
  font-size:14px;font-weight:700;padding:0 18px;cursor:pointer}
.answer{background:var(--panel);border:1px solid var(--border);border-left:3px solid var(--accent);
  border-radius:12px;padding:16px 18px;white-space:pre-wrap;line-height:1.7;font-size:15px}
.src-h{color:var(--muted);font-size:13px;font-weight:700;margin:22px 0 4px;letter-spacing:.3px}
"""

LAYOUT = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ title }} · AI 지식 비서</title>
<style>{{ css|safe }}{{ extra_css|safe }}</style></head>
<body>
<div class="topbar"><div class="inner">
  <a class="brand" href="/">🧠 AI 지식 비서 <span>wiki</span></a>
  <nav class="nav"><a href="/">주제</a><a href="/daily">데일리</a><a href="/learn">학습노트</a><a href="/models">모델</a><a href="/ask">질문</a><a href="{{ today_href }}">오늘</a></nav>
  <form class="searchbox" action="/search" method="get">
    <input type="search" name="q" placeholder="검색" value="{{ q }}" aria-label="노트 검색">
  </form>
</div></div>
<div class="wrap">{{ content|safe }}</div>
</body></html>"""

INDEX = """
{% if daily %}
<a class="today-banner" href="/daily/{{ daily.date }}">
  <div class="tb-label">🗓️ 오늘 · {{ daily.date }}</div>
  <div class="tb-title">{{ daily.title }}</div>
  <div class="tb-more">데일리 {{ daily_count }}일치 · 전체 보기 →</div>
</a>
{% endif %}
<h1 class="page">📚 주제</h1>
<div class="sub">매일 05:00 자동 수집·요약·분류. 카드를 눌러 정리형 위키로 이동.</div>
<div class="grid">
{% for c in cards %}
  <a class="card" href="/topic/{{ c.name|urlencode }}" style="--accent:{{ c.accent }}">
    <div class="dot"></div>
    <div class="t">{{ c.name }}{% if c.updated_today %}<span class="badge-new">NEW</span>{% endif %}</div>
    <div class="m">{{ c.count }}</div>
  </a>
{% endfor %}
</div>
"""

DAILY_INDEX = """
<h1 class="page">🗓️ 데일리</h1>
<div class="sub">날짜별 원본 요약. 총 {{ entries|length }}일치.</div>
<ul class="daily-list">
{% for e in entries %}
  <li><a href="/daily/{{ e.date }}"><span class="d">{{ e.date }}</span><span>{{ e.title }}</span></a></li>
{% endfor %}
</ul>
"""

DOC = """
<h1 class="page">{{ heading }}</h1>
{% if sub %}<div class="sub">{{ sub }}</div>{% endif %}
<div class="doc">{{ body|safe }}</div>
{% if prev or next %}
<div class="daynav">
  <span>{% if prev %}<a href="/daily/{{ prev }}">← {{ prev }}</a>{% endif %}</span>
  <span>{% if next %}<a href="/daily/{{ next }}">{{ next }} →</a>{% endif %}</span>
</div>
{% endif %}
"""


def _today_href():
    """topbar '오늘' 링크: 최신 데일리로, 데일리가 없으면 목록으로."""
    entries = render.list_dailies()
    return f"/daily/{entries[0].date}" if entries else "/daily"


def _page(title, content, extra_css="", q=""):
    return render_template_string(
        LAYOUT, title=title, css=BASE_CSS, extra_css=extra_css,
        content=content, today_href=_today_href(), q=q,
    )


@app.route("/")
def index():
    cards = list(render.list_topics())
    view = [
        {"name": c.name, "count": c.count, "accent": ACCENTS[i % len(ACCENTS)],
         "updated_today": c.updated_today}
        for i, c in enumerate(cards)
    ]
    # #21 '오늘 중심': 최신 데일리 하나를 상단 하이라이트로 (없으면 배너 생략)
    dailies = render.list_dailies()
    latest = dailies[0] if dailies else None
    content = render_template_string(INDEX, cards=view,
                                     daily=latest, daily_count=len(dailies))
    return _page("주제", content)


@app.route("/topic/<name>")
def topic(name):
    result = render.load_topic(name)
    if result is None:
        abort(404)
    heading, body = result
    content = render_template_string(DOC, heading=heading, sub="", body=body)
    return _page(heading, content)


@app.route("/daily")
def daily_index():
    entries = render.list_dailies()
    content = render_template_string(DAILY_INDEX, entries=entries)
    return _page("데일리", content)


LEARN_INDEX = """
<h1 class="page">🎓 학습 노트</h1>
<div class="sub">개념 하나를 정리+학습경로+내 적용법으로. 생성:
<code>python -m collector learn "&lt;개념&gt;"</code></div>
{% if entries %}
<ul class="daily-list">
{% for e in entries %}
  <li><a href="/learn/{{ e.name|urlencode }}"><span>{{ e.title }}</span></a></li>
{% endfor %}
</ul>
{% else %}
<div class="sub">아직 학습 노트가 없습니다.</div>
{% endif %}
"""


@app.route("/learn")
def learn_index():
    # render.LEARN_DIR를 매 요청 명시 전달 — 기본값의 def-시점 바인딩 함정 회피(테스트 주입 가능)
    entries = render.list_learn_notes(render.LEARN_DIR)
    content = render_template_string(LEARN_INDEX, entries=entries)
    return _page("학습 노트", content)


@app.route("/learn/<name>")
def learn_note(name):
    result = render.load_learn_note(name, render.LEARN_DIR)
    if result is None:
        abort(404)
    heading, body = result
    content = render_template_string(DOC, heading=heading, sub="", body=body)
    return _page(heading, content)


MODELS_INDEX = """
<h1 class="page">🛰️ 모델 업데이트</h1>
<div class="sub">Claude·OpenAI·Gemini 공식 문서 변경을 매일 감지·요약. 날짜별 기록.</div>
{% if entries %}
<ul class="daily-list">
{% for e in entries %}
  <li><a href="/models/{{ e.date }}"><span class="d">{{ e.date }}</span><span>{{ e.title }}</span></a></li>
{% endfor %}
</ul>
{% else %}
<div class="sub">아직 감지된 변경이 없습니다. (매일 cron이 변경 시에만 기록)</div>
{% endif %}
"""


@app.route("/models")
def models_index():
    entries = render.list_model_updates(render.MODEL_UPDATES_DIR)
    content = render_template_string(MODELS_INDEX, entries=entries)
    return _page("모델 업데이트", content)


@app.route("/models/<date>")
def model_update(date):
    result = render.load_model_update(date, render.MODEL_UPDATES_DIR)
    if result is None:
        abort(404)
    heading, body = result
    content = render_template_string(DOC, heading=heading, sub="", body=body)
    return _page(heading, content)


# Q&A (docs/04) — 질문/답변·출처. 질문·답변 모두 오토이스케이프(|safe 금지) XSS 안전.
ASK = """
<h1 class="page">💬 질문</h1>
<div class="sub">쌓인 노트(주제·데일리·학습노트)에 근거해 답합니다. 근거 없으면 정직하게 "없음".</div>
<form class="askform" action="/ask" method="get">
  <input type="text" name="q" value="{{ q }}" placeholder="예: 최근 메모리 시장 동향 정리해줘" aria-label="질문" autofocus>
  <button type="submit">질문</button>
</form>
{% if q %}
  {% if error %}
    <div class="sub">{{ error }}</div>
  {% else %}
    <div class="answer">{{ answer }}</div>
    {% if sources %}
    <div class="src-h">근거 출처 (답변의 [n]에 대응)</div>
    <ul class="daily-list">
    {% for s in sources %}
      <li><a href="{{ s.href }}"><span class="d">[{{ s.n }}] {{ s.kind }}</span><span>{{ s.title }}</span></a></li>
    {% endfor %}
    </ul>
    {% endif %}
  {% endif %}
{% endif %}
"""


@app.route("/ask")
def ask():
    q = request.args.get("q", "").strip()
    answer = error = None
    sources = []
    if q:
        try:
            result = qa.answer(q, topics_dir=render.TOPICS_DIR,
                               daily_dir=render.DAILY_DIR, learn_dir=render.LEARN_DIR)
            answer = result["answer"]
            sources = result["sources"]
        except QuotaExhausted:
            error = "오늘 무료 쿼터를 다 써서 지금은 답할 수 없어요. 잠시 후 다시 시도해 주세요."
        except Exception as e:            # 개별 실패 격리 — 앱이 죽지 않게
            import traceback, sys
            traceback.print_exc(file=sys.stderr)   # 상세는 서버 로그에만
            error = "답변 생성 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요."
    content = render_template_string(ASK, q=q, answer=answer, sources=sources, error=error)
    return _page("질문", content)


# #19 노트 전체 검색 — 스니펫·쿼리 echo 모두 오토이스케이프(|safe 금지)로 XSS 안전
SEARCH = """
<h1 class="page">🔎 검색</h1>
<div class="sub">{% if q %}"{{ q }}" — {{ hits|length }}건{% else %}topbar 검색창에 찾을 말을 입력하세요.{% endif %}</div>
{% if hits %}
<ul class="hits">
{% for h in hits %}
  <li><a href="{{ h.href }}">
    <div class="ht">{{ h.icon }} {{ h.title }}</div>
    <div class="hs">{{ h.snippet }}</div>
  </a></li>
{% endfor %}
</ul>
{% elif q %}
<div class="sub">결과가 없습니다.</div>
{% endif %}
"""

# kind → (아이콘, 상세 라우트 접두사)
_KIND_VIEW = {"topic": ("📚", "/topic/"), "daily": ("🗓️", "/daily/"),
              "learn": ("🎓", "/learn/")}


@app.route("/search")
def search():
    q = request.args.get("q", "")
    # 디렉터리를 매 요청 명시 전달 — 기본값의 def-시점 바인딩 함정 회피(테스트 주입 가능)
    hits = render.search_notes(q, topics_dir=render.TOPICS_DIR,
                               daily_dir=render.DAILY_DIR,
                               learn_dir=render.LEARN_DIR)
    view = []
    for h in hits:
        icon, prefix = _KIND_VIEW[h.kind]
        view.append({"icon": icon, "href": prefix + quote(h.name),
                     "title": h.title, "snippet": h.snippet})
    content = render_template_string(SEARCH, q=q.strip(), hits=view)
    return _page("검색", content, q=q.strip())


@app.route("/daily/<date>")
def daily(date):
    result = render.load_daily(date)
    if result is None:
        abort(404)
    heading, body = result
    # 목록(최신순) 기준 이전날/다음날 — 끝이면 생략
    dates = [e.date for e in render.list_dailies()]
    prev_d = next_d = None
    if date in dates:
        i = dates.index(date)
        prev_d = dates[i + 1] if i + 1 < len(dates) else None
        next_d = dates[i - 1] if i > 0 else None
    content = render_template_string(
        DOC, heading=heading, sub="", body=body, prev=prev_d, next=next_d
    )
    return _page(heading, content)


@app.errorhandler(404)
def not_found(_e):
    content = (
        '<h1 class="page">404</h1><div class="sub">그런 페이지는 없습니다. '
        '<a href="/">주제로 돌아가기</a></div>'
    )
    return _page("404", content), 404


if __name__ == "__main__":
    # 디버거(Werkzeug)는 RCE 통로가 될 수 있어 기본 꺼짐 — FLASK_DEBUG=1일 때만
    app.run(host="127.0.0.1", port=5000,
            debug=os.environ.get("FLASK_DEBUG") == "1")
