#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把全书（序言 + 9 章 + 后记）合并成单个自包含 HTML，SVG 配图内联。
用法: python3 scripts/build_html.py [repo_root]
无第三方依赖。"""
import os, re, sys

ROOT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def load_svg(path, prefix=''):
    s = open(path, encoding='utf-8').read()
    s = re.sub(r'<\?xml[^>]*\?>\s*', '', s)   # 去 XML 声明
    s = re.sub(r'<!DOCTYPE[^>]*>\s*', '', s)
    # 剥离图内"图 X-Y 编号标题"行：下方 figcaption 已承担编号标题，留着会上下重复。
    # 仅构建时剥离；.svg 源文件仍自带标题，单独打开不受影响。保留解释性副标题。
    m = re.search(r'<text\b[^>]*>\s*图\s*\d+[-－]\d+\s*[^<]*</text>', s)
    if m:
        s = s[:m.start()] + s[m.end():]
    # 内联 SVG 没有 width/height 时浏览器会塌缩为 0×0；注入 width="100%" 保证可见
    s = re.sub(r'(<svg\b)(?![^>]*\swidth=)', r'\1 width="100%"', s)
    # 内联到同一 HTML 时，各 SVG 的 <marker id="arrow"> 等会跨文件冲突
    # （HTML 规范要求 id 唯一，且 url(#id) 会全部指向第一个同名定义）。
    # 给每个图的 id 加上唯一前缀（基于文件名），同步替换 url(#...) 引用。
    if prefix:
        ids = set(re.findall(r'\bid="([^"]+)"', s))
        for _id in ids:
            s = s.replace('id="%s"' % _id, 'id="%s_%s"' % (prefix, _id))
            s = s.replace('url(#%s)' % _id, 'url(#%s_%s)' % (prefix, _id))
            s = s.replace('href="#%s"' % _id, 'href="#%s_%s"' % (prefix, _id))
    return s  # <svg ...>...</svg>

def split_row(line):
    line = line.strip()
    if line.startswith('|'): line = line[1:]
    if line.endswith('|'): line = line[:-1]
    return [c.strip() for c in line.split('|')]

SEP = re.compile(r'^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$')

def inline(text, svgmap, diag_prefix=''):
    codes = []
    def stash(m):
        codes.append(m.group(1)); return '\x00C%d\x00' % (len(codes) - 1)
    text = re.sub(r'`([^`]+)`', stash, text)
    text = esc(text)
    # 图片
    def img(m):
        alt, url = m.group(1), m.group(2)
        if url in svgmap:
            return '<span class="inline-svg">' + svgmap[url] + '</span>'
        if not url.endswith('.svg') and diag_prefix:
            url = diag_prefix + '/' + os.path.basename(url)
        return '<img src="%s" alt="%s">' % (url, alt)
    text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', img, text)
    # 链接
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    # 加粗 / 斜体
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'<em>\1</em>', text)
    # 还原行内代码
    text = re.sub(r'\x00C(\d+)\x00', lambda m: '<code>' + esc(codes[int(m.group(1))]) + '</code>', text)
    return text

def convert(md, svgmap, gptmap, counter, diag_prefix='', chidx=None, registry=None):
    """返回 (html, headings) ；headings=[(level,text,id)]
    chidx+registry 给定时：编号标题派生稳定锚 id（sec-N.M），图/表派生 fig-N-M / table-N-M，
    并登记到 registry（{'sec':{'9.2':chidx,...},'fig':{'3-1':chidx,...},'tab':{...}}），
    供全书两遍构建后 link_xrefs 做交叉引用自动链接。"""
    lines = md.split('\n')
    out, heads = [], []
    i, n = 0, len(lines)

    def is_break(l, nxt):
        if not l.strip(): return True
        if re.match(r'^#{1,6}\s', l): return True
        if l.strip().startswith('```'): return True
        if l.lstrip().startswith('>'): return True
        if re.match(r'^(\s*)([-*+]|\d+\.)\s+', l): return True
        if re.match(r'^(-{3,}|\*{3,}|_{3,})\s*$', l): return True
        if re.match(r'^\s*!\[[^\]]*\]\([^)]+\)\s*$', l): return True
        if l.lstrip().startswith('|') and nxt is not None and SEP.match(nxt): return True
        return False

    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1; continue
        # fenced code
        if line.strip().startswith('```'):
            lang = line.strip()[3:].strip()
            buf = []; i += 1
            while i < n and not lines[i].strip().startswith('```'):
                buf.append(lines[i]); i += 1
            i += 1
            cls = ' class="lang-%s"' % lang if lang else ''
            out.append('<pre><code%s>%s</code></pre>' % (cls, esc('\n'.join(buf))))
            continue
        # heading
        m = re.match(r'^(#{1,6})\s+(.*)$', line)
        if m:
            lvl = len(m.group(1)); txt = m.group(2).strip()
            counter[0] += 1; hid = 's%d' % counter[0]
            # 编号小节（"9.1"/"8.4.6"开头且非章标题）→ 稳定锚 sec-N.M，供"N.M 节"引用跳转
            mnum = re.match(r'^(\d+(?:\.\d+)*)[\s　]', txt) if lvl >= 2 else None
            if mnum and registry is not None:
                _num = mnum.group(1)
                # 登记绊线：①节号首段必须等于章号（防"## 2026 年复盘"式标题误判、劫持他章锚点）；
                # ②重号直接失败（分页模式没有页内重复 id 安全网，必须在此拦下）
                if chidx is not None and 1 <= chidx <= 10 and int(_num.split('.')[0]) != chidx:
                    sys.exit('构建失败: 标题"%s"编号 %s 与所在章(ch%d)不符' % (txt, _num, chidx))
                if _num in registry['sec']:
                    sys.exit('构建失败: 小节编号 %s 重复登记（标题"%s"）' % (_num, txt))
                hid = 'sec-' + _num
                registry['sec'][_num] = chidx
            heads.append((lvl, txt, hid))
            out.append('<h%d id="%s">%s</h%d>' % (lvl, hid, inline(txt, svgmap, diag_prefix), lvl))
            i += 1; continue
        # hr
        if re.match(r'^(-{3,}|\*{3,}|_{3,})\s*$', line):
            out.append('<hr>'); i += 1; continue
        # table
        if line.lstrip().startswith('|') and i + 1 < n and SEP.match(lines[i + 1]):
            header = split_row(line); rows = []; i += 2
            while i < n and lines[i].lstrip().startswith('|'):
                rows.append(split_row(lines[i])); i += 1
            # 紧邻上文是"**表 N-M　…**"标签段 → 表挂稳定锚 table-N-M
            tab_id = ''
            if registry is not None and out:
                mtab = re.match(r'^<p>(?:<strong>)?表\s*(\d+)\s*[-－–]\s*(\d+)', out[-1])
                if mtab:
                    _key = '%s-%s' % (mtab.group(1), mtab.group(2))
                    if chidx is not None and 1 <= chidx <= 10 and int(mtab.group(1)) != chidx:
                        sys.exit('构建失败: 表 %s 编号与所在章(ch%d)不符' % (_key, chidx))
                    if _key in registry['tab']:
                        sys.exit('构建失败: 表编号 %s 重复登记' % _key)
                    tab_id = ' id="table-%s"' % _key
                    registry['tab'][_key] = chidx
                    # 标签段打 class：link_xrefs 据此豁免"表 N-M"自链（与 figcaption 防自引同口径）
                    if out[-1].startswith('<p>'):
                        out[-1] = '<p class="tab-label">' + out[-1][3:]
            th = ''.join('<th>%s</th>' % inline(c, svgmap, diag_prefix) for c in header)
            trs = []
            for r in rows:
                while len(r) < len(header): r.append('')
                trs.append('<tr>%s</tr>' % ''.join('<td>%s</td>' % inline(c, svgmap, diag_prefix) for c in r[:len(header)]))
            out.append('<div class="table-wrap"><table%s><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (tab_id, th, ''.join(trs)))
            continue
        # blockquote
        if line.lstrip().startswith('>'):
            buf = []
            while i < n and lines[i].lstrip().startswith('>'):
                buf.append(re.sub(r'^\s*>\s?', '', lines[i])); i += 1
            out.append('<blockquote>%s</blockquote>' % inline(' '.join(b.strip() for b in buf), svgmap, diag_prefix))
            continue
        # list
        lm = re.match(r'^(\s*)([-*+]|\d+\.)\s+(.*)$', line)
        if lm:
            ordered = bool(re.match(r'\d+\.', lm.group(2)))
            items = []
            while i < n:
                lm2 = re.match(r'^(\s*)([-*+]|\d+\.)\s+(.*)$', lines[i])
                if not lm2: break
                items.append(lm2.group(3)); i += 1
            tag = 'ol' if ordered else 'ul'
            out.append('<%s>%s</%s>' % (tag, ''.join('<li>%s</li>' % inline(t, svgmap, diag_prefix) for t in items), tag))
            continue
        # 图片独占行 → figure
        im = re.match(r'^\s*!\[([^\]]*)\]\(([^)]+)\)\s*$', line)
        if im:
            alt, url = im.group(1), im.group(2)
            cap_text = alt
            consumed = 1
            # 若下一行是图注（*图 X-Y …* 或 图 X-Y　…，仅全角空格体例），合并为唯一图注，避免「figcaption + 图注段落」重复
            if i + 1 < n:
                mc = re.match(r'^\s*\*([^*]+)\*\s*$', lines[i + 1])
                mc2 = re.match(r'^\s*图\s*\d+[-－]\d+　', lines[i + 1])
                if mc:
                    cap_text = mc.group(1); consumed = 2
                elif mc2:
                    cap_text = lines[i + 1].strip(); consumed = 2
            cap = '<figcaption>%s</figcaption>' % inline(cap_text, svgmap, diag_prefix) if cap_text else ''
            # 图 N-M → 稳定锚 fig-N-M（挂在 figure 上，供正文"图 N-M"引用跳转）
            fid = ''
            mfid = re.match(r'^\s*图\s*(\d+)\s*[-－–]\s*(\d+)', cap_text or alt)
            if mfid and registry is not None:
                _fkey = '%s-%s' % (mfid.group(1), mfid.group(2))
                if chidx is not None and 1 <= chidx <= 10 and int(mfid.group(1)) != chidx:
                    sys.exit('构建失败: 图 %s 编号与所在章(ch%d)不符' % (_fkey, chidx))
                if _fkey in registry['fig']:
                    sys.exit('构建失败: 图编号 %s 重复登记' % _fkey)
                fid = ' id="fig-%s"' % _fkey
                registry['fig'][_fkey] = chidx
            if url in svgmap:
                out.append('<figure class="fig"%s>%s%s</figure>' % (fid, svgmap[url], cap))
            else:
                img_url = diag_prefix + '/' + os.path.basename(url) if diag_prefix else url
                out.append('<figure class="fig"%s><img src="%s" alt="%s">%s</figure>' % (fid, img_url, alt, cap))
            i += consumed; continue
        # paragraph
        buf = [line]; i += 1
        while i < n:
            l = lines[i]; nxt = lines[i + 1] if i + 1 < n else None
            if is_break(l, nxt): break
            buf.append(l); i += 1
        out.append('<p>%s</p>' % inline(' '.join(b.strip() for b in buf), svgmap, diag_prefix))
    return '\n'.join(out), heads


# ----------------------------------------------------------------交叉引用自动链接
# 正文文本中的 图N-M / 表N-M / N.M节 / 第N章 引用 → 站内跳转 <a class="xref">。
# 只作用于纯文本节点：svg / pre / code / a / figcaption / h1-h4 内豁免（防自引、防嵌套、防改图内文字）。

XREF_SKIP = {'svg', 'pre', 'code', 'a', 'figcaption', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'script', 'style'}

XREF_PATTERNS = [
    ('fig', re.compile(r'图\s*(\d+)\s*[-－–]\s*(\d+)')),
    ('tab', re.compile(r'表\s*(\d+)\s*[-－–]\s*(\d+)')),
    # 负向断言防截词："2.4 节点/节约/节奏"不得切成"2.4 节"+"点"
    ('sec', re.compile(r'(\d+(?:\.\d+)+)\s*节(?![点约能省奏])')),
    ('ch', re.compile(r'第\s*(\d+)\s*章')),
    # "见 N.M"（无"节"字）变体，放最后：已带"节"的引用先被上面消费，不会重叠；
    # 负向断言排除"8.2.3–8.2.4"节号范围（范围引用维持不链）；
    # lookbehind 排除"意见/看见/常见/罕见"等构词字（"归类见 7.2.3"这类真引用不受影响）
    ('seeref', re.compile(r'(?<![意看可听碰遇常罕见望瞧窥拜])(?:见|参见|详见)\s*(\d+(?:\.\d+)+)(?![\d.\-–—~])')),
]

def new_registry():
    return {'sec': {}, 'fig': {}, 'tab': {}}

def link_xrefs(body, cur_idx, registry, n_chapters, page_for=None, stats=None):
    """对一章 HTML 正文做引用链接。返回处理后的 HTML。
    page_for=None → 单文件模式，目标一律 #chN / #id；
    否则 page_for(idx) 返回该章页面文件名（分页模式：跨章 target#id，同章 #id）。
    stats: {'linked':int,'unresolved':{key:count}} 由调用方传入累计。"""
    if stats is None:
        stats = {'linked': 0, 'unresolved': {}}
    # 先剥 HTML 注释：注释里的裸 "<" 会干扰标签切段（可能吞掉 </svg>，使豁免深度永不归零、
    # 该章后续引用全部静默失链）。未闭合注释剥不掉，由章末深度绊线兜住。
    body = re.sub(r'<!--.*?-->', '', body, flags=re.S)
    parts = re.split(r'(<[^>]*>)', body)
    depth = dict.fromkeys(XREF_SKIP, 0)
    in_tab_label = False  # <p class="tab-label"> 内豁免（防表标签自链，与 figcaption 同口径）

    def href_for(kind, m):
        if kind == 'ch':
            n = int(m.group(1))
            # 具名章只有 1..10（CHAPTERS 尾部的后记不按"第 N 章"被引用）
            if not (1 <= n <= 10):
                return None
            if page_for is None:
                return '#ch%d' % n
            return '#' if n == cur_idx else page_for(n)  # 同章自指：页内回顶，不整页重载
        if kind == 'fig':
            key = '%s-%s' % (m.group(1), m.group(2)); a_id = 'fig-' + key; reg = registry['fig']
        elif kind == 'tab':
            key = '%s-%s' % (m.group(1), m.group(2)); a_id = 'table-' + key; reg = registry['tab']
        else:
            key = m.group(1); a_id = 'sec-' + key; reg = registry['sec']
        t = reg.get(key)
        if t is None:
            return None
        if page_for is None:
            return '#' + a_id
        return ('#%s' % a_id) if t == cur_idx else (page_for(t) + '#' + a_id)

    for i, seg in enumerate(parts):
        if seg.startswith('<'):
            if seg.startswith('<p class="tab-label"'):
                in_tab_label = True
            elif seg.startswith('</p>'):
                in_tab_label = False
            tm = re.match(r'</?\s*([a-zA-Z0-9-]+)', seg)
            if tm:
                t = tm.group(1).lower()
                if t in depth:
                    if seg.startswith('</'):
                        depth[t] -= 1
                    elif not seg.endswith('/>'):
                        depth[t] += 1
            continue
        if in_tab_label or any(v > 0 for v in depth.values()):
            continue
        for kind, pat in XREF_PATTERNS:
            def repl(m, kind=kind):
                href = href_for(kind, m)
                if href is None:
                    k = '%s:%s' % (kind, m.group(1) if kind != 'fig' and kind != 'tab' else '%s-%s' % (m.group(1), m.group(2)))
                    stats['unresolved'][k] = stats['unresolved'].get(k, 0) + 1
                    return m.group(0)
                stats['linked'] += 1
                return '<a class="xref" href="%s">%s</a>' % (href, m.group(0))
            parts[i] = pat.sub(repl, parts[i])
    # 绊线：豁免深度必须归零。未闭合的 svg/a/code 等会让该章剩余引用被静默跳过且无任何信号，
    # 这里直接构建失败，把问题拦在落盘前。
    bad = [t for t, v in depth.items() if v]
    if bad:
        sys.exit('构建失败: link_xrefs 豁免深度未归零 %s —— 存在未闭合标签（如 SVG 内裸 "<"），其后引用已被静默跳过' % bad)
    return ''.join(parts)


# ----------------------------------------------------------------构建期落锤校验

def validate_site(pages, out_json=None, label='', stats=None):
    """pages: [(name, html), ...]。校验：页内重复 id / 锚点可达（含跨页 file#frag）/ 无外部资源依赖。
    致命问题直接 SystemExit(1)；结果连同 stats 写入 out_json（qa/build-audit.json）。返回 audit dict。"""
    ids_by_page = {}
    for name, h in pages:
        ids = re.findall(r'\bid="([^"]+)"', h)
        seen, dup = set(), []
        for i in ids:
            (dup.append(i) if i in seen else seen.add(i))
        if dup:
            print('校验失败 [%s] %s 页内重复 id: %s' % (label, name, sorted(set(dup))))
            sys.exit(1)
        ids_by_page[name] = seen

    broken = []
    for name, h in pages:
        base = os.path.dirname(name)
        for href in re.findall(r'\bhref="([^"]+)"', h):
            if href.startswith(('http://', 'https://', 'mailto:', 'data:')):
                continue  # 外链与 data URI 资源，允许
            if href.startswith('#'):
                frag_page, frag = name, href[1:]
            else:
                # 按源页真实目录解析相对路径：字符串归一化会让 "../chapters/x" 这类错路径
                # 在剥前缀后"碰巧命中"而假通过；浏览器实际是按目录解析的
                norm = os.path.normpath(os.path.join(base, href.split('#', 1)[0]))
                frag = href.split('#', 1)[1] if '#' in href else None
                frag_page = norm
            if frag_page not in ids_by_page:
                broken.append('%s: href=%s（目标页不存在）' % (name, href)); continue
            if frag and frag not in ids_by_page[frag_page]:
                broken.append('%s: href=%s（锚点不存在）' % (name, href))
    if broken:
        print('校验失败 [%s] 坏锚点 %d 处:' % (label, len(broken)))
        for b in broken[:20]:
            print('  ' + b)
        sys.exit(1)

    # 外部资源依赖（违反自包含）：覆盖 script/img/link 等资源标签（含无引号写法、SVG 的
    # xlink:href、protocol-relative "//"）以及 style 内联 url()；<a href> 不算资源加载，不查
    EXT_RES = re.compile(r'''<(?:script|img|image|iframe|frame|video|audio|link|source|embed|object)\b[^>]*?(?:xlink:)?(?:src|href|data)\s*=\s*["']?\s*(?:https?:)?//''')
    EXT_STYLE = re.compile(r'''style\s*=\s*["'][^"']*url\(\s*["']?\s*(?:https?:)?//''', re.I)
    external = []
    for name, h in pages:
        for m in EXT_RES.finditer(h):
            external.append('%s: %s…' % (name, h[m.start():m.start() + 80]))
        for m in EXT_STYLE.finditer(h):
            external.append('%s: style url() %s…' % (name, h[m.start():m.start() + 60]))
    if external:
        print('校验失败 [%s] 外部资源依赖（违反自包含）:' % label)
        for e in external[:10]:
            print('  ' + e)
        sys.exit(1)

    audit = {
        'label': label,
        'pages': {name: len(ids) for name, ids in ids_by_page.items()},
        'xrefs_linked': (stats or {}).get('linked', 0),
        'xrefs_unresolved': (stats or {}).get('unresolved', {}),
        'broken_anchors': 0,
        'external_resources': 0,
    }
    if out_json:
        import json
        os.makedirs(os.path.dirname(out_json), exist_ok=True)
        with open(out_json, 'w', encoding='utf-8') as f:
            json.dump(audit, f, ensure_ascii=False, indent=2)
    return audit

CHAPTERS = [
    ('chapters/00-preface.md', None),
    ('chapters/01-introduction/chapter.md', 'chapters/01-introduction/diagrams'),
    ('chapters/02-data-structures-protocols/chapter.md', 'chapters/02-data-structures-protocols/diagrams'),
    ('chapters/03-lifecycle/chapter.md', 'chapters/03-lifecycle/diagrams'),
    ('chapters/04-memory-disk/chapter.md', 'chapters/04-memory-disk/diagrams'),
    ('chapters/05-layered-architecture/chapter.md', 'chapters/05-layered-architecture/diagrams'),
    ('chapters/06-security/chapter.md', 'chapters/06-security/diagrams'),
    ('chapters/07-cluster/chapter.md', 'chapters/07-cluster/diagrams'),
    ('chapters/08-storage-format/chapter.md', 'chapters/08-storage-format/diagrams'),
    ('chapters/09-data-sync/chapter.md', 'chapters/09-data-sync/diagrams'),
    ('chapters/10-summary/chapter.md', 'chapters/10-summary/diagrams'),
    ('chapters/10-epilogue.md', None),
]

CSS = """
*{box-sizing:border-box}
:root{--ink:#1f2328;--mute:#57606a;--line:#d8dee4;--accent:#4f46e5;--bg:#fff;--soft:#f6f8fa}
html{scroll-behavior:smooth}
body{margin:0;font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans CJK SC",system-ui,sans-serif;color:var(--ink);background:#fff;line-height:1.8;font-size:16px}
.layout{display:grid;grid-template-columns:264px 1fr;max-width:1340px;margin:0 auto}
nav.toc{position:sticky;top:0;align-self:start;height:100vh;overflow-y:auto;padding:24px 16px 24px 8px;border-right:1px solid var(--line);font-size:14px}
.toc-title{font-weight:700;font-size:15px;color:var(--accent);margin:0 0 4px 8px}
.toc-sub{font-size:12px;color:var(--mute);margin:0 0 16px 8px}
nav.toc ul{list-style:none;padding:0;margin:0}
nav.toc li>a{display:block;padding:5px 10px;border-radius:6px;color:var(--ink);text-decoration:none;line-height:1.5}
nav.toc li>a:hover{background:var(--soft)}
nav.toc li.active>a{background:#eef2ff;color:var(--accent);font-weight:600}
nav.toc li.nav-sub>a{padding-left:22px;font-size:13px;color:var(--mute)}
.content{padding:32px 48px 120px;max-width:1000px;overflow-wrap:anywhere}
section.chapter{scroll-margin-top:20px}
section.chapter+section.chapter{margin-top:64px;border-top:2px solid var(--line);padding-top:40px}
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
.gpt-alt{margin-top:1.2em;padding-top:1em;border-top:1px dashed var(--mute);opacity:.82}
.gpt-alt img{max-width:600px;width:100%;height:auto;display:block;margin:0 auto;border-radius:6px;border:1px solid #e5e7eb}
.gpt-alt small{display:block;text-align:center;color:var(--mute);font-size:.82em;margin-top:.4em}
.toc-toggle{display:none}
@media(max-width:1200px){figure.fig{margin:2em auto}}
@media(max-width:860px){
  .layout{grid-template-columns:1fr}
  nav.toc{position:fixed;left:0;top:0;width:280px;background:#fff;z-index:50;transform:translateX(-100%);transition:transform .2s;box-shadow:2px 0 12px rgba(0,0,0,.08)}
  nav.toc.open{transform:translateX(0)}
  .content{padding:20px 18px 80px;max-width:100%;min-width:0}
  .toc-toggle{display:inline-block;position:fixed;right:16px;bottom:16px;z-index:60;background:var(--accent);color:#fff;border:none;border-radius:50%;width:48px;height:48px;font-size:13px;box-shadow:0 4px 12px rgba(0,0,0,.2);cursor:pointer}
  .backdrop{display:none;position:fixed;inset:0;background:rgba(0,0,0,.3);z-index:40}
  .backdrop.show{display:block}
  /* 窄屏宽图改为容器内横向滚动，文字保持可读 */
  .svg-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}
  figure.fig svg{min-width:760px}
}
@media print{nav.toc{display:none}.layout{grid-template-columns:1fr}.content{max-width:100%;padding:0}section.chapter+section.chapter{page-break-before:always;border-top:none}a.xref{color:inherit}}
"""

JS = """
(function(){
  var btn=document.querySelector('.toc-toggle'),nav=document.getElementById('toc'),bd=document.getElementById('bd');
  if(btn){btn.addEventListener('click',function(){nav.classList.toggle('open');if(bd)bd.classList.toggle('show',nav.classList.contains('open'))});}
  if(bd){bd.addEventListener('click',function(){nav.classList.remove('open');bd.classList.remove('show');});}
  // 当前章节高亮
  var secs=Array.prototype.slice.call(document.querySelectorAll('section.chapter'));
  var links=Array.prototype.slice.call(document.querySelectorAll('nav.toc a[data-target]'));
  if('IntersectionObserver' in window && links.length){
    var map={};links.forEach(function(a){map[a.getAttribute('data-target')]=a;});
    var io=new IntersectionObserver(function(entries){
      entries.forEach(function(e){
        if(e.isIntersecting){
          links.forEach(function(a){a.parentElement.classList.remove('active');});
          var a=map[e.target.id]; if(a)a.parentElement.classList.add('active');
        }
      });
    },{rootMargin:'-10% 0px -75% 0px',threshold:0});
    secs.forEach(function(s){io.observe(s);});
  }
})();
"""

def main():
    counter = [0]
    registry = new_registry()
    converted = []  # [(idx, rel, diag, html_body, heads)]
    # 第一遍：全部转换，收齐全书锚点登记（后章引用前章、前章引用后章都要齐了才可链接）
    for idx, (rel, diag) in enumerate(CHAPTERS):
        path = os.path.join(ROOT, rel)
        md = open(path, encoding='utf-8').read()
        svgmap = {}
        gptmap = {}
        if diag and os.path.isdir(os.path.join(ROOT, diag)):
            for fn in sorted(os.listdir(os.path.join(ROOT, diag))):
                if fn.endswith('.svg'):
                    prefix = fn.replace('.svg', '').replace('-', '_')  # fig-1-1 → fig_1_1
                    svg = load_svg(os.path.join(ROOT, diag, fn), prefix)
                    svgmap['diagrams/' + fn] = '<div class="svg-wrap">' + svg + '</div>'
                elif fn.endswith('-gpt.png'):
                    gptmap['diagrams/' + fn] = diag + '/' + fn
        html_body, heads = convert(md, svgmap, gptmap, counter, diag, chidx=idx, registry=registry)
        converted.append((idx, rel, html_body, heads))
    # 第二遍：交叉引用自动链接
    stats = {'linked': 0, 'unresolved': {}}
    linked_bodies = [link_xrefs(b, idx, registry, len(CHAPTERS), None, stats) for (idx, rel, b, heads) in converted]

    nav_parts = ['<ul>']
    body_parts = []
    for (idx, rel, html_body, heads), linked in zip(converted, linked_bodies):
        sec_id = 'ch%d' % idx
        # 章标题（第一个 h1）作为 nav 项
        h1 = next((t for (l, t, _id) in heads if l == 1), os.path.basename(rel))
        nav_parts.append('<li><a href="#%s" data-target="%s">%s</a>' % (heads[0][2] if heads else sec_id, sec_id, h1))
        # 子项 h2
        subs = [h for h in heads if h[0] == 2]
        if subs:
            nav_parts.append('<ul>')
            for (l, t, hid) in subs:
                nav_parts.append('<li class="nav-sub"><a href="#%s">%s</a></li>' % (hid, t))
            nav_parts.append('</ul>')
        nav_parts.append('</li>')
        body_parts.append('<section class="chapter" id="%s">%s</section>' % (sec_id, linked))
    nav_parts.append('</ul>')

    doc = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>架构取舍之道：从 Redis、MySQL、Kafka 理解系统设计</title>
<style>%s</style>
</head>
<body>
<div class="backdrop" id="bd"></div>
<button class="toc-toggle">目录</button>
<div class="layout">
<nav class="toc" id="toc">
  <div class="toc-title">架构取舍之道</div>
  <div class="toc-sub">从 Redis、MySQL、Kafka 理解系统设计</div>
  %s
</nav>
<main class="content">
<article>
%s
</article>
</main>
</div>
<script>%s</script>
</body>
</html>""" % (CSS, '\n  '.join(nav_parts), '\n'.join(body_parts), JS)

    out = os.path.join(ROOT, '架构之道.html')
    # 构建期落锤校验（落盘前）：重复 id / 坏锚点 / 外部资源 → 任一命中直接失败退出
    audit = validate_site([(os.path.basename(out), doc)], out_json=os.path.join(ROOT, 'qa', 'build-audit.json'),
                          label='single', stats=stats)
    open(out, 'w', encoding='utf-8').write(doc)
    size = os.path.getsize(out)
    nsvg = doc.count('<svg')
    ntab = doc.count('<table')
    print('已生成: %s' % out)
    print('大小: %.1f KB | 内联 SVG: %d | 表格: %d | 章节: %d' % (size / 1024, nsvg, ntab, len(CHAPTERS)))
    print('交叉引用: 已链接 %d 处 | 未解析 %d 种%s' % (
        audit['xrefs_linked'], len(audit['xrefs_unresolved']),
        ('（' + '、'.join('%s×%d' % kv for kv in sorted(audit['xrefs_unresolved'].items())) + '）') if audit['xrefs_unresolved'] else ''))
    print('构建校验: PASS（重复 id/坏锚点/外部资源 均零）→ qa/build-audit.json')

if __name__ == '__main__':
    main()
