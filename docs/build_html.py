"""검증 문서(Markdown) → 단일 자체완결 HTML 패키지 변환.

docs/*.md 를 사이드바 목차가 있는 하나의 인쇄 친화적 HTML(`validation-package.html`)로
묶는다. 외부 CDN 없음 — 파일 하나만 공유하면 된다.

사용:  python docs/build_html.py
의존:  pip install markdown
"""
from __future__ import annotations

import datetime as _dt
import html as _html
import pathlib
import re

import markdown

BASE = pathlib.Path(__file__).parent

# (파일명, 앵커 id, 사이드바 라벨) — 읽기 순서
DOCS = [
    ("README.md", "doc-readme", "문서 인덱스"),
    ("00-validation-plan.md", "doc-00", "00 · 검증 계획 (VP)"),
    ("01-user-requirements.md", "doc-01", "01 · 사용자 요구사항 (URS)"),
    ("02-functional-spec.md", "doc-02", "02 · 기능 명세 (FS)"),
    ("03-design-spec.md", "doc-03", "03 · 설계 명세 (DS)"),
    ("04-risk-assessment.md", "doc-04", "04 · 위험 평가 (RA)"),
    ("05-utck-reference-analysis.md", "doc-05", "05 · UTCk 기준 분석 (REF)"),
    ("06-traceability-matrix.md", "doc-06", "06 · 추적성 매트릭스 (RTM)"),
    ("07-iq-protocol.md", "doc-07", "07 · IQ 프로토콜"),
    ("08-oq-protocol.md", "doc-08", "08 · OQ 프로토콜"),
    ("09-pq-protocol.md", "doc-09", "09 · PQ 프로토콜"),
    ("10-kriss-conformance-report.md", "doc-10", "10 · KRISS 정합성 보고서 (VSR)"),
    ("11-regulatory-best-practices.md", "doc-11", "11 · 규제·모범사례 (REG)"),
    ("manual-device-ntp-setup.md", "doc-manual", "운영 매뉴얼 · 장비 NTP 설정"),
    ("field-validation-runbook.md", "doc-runbook", "런북 · 현장 검증 실행"),
]
FILEMAP = {fn: anc for fn, anc, _ in DOCS}

_MD_LINK = re.compile(r'href="([0-9A-Za-z\-]+\.md)(#[^"]*)?"')
_STRIKE = re.compile(r"~~(.+?)~~")


def _convert(md_text: str) -> str:
    md_text = _STRIKE.sub(r"<del>\1</del>", md_text)  # ~~취소선~~ 지원
    out = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "sane_lists", "attr_list", "toc"],
    )

    def _relink(m: re.Match) -> str:
        anc = FILEMAP.get(m.group(1))
        return f'href="#{anc}"' if anc else m.group(0)

    return _MD_LINK.sub(_relink, out)


CSS = """
:root{--navy:#1a2b4a;--gold:#b8860b;--ink:#222;--muted:#667;--line:#e3e6ec;--bg:#f6f7f9;}
*{box-sizing:border-box;}
body{margin:0;font-family:-apple-system,'Segoe UI',Roboto,'Malgun Gothic',sans-serif;
  color:var(--ink);background:var(--bg);line-height:1.65;}
a{color:var(--navy);text-decoration:none;}
a:hover{text-decoration:underline;}
nav.sidebar{position:fixed;top:0;left:0;width:264px;height:100vh;overflow-y:auto;
  background:var(--navy);color:#cdd6e6;padding:1.4rem 0;}
nav.sidebar .brand{padding:0 1.3rem 1rem;border-bottom:1px solid #2e4368;}
nav.sidebar .brand h1{font-size:1.05rem;color:#fff;margin:0 0 .25rem;}
nav.sidebar .brand p{font-size:.72rem;color:#8fa0bd;margin:0;}
nav.sidebar a{display:block;color:#cdd6e6;font-size:.83rem;padding:.5rem 1.3rem;
  border-left:3px solid transparent;}
nav.sidebar a:hover{background:#223a5e;color:#fff;text-decoration:none;}
nav.sidebar a.active{background:rgba(184,134,11,.16);border-left-color:var(--gold);color:#fff;}
main{margin-left:264px;padding:2.4rem 3rem 6rem;max-width:980px;}
.cover{background:var(--navy);color:#fff;border-radius:12px;padding:2rem 2.2rem;margin-bottom:2.5rem;}
.cover h1{margin:.1rem 0 .4rem;font-size:1.7rem;}
.cover .sub{color:#aebbd4;font-size:.95rem;}
.cover .disclaimer{margin-top:1rem;font-size:.8rem;color:#d8c089;background:rgba(184,134,11,.12);
  border:1px solid rgba(184,134,11,.4);border-radius:8px;padding:.6rem .85rem;}
.cover .meta{margin-top:.8rem;font-size:.76rem;color:#8fa0bd;}
section.doc{background:#fff;border:1px solid var(--line);border-radius:12px;
  padding:1.8rem 2.1rem;margin-bottom:2rem;}
section.doc>h1:first-child{margin-top:0;}
h1,h2,h3,h4{color:var(--navy);line-height:1.3;}
h1{font-size:1.5rem;border-bottom:3px solid var(--gold);padding-bottom:.35rem;}
h2{font-size:1.2rem;margin-top:1.8rem;border-bottom:1px solid var(--line);padding-bottom:.25rem;}
h3{font-size:1.02rem;margin-top:1.3rem;}
table{border-collapse:collapse;width:100%;margin:1rem 0;font-size:.84rem;}
th,td{border:1px solid var(--line);padding:.5rem .65rem;text-align:left;vertical-align:top;}
th{background:var(--navy);color:#fff;font-weight:600;}
tbody tr:nth-child(even){background:#f7f9fc;}
code{background:#eef1f6;padding:.1rem .35rem;border-radius:4px;font-size:.85em;
  font-family:'Cascadia Code',Consolas,monospace;}
pre{background:#0f1b2e;color:#d6e0f0;padding:1rem 1.2rem;border-radius:8px;overflow:auto;
  font-size:.8rem;line-height:1.5;}
pre code{background:none;color:inherit;padding:0;}
blockquote{margin:1rem 0;padding:.6rem 1rem;background:#fbf7ec;border-left:4px solid var(--gold);
  color:#5b4a1a;border-radius:0 6px 6px 0;}
blockquote p{margin:.3rem 0;}
del{color:#9aa0aa;}
ul,ol{padding-left:1.4rem;}
li{margin:.2rem 0;}
hr{border:none;border-top:1px solid var(--line);margin:2rem 0;}
.totop{position:fixed;right:1.4rem;bottom:1.4rem;background:var(--navy);color:#fff;
  width:42px;height:42px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-size:1.1rem;box-shadow:0 2px 8px rgba(0,0,0,.25);}
.totop:hover{background:var(--gold);text-decoration:none;}
@media print{
  nav.sidebar,.totop{display:none;}
  body{background:#fff;}
  main{margin:0;max-width:none;padding:0;}
  .cover,section.doc{border:none;border-radius:0;box-shadow:none;}
  section.doc{padding:0;margin:0 0 1.5rem;page-break-before:always;}
  section#doc-readme{page-break-before:avoid;}
  th{background:#1a2b4a !important;-webkit-print-color-adjust:exact;print-color-adjust:exact;}
  pre{background:#f0f0f0;color:#111;border:1px solid #ccc;}
}
@media(max-width:820px){
  nav.sidebar{position:static;width:100%;height:auto;}
  main{margin-left:0;padding:1.4rem;}
}
"""

JS = """
const links=[...document.querySelectorAll('nav.sidebar a')];
const map=new Map(links.map(a=>[a.getAttribute('href').slice(1),a]));
const obs=new IntersectionObserver((es)=>{
  es.forEach(e=>{if(e.isIntersecting){
    links.forEach(a=>a.classList.remove('active'));
    const a=map.get(e.target.id); if(a)a.classList.add('active');
  }});
},{rootMargin:'-10% 0px -80% 0px'});
document.querySelectorAll('section.doc').forEach(s=>obs.observe(s));
"""


def build() -> pathlib.Path:
    nav_items, sections = [], []
    for fn, anc, label in DOCS:
        text = (BASE / fn).read_text(encoding="utf-8")
        nav_items.append(f'<a href="#{anc}">{_html.escape(label)}</a>')
        sections.append(f'<section id="{anc}" class="doc">\n{_convert(text)}\n</section>')

    today = _dt.date.today().isoformat()
    doc = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>pharma-ntp-standard · 검증 문서 패키지</title>
<style>{CSS}</style>
</head>
<body>
<nav class="sidebar">
  <div class="brand">
    <h1>pharma-ntp-standard</h1>
    <p>검증 문서 패키지 · GAMP 5 V 모델</p>
  </div>
  {''.join(nav_items)}
</nav>
<main>
  <header class="cover">
    <div class="sub">제약(GxP) NTP 시간 표준 — KRISS UTC(k) 준거 모니터링·검증</div>
    <h1>컴퓨터 시스템 검증(CSV) 문서 패키지</h1>
    <div class="sub">GAMP 5 기반 V 모델 산출물 · 시스템 영향도: 직접 영향 시스템</div>
    <div class="disclaimer">⚠ 공식 인증 제품이 아니라 UTCk에 <em>준하는</em> 오픈소스 참조 구현입니다.
      실제 규제 환경 적용 시 별도 검증이 필요합니다.</div>
    <div class="meta">생성일 {today} · 자동 변환(build_html.py)</div>
  </header>
  {''.join(sections)}
</main>
<a class="totop" href="#" title="맨 위로">↑</a>
<script>{JS}</script>
</body>
</html>
"""
    out = BASE / "validation-package.html"
    out.write_text(doc, encoding="utf-8")
    return out


if __name__ == "__main__":
    path = build()
    print(f"생성됨: {path}  ({len(DOCS)}개 문서, {path.stat().st_size:,} bytes)")
