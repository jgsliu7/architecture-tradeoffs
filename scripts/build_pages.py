#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a paged HTML review site from the book Markdown sources.

Output:
  dist/index.html
  dist/chapters/*.html

Markdown and SVG remain the source of truth. SVG diagrams are inlined so each
chapter page is self-contained and images display without copying assets.
"""
import os
import shutil
import sys

from build_html import CHAPTERS, JS, convert, load_svg, link_xrefs, new_registry, validate_site

ROOT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
CHAPTER_DIR = os.path.join(DIST, "chapters")

# 内部审阅版保留“分页审阅版”称谓；公开仓库构建时设置 BOOK_EDITION=public。
PUBLIC_EDITION = os.environ.get("BOOK_EDITION", "").strip().lower() == "public"
BOOK_TITLE = "架构取舍之道：从 Redis、MySQL、Kafka 理解系统设计"
EDITION_LABEL = "在线阅读版" if PUBLIC_EDITION else "分页审阅版"
PAGE_TITLE = BOOK_TITLE if PUBLIC_EDITION else BOOK_TITLE + "（分页审阅版）"


PAGE_CSS = """
*{box-sizing:border-box}
:root{--ink:#1f2328;--mute:#57606a;--line:#d8dee4;--accent:#4f46e5;--bg:#fff;--soft:#f6f8fa}
html{scroll-behavior:smooth}
body{margin:0;font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans CJK SC",system-ui,sans-serif;color:var(--ink);background:#fff;line-height:1.8;font-size:16px}
.layout{display:grid;grid-template-columns:var(--toc-w,292px) 6px 1fr;max-width:1340px;margin:0 auto;transition:grid-template-columns .2s}
body.toc-dragging .layout{transition:none}
nav.toc{position:sticky;top:0;align-self:start;height:100vh;overflow-y:auto;padding:24px 16px 24px 8px;font-size:14px;min-width:0}
main.content{min-width:0}
.toc-drag{position:sticky;top:0;align-self:start;height:100vh;cursor:col-resize;background:var(--line);transition:background .15s}
.toc-drag:hover,.toc-drag.active{background:var(--accent)}
body.toc-dragging{user-select:none;cursor:col-resize}
.toc-collapse{position:absolute;top:16px;right:8px;border:1px solid var(--line);background:#fff;color:var(--mute);border-radius:6px;width:24px;height:24px;font-size:13px;line-height:1;cursor:pointer;padding:0}
.toc-collapse:hover{color:var(--accent);border-color:var(--accent)}
.toc-expand{display:none;position:fixed;left:0;top:120px;z-index:55;border:1px solid var(--line);border-left:none;background:#fff;color:var(--mute);border-radius:0 8px 8px 0;padding:10px 6px;font-size:14px;cursor:pointer;box-shadow:2px 2px 8px rgba(0,0,0,.08)}
.toc-expand:hover{color:var(--accent)}
body.toc-collapsed .layout{grid-template-columns:1fr}
body.toc-collapsed nav.toc,body.toc-collapsed .toc-drag{display:none}
body.toc-collapsed .toc-expand{display:block}
.toc-title{font-weight:700;font-size:15px;color:var(--accent);margin:0 0 4px 8px}
.toc-title a{color:inherit;text-decoration:none}
.toc-sub{font-size:12px;color:var(--mute);margin:0 0 16px 8px}
nav.toc ul{list-style:none;padding:0;margin:0}
nav.toc li>a{display:block;padding:5px 10px;border-radius:6px;color:var(--ink);text-decoration:none;line-height:1.5}
nav.toc li>a:hover{background:var(--soft)}
nav.toc li.active>a{background:#eef2ff;color:var(--accent);font-weight:600}
nav.toc li.nav-sub>a{padding-left:22px;font-size:13px;color:var(--mute)}
.content{padding:32px 48px 120px;max-width:1000px;overflow-wrap:anywhere}
.chapter-meta{color:var(--mute);font-size:13px;margin:0 0 18px}
.page-nav{display:flex;justify-content:space-between;gap:16px;margin:40px 0 0;padding-top:20px;border-top:1px solid var(--line)}
.page-nav a{display:block;max-width:48%;padding:10px 12px;border:1px solid var(--line);border-radius:8px;text-decoration:none;color:var(--ink);background:var(--soft);line-height:1.5}
.page-nav a:hover{border-color:var(--accent);color:var(--accent)}
.page-nav .empty{visibility:hidden}
h1,h2,h3,h4{line-height:1.35;color:var(--ink);font-weight:700}
h1{font-size:1.9em;margin:0 0 .6em;padding-bottom:.3em}
h2{font-size:1.42em;margin:1.8em 0 .6em}
h3{font-size:1.18em;margin:1.5em 0 .5em}
h4{font-size:1.04em;margin:1.3em 0 .4em;color:#24292f}
p{margin:0 0 1em}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
strong{font-weight:700;color:#111827}
em{font-style:normal;color:var(--mute)}
hr{border:none;border-top:1px solid var(--line);margin:2.4em 0}
code{font-family:"SF Mono",Menlo,Consolas,monospace;background:var(--soft);padding:.12em .4em;border-radius:4px;font-size:.9em;color:#24292f}
pre{background:#1e1e2e;color:#cdd6f4;padding:16px 18px;border-radius:8px;overflow-x:auto;line-height:1.55}
pre code{background:none;color:inherit;padding:0;font-size:.86em}
blockquote{margin:1.2em 0;padding:.6em 1em .6em 1.1em;border-left:4px solid var(--accent);background:#f7f8ff;color:#343a40;border-radius:0 6px 6px 0}
blockquote strong{color:var(--accent)}
ul,ol{margin:0 0 1em;padding-left:1.7em}
li{margin:.25em 0}
.table-wrap{overflow-x:auto;margin:1.2em 0}
table{border-collapse:collapse;width:100%;font-size:.94em}
th,td{border:1px solid var(--line);padding:8px 12px;text-align:left;vertical-align:top}
thead th{background:#eef2ff;color:#3730a3;font-weight:600}
tbody tr:nth-child(even){background:#fafbfd}
figure.fig{margin:2em calc((100% - 1000px)/2);text-align:center}
.svg-wrap,.inline-svg{display:block;width:100%}
figure.fig svg,.inline-svg svg,.svg-wrap svg,figure.fig img{width:100%;max-width:1000px;height:auto;display:block;margin:0 auto}
figcaption{color:var(--mute);font-size:.92em;margin-top:.6em;line-height:1.5}
.toc-toggle{display:none}
.review-index{display:grid;gap:12px;margin:24px 0 0}
.review-index a{display:block;padding:14px 16px;border:1px solid var(--line);border-radius:8px;color:var(--ink);text-decoration:none;background:#fff}
.review-index a:hover{border-color:var(--accent);background:#f7f8ff}
.review-index strong{display:block;color:var(--ink)}
.review-index span{display:block;color:var(--mute);font-size:13px;margin-top:2px}
@media(max-width:1200px){figure.fig{margin:2em auto}}
@media(max-width:900px){
  .layout{grid-template-columns:1fr}
  nav.toc{position:fixed;left:0;top:0;width:292px;background:#fff;z-index:50;transform:translateX(-100%);transition:transform .2s;box-shadow:2px 0 12px rgba(0,0,0,.08)}
  nav.toc.open{transform:translateX(0)}
  body.toc-collapsed nav.toc{display:block}
  .toc-drag,.toc-collapse,.toc-expand{display:none!important}
  .content{padding:20px 18px 80px;max-width:100%;min-width:0}
  .toc-toggle{display:inline-block;position:fixed;right:16px;bottom:16px;z-index:60;background:var(--accent);color:#fff;border:none;border-radius:50%;width:48px;height:48px;font-size:13px;box-shadow:0 4px 12px rgba(0,0,0,.2);cursor:pointer}
  .backdrop{display:none;position:fixed;inset:0;background:rgba(0,0,0,.3);z-index:40}
  .backdrop.show{display:block}
  /* 窄屏宽图改为容器内横向滚动，文字保持可读 */
  .svg-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}
  figure.fig svg{min-width:760px}
}
@media print{a.xref{color:inherit}}
"""

# 分页站点专属交互：目录分隔条拖拽调宽 + 目录收起/展开，状态存 localStorage。
# 元素只存在于 page_shell；单页构建（build_html.py）不含这些 id，不受影响。
PAGES_JS = """
(function(){
  var layout=document.querySelector('.layout'),drag=document.getElementById('tocDrag');
  var colBtn=document.getElementById('tocCollapse'),expBtn=document.getElementById('tocExpand');
  var KEY_W='paged.tocW',KEY_C='paged.tocCollapsed';
  try{
    var w=localStorage.getItem(KEY_W);
    if(w&&layout)layout.style.setProperty('--toc-w',w);
    if(localStorage.getItem(KEY_C)==='1')document.body.classList.add('toc-collapsed');
  }catch(e){}
  if(colBtn){colBtn.addEventListener('click',function(){
    document.body.classList.add('toc-collapsed');
    try{localStorage.setItem(KEY_C,'1');}catch(e){}
  });}
  if(expBtn){expBtn.addEventListener('click',function(){
    document.body.classList.remove('toc-collapsed');
    try{localStorage.setItem(KEY_C,'0');}catch(e){}
  });}
  if(drag&&layout){
    drag.addEventListener('pointerdown',function(e){
      e.preventDefault();
      document.body.classList.add('toc-dragging');
      drag.classList.add('active');
      function mv(ev){
        var left=layout.getBoundingClientRect().left;
        var w=Math.min(Math.max(ev.clientX-left,200),520);
        layout.style.setProperty('--toc-w',Math.round(w)+'px');
      }
      function up(){
        document.body.classList.remove('toc-dragging');
        drag.classList.remove('active');
        try{localStorage.setItem(KEY_W,layout.style.getPropertyValue('--toc-w'));}catch(e2){}
        window.removeEventListener('pointermove',mv);
        window.removeEventListener('pointerup',up);
      }
      window.addEventListener('pointermove',mv);
      window.addEventListener('pointerup',up);
    });
  }
})();
"""


def html_escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def slug_for(index, rel):
    if rel.endswith("00-preface.md"):
        return "00-preface.html"
    if rel.endswith("10-epilogue.md"):
        return "10-epilogue.html"
    parts = rel.split("/")
    if len(parts) > 1:
        return parts[1] + ".html"
    return "%02d.html" % index


def load_chapters():
    items = []
    counter = [0]
    registry = new_registry()
    for idx, (rel, diag) in enumerate(CHAPTERS):
        path = os.path.join(ROOT, rel)
        md = open(path, encoding="utf-8").read()
        svgmap = {}
        gptmap = {}
        if diag and os.path.isdir(os.path.join(ROOT, diag)):
            for fn in sorted(os.listdir(os.path.join(ROOT, diag))):
                if fn.endswith(".svg"):
                    prefix = fn.replace(".svg", "").replace("-", "_")
                    svg = load_svg(os.path.join(ROOT, diag, fn), prefix)
                    svgmap["diagrams/" + fn] = '<div class="svg-wrap">' + svg + "</div>"
                elif fn.endswith('-gpt.png'):
                    gptmap['diagrams/' + fn] = '../../' + diag + '/' + fn
        body, heads = convert(md, svgmap, gptmap, counter, ('../../' + diag) if diag else '', chidx=idx, registry=registry)
        title = next((t for (lvl, t, _hid) in heads if lvl == 1), os.path.basename(rel))
        items.append({
            "index": idx,
            "rel": rel,
            "file": slug_for(idx, rel),
            "title": title,
            "body": body,
            "heads": heads,
        })
    return items, registry


def nav_html(items, current_file=None, depth="chapter"):
    prefix = "" if depth == "root" else "../"
    out = ['<ul>']
    out.append('<li><a href="%sindex.html">首页目录</a></li>' % prefix)
    for item in items:
        active = ' class="active"' if item["file"] == current_file else ""
        href = "%schapters/%s" % (prefix, item["file"]) if depth == "root" else item["file"]
        out.append("<li%s><a href=\"%s\">%s</a>" % (active, href, html_escape(item["title"])))
        if item["file"] == current_file:
            subs = [h for h in item["heads"] if h[0] == 2]
            if subs:
                out.append("<ul>")
                for (_lvl, text, hid) in subs:
                    out.append('<li class="nav-sub"><a href="#%s">%s</a></li>' % (hid, html_escape(text)))
                out.append("</ul>")
        out.append("</li>")
    out.append("</ul>")
    return "\n".join(out)


def page_shell(title, nav, main, depth="chapter"):
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s</title>
<style>%s</style>
</head>
<body>
<div class="backdrop" id="bd"></div>
<button class="toc-toggle">目录</button>
<button class="toc-expand" id="tocExpand" title="展开目录">»</button>
<div class="layout">
<nav class="toc" id="toc">
  <button class="toc-collapse" id="tocCollapse" title="收起目录">«</button>
  <div class="toc-title"><a href="%sindex.html">架构取舍之道</a></div>
  <div class="toc-sub">%s</div>
  %s
</nav>
<div class="toc-drag" id="tocDrag" title="拖拽调整目录宽度"></div>
<main class="content">
%s
</main>
</div>
<script>%s</script>
<script>%s</script>
</body>
</html>""" % (html_escape(title), PAGE_CSS, "" if depth == "root" else "../", EDITION_LABEL, nav, main, JS, PAGES_JS)


def build_index(items):
    cards = []
    for item in items:
        cards.append(
            '<a href="chapters/%s"><strong>%s</strong><span>%s</span></a>'
            % (item["file"], html_escape(item["title"]), html_escape(item["rel"]))
        )
    intro = ("全书正文与插图。每章页面已内联 SVG 图示，可直接浏览。"
             if PUBLIC_EDITION else
             "源稿来自 Markdown；本目录用于逐章审阅和单独优化。每章页面已内联 SVG 图示，可直接浏览图片。")
    main = """
<h1>%s</h1>
<p class="chapter-meta">%s</p>
<div class="review-index">
%s
</div>
""" % (PAGE_TITLE, intro, "\n".join(cards))
    return page_shell(PAGE_TITLE, nav_html(items, depth="root"), main, depth="root")


def prev_next(items, idx):
    prev_item = items[idx - 1] if idx > 0 else None
    next_item = items[idx + 1] if idx + 1 < len(items) else None
    prev_link = '<a href="%s">← %s</a>' % (prev_item["file"], html_escape(prev_item["title"])) if prev_item else '<span class="empty"></span>'
    next_link = '<a href="%s">%s →</a>' % (next_item["file"], html_escape(next_item["title"])) if next_item else '<span class="empty"></span>'
    return '<nav class="page-nav">%s%s</nav>' % (prev_link, next_link)


def build_chapter_page(items, idx):
    item = items[idx]
    main = '<article class="chapter">%s%s</article>' % (item["body"], prev_next(items, idx))
    return page_shell(item["title"], nav_html(items, current_file=item["file"], depth="chapter"), main, depth="chapter")


def main():
    items, registry = load_chapters()
    # 交叉引用自动链接（分页模式：跨章 file#frag、同章 #frag）
    stats = {'linked': 0, 'unresolved': {}}
    page_for = lambda i: items[i]["file"]
    for item in items:
        item["body"] = link_xrefs(item["body"], item["index"], registry, len(CHAPTERS), page_for, stats)

    # 页名用产物真实路径（带 chapters/ 前缀）：validate_site 按源页目录解析相对路径，
    # 裸文件名会让 "../x.html" 这类错路径在归一化时碰巧命中而假通过
    pages = [("index.html", build_index(items))]
    pages += [("chapters/" + item["file"], build_chapter_page(items, idx)) for idx, item in enumerate(items)]

    # 落锤校验（落盘前）：页内重复 id / 跨页坏锚点 / 外部资源
    audit = validate_site(pages, out_json=os.path.join(ROOT, "qa", "pages-audit.json"), label="paged", stats=stats)

    if os.path.isdir(DIST):
        shutil.rmtree(DIST)
    os.makedirs(CHAPTER_DIR, exist_ok=True)
    for name, html_doc in pages:
        open(os.path.join(DIST, name), "w", encoding="utf-8").write(html_doc)

    print("已生成分页站点: %s" % DIST)
    print("首页: %s" % os.path.join(DIST, "index.html"))
    print("章节页: %d" % len(items))
    print("交叉引用: 已链接 %d 处 | 未解析 %d 种%s" % (
        audit["xrefs_linked"], len(audit["xrefs_unresolved"]),
        ("（" + "、".join("%s×%d" % kv for kv in sorted(audit["xrefs_unresolved"].items())) + "）") if audit["xrefs_unresolved"] else ""))
    print("构建校验: PASS（重复 id/坏锚点/外部资源 均零）→ qa/pages-audit.json")


if __name__ == "__main__":
    main()
