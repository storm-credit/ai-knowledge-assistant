"""Local web viewer for the AI knowledge wiki.

Serves the themed topic pages and daily digests from ``notes/`` with a clean
dark UI. Run with:  ``python -m web.app``  then open http://127.0.0.1:5000
"""
from __future__ import annotations

from flask import Flask, abort, render_template_string

from web import render

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
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:16px}
.card{display:block;background:var(--panel);border:1px solid var(--border);
  border-radius:14px;padding:18px 18px 16px;transition:transform .12s ease,border-color .12s ease}
.card:hover{transform:translateY(-2px);border-color:var(--accent);text-decoration:none}
.card .dot{width:26px;height:26px;border-radius:8px;background:var(--accent);
  opacity:.9;margin-bottom:12px}
.card .t{font-size:17px;font-weight:650;color:var(--text)}
.card .m{color:var(--muted);font-size:13px;margin-top:6px}
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
.callout{background:var(--panel);border:1px solid var(--border);border-left:3px solid var(--accent);
  border-radius:10px;padding:14px 16px;margin:14px 0}
.callout-title{font-weight:650;font-size:14px;margin-bottom:6px}
.callout-body{color:var(--muted);font-size:14px}
hr{border:none;border-top:1px solid var(--border);margin:24px 0}
/* 데일리 이전/다음 내비 */
.daynav{display:flex;justify-content:space-between;gap:12px;margin-top:32px;
  padding-top:16px;border-top:1px solid var(--border);font-size:14px}
"""

LAYOUT = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ title }} · AI 지식 비서</title>
<style>{{ css|safe }}{{ extra_css|safe }}</style></head>
<body>
<div class="topbar"><div class="inner">
  <a class="brand" href="/">🧠 AI 지식 비서 <span>wiki</span></a>
  <nav class="nav"><a href="/">주제</a><a href="/daily">데일리</a><a href="{{ today_href }}">오늘</a></nav>
</div></div>
<div class="wrap">{{ content|safe }}</div>
</body></html>"""

INDEX = """
<h1 class="page">📚 주제</h1>
<div class="sub">매일 05:00 자동 수집·요약·분류. 카드를 눌러 정리형 위키로 이동.</div>
<div class="grid">
{% for c in cards %}
  <a class="card" href="/topic/{{ c.name|urlencode }}" style="--accent:{{ c.accent }}">
    <div class="dot"></div>
    <div class="t">{{ c.name }}</div>
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


def _page(title, content, extra_css=""):
    return render_template_string(
        LAYOUT, title=title, css=BASE_CSS, extra_css=extra_css,
        content=content, today_href=_today_href(),
    )


@app.route("/")
def index():
    cards = list(render.list_topics())
    view = [
        {"name": c.name, "count": c.count, "accent": ACCENTS[i % len(ACCENTS)]}
        for i, c in enumerate(cards)
    ]
    content = render_template_string(INDEX, cards=view)
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
    app.run(host="127.0.0.1", port=5000, debug=True)
