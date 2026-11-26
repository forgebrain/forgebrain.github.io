#!/usr/bin/env python3
"""Build migrated essays into this (pre-generated Octopress) site.

The site only contains Octopress's generated HTML, not its source, so this
script renders new posts by reusing an existing post page as the template.

Sources live in _essays/<group>/*.md with YAML front matter:

    ---
    title: 母亲节
    date: 2012-05-14 01:17
    category: emotion        # key in CATEGORIES below (where it came from)
    tags: [家庭, 成长]        # theme tags, keys of TAGS below
    source: 博客园
    source_url: https://www.cnblogs.com/...
    ---
    Markdown body

Running the script is idempotent: it (re)writes every essay page, the
category pages, /essays/, the archives list, the nav link, the sidebar tags
and sitemap entries.

    pip install markdown pyyaml
    python3 _tools/build_essays.py
"""
import datetime as dt
import html
import pathlib
import re

import markdown
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "_essays"
POST_TEMPLATE = ROOT / "blog/2013/12/12/end-of-period/index.html"
CATEGORY_TEMPLATE = ROOT / "blog/categories/life/index.html"
SITE = "http://coolbrain.github.com"

# key -> (display name, intro shown on /essays/)
CATEGORIES = {
    "emotion": ("情感", "博客园「情感类」随笔，2012–2015。"),
    "reason": ("理性", "博客园「理性类」随笔。"),
    "qzone": ("QQ空间日志", "QQ空间「一枯一荣」里的日志，2009–2012。"),
    "wechat": ("公众号", "微信公众号「静志灼灼」上的文章，2019。"),
    "letters": ("邮件", "2016 年秋天用 QQ邮箱写下的每日总结。"),
}
CATEGORY_ORDER = list(CATEGORIES)

# theme tags: display name -> url slug (pages live at /blog/tags/<slug>/)
TAGS = {
    "家庭": "family",
    "父母": "parents",
    "成长": "growth",
    "反思": "reflection",
    "校园": "campus",
    "求学": "study",
    "求职": "career",
    "感恩": "gratitude",
    "人生观": "outlook",
    "佛学": "buddhism",
    "自信": "confidence",
    "友情": "friendship",
    "旅行": "travel",
    "计划": "plans",
    "金钱": "money",
    "健康": "health",
    "电影": "film",
    "读书": "reading",
    "情绪": "mood",
}

MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
GEN_MARK = "<!-- essays:generated -->"
# emphasis styles for essays: **key point** in accent colour, ==phrase== as a soft highlight
ESSAY_STYLE = (
    "<style>.essay strong{color:#b03a2e;font-weight:bold}"
    ".essay mark{background:#fdf2c4;color:inherit;padding:0 .15em}</style>"
)
SHOW_SOURCE_NOTE = False  # the post header already shows the original date


def ordinal(n):
    if 10 <= n % 100 <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def load_essays():
    essays = []
    for path in sorted(SRC.glob("**/*.md")):
        text = path.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
        if not m:
            raise SystemExit(f"missing front matter: {path}")
        meta = yaml.safe_load(m.group(1))
        if meta.get("draft"):
            continue
        date = meta["date"]
        if isinstance(date, str):
            date = dt.datetime.strptime(date, "%Y-%m-%d %H:%M")
        elif isinstance(date, dt.date) and not isinstance(date, dt.datetime):
            date = dt.datetime(date.year, date.month, date.day)
        slug = meta.get("slug") or path.stem
        cat = meta["category"]
        assert cat in CATEGORIES, (path, cat)
        tags = meta.get("tags") or []
        for t in tags:
            assert t in TAGS, (path, t)
        body_md = m.group(2).strip()
        # ==text== marks a highlighted phrase (rendered as <mark>)
        body_md = re.sub(r"==(.+?)==", r"<mark>\1</mark>", body_md)
        body = markdown.markdown(body_md, extensions=["nl2br", "sane_lists"])
        plain = re.sub(r"<[^>]+>", "", body)
        plain = re.sub(r"\s+", " ", html.unescape(plain)).strip()
        essays.append(
            dict(
                title=str(meta["title"]),
                date=date,
                cat=cat,
                tags=list(tags),
                source=meta.get("source", ""),
                source_url=meta.get("source_url", ""),
                url=f"/blog/{date:%Y/%m/%d}/{slug}/",
                body=body,
                desc=plain[:150] + (" &hellip;" if len(plain) > 150 else ""),
            )
        )
    essays.sort(key=lambda e: e["date"])
    return essays


def time_tag(d):
    iso = d.strftime("%Y-%m-%dT%H:%M:00+08:00")
    return (
        f'<time datetime="{iso}" pubdate data-updated="true">'
        f"{MONTHS[d.month-1]} {d.day}<span>{ordinal(d.day)}</span>, {d.year}</time>"
    )


def cat_link(cat):
    return f"<a class='category' href='/blog/categories/{cat}/'>{CATEGORIES[cat][0]}</a>"


def tag_link(t):
    return f"<a class='category' href='/blog/tags/{TAGS[t]}/'>{t}</a>"


def links(e):
    return ", ".join([cat_link(e["cat"])] + [tag_link(t) for t in e["tags"]])


def render_post(tpl, e, prev, nxt):
    t = html.escape(e["title"], quote=False)
    out = tpl
    out = re.sub(r"<title>.*?</title>", f"<title>{t} - ForgeBrain</title>", out, count=1)
    out = re.sub(r'(<meta name="description" content=")[^"]*(">)',
                 lambda m: m.group(1) + html.escape(e["desc"], quote=True).replace("&amp;hellip;", "&hellip;") + m.group(2),
                 out, count=1)
    out = re.sub(r'(<link rel="canonical" href=")[^"]*(">)',
                 lambda m: m.group(1) + SITE + e["url"] + m.group(2), out, count=1)
    out = re.sub(r'<h1 class="entry-title">.*?</h1>',
                 f'<h1 class="entry-title">{t}</h1>', out, count=1)
    out = re.sub(r"<time datetime=[^>]*>.*?</time>", time_tag(e["date"]), out)
    note = ""
    if e["source"] and SHOW_SOURCE_NOTE:
        src = html.escape(e["source"])
        if e["source_url"]:
            src = f'<a href="{html.escape(e["source_url"])}">{src}</a>'
        note = f'\n<p class="essay-source" style="color:#888;font-size:.85em">原载于{src}，原发表时间 {e["date"]:%Y-%m-%d %H:%M}。</p>'
    content = f'<div class="entry-content">{GEN_MARK}{ESSAY_STYLE}\n<div class="essay">\n{e["body"]}{note}\n</div>\n</div>'
    out = re.sub(r'<div class="entry-content">.*?</div>\n', lambda m: content + "\n", out, count=1, flags=re.S)
    out = re.sub(r'<span class="categories">.*?</span>',
                 f'<span class="categories">\n  \n    {links(e)}\n  \n</span>',
                 out, count=1, flags=re.S)
    nav = []
    if prev:
        pt = html.escape(prev["title"], quote=False)
        nav.append(f'<a class="basic-alignment left" href="{prev["url"]}" title="Previous Post: {pt}">&laquo; {pt}</a>')
    if nxt:
        nt = html.escape(nxt["title"], quote=False)
        nav.append(f'<a class="basic-alignment right" href="{nxt["url"]}" title="Next Post: {nt}">{nt} &raquo;</a>')
    out = re.sub(r'(<p class="meta">\s*)(<a class="basic-alignment left".*?)(\s*</p>\s*</footer>)',
                 lambda m: m.group(1) + "\n        ".join(nav) + m.group(3), out, count=1, flags=re.S)
    out = re.sub(r"(var disqus_(?:identifier|url) = ')[^']*(')",
                 lambda m: m.group(1) + SITE + e["url"] + m.group(2), out)
    return out


def archive_item(title, url, d, cats_html):
    iso = d.strftime("%Y-%m-%dT%H:%M:00+08:00")
    return (
        f"<article>\n  \n<h1><a href=\"{url}\">{title}</a></h1>\n"
        f"<time datetime=\"{iso}\" pubdate><span class='month'>{MONTHS[d.month-1]}</span> "
        f"<span class='day'>{d.day:02d}</span> <span class='year'>{d.year}</span></time>\n\n"
        f"<footer>\n  <span class=\"categories\">posted in {cats_html}</span>\n</footer>\n\n\n</article>\n"
    )


def group_by_year(items):
    """items: list of (datetime, html). Returns archive body HTML, newest first."""
    items = sorted(items, key=lambda x: x[0], reverse=True)
    out, year = [], None
    for d, h in items:
        if d.year != year:
            year = d.year
            out.append(f"\n\n\n  \n  <h2>{year}</h2>\n\n")
        out.append(h + "\n\n\n")
    return "".join(out)


def replace_archive_body(page, body):
    return re.sub(r'(<div id="blog-archives"[^>]*>).*?(</div>\s*</article>)',
                  lambda m: m.group(1) + body + m.group(2), page, count=1, flags=re.S)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main():
    essays = load_essays()
    gen_urls = {e["url"] for e in essays}
    tpl = POST_TEMPLATE.read_text(encoding="utf-8")

    # 1. posts (prev/next chained within the migrated collection)
    for i, e in enumerate(essays):
        prev = essays[i - 1] if i > 0 else None
        nxt = essays[i + 1] if i + 1 < len(essays) else None
        write(ROOT / e["url"].strip("/") / "index.html", render_post(tpl, e, prev, nxt))

    def item(e):
        return (e["date"], archive_item(html.escape(e["title"], quote=False), e["url"], e["date"], links(e)))

    # 2. category pages
    ctpl = CATEGORY_TEMPLATE.read_text(encoding="utf-8")
    for cat in CATEGORY_ORDER:
        sub = [e for e in essays if e["cat"] == cat]
        if not sub:
            continue
        name = CATEGORIES[cat][0]
        page = re.sub(r"<title>.*?</title>", f"<title>Category: {name} - ForgeBrain</title>", ctpl, count=1)
        page = page.replace("Category: Life", f"Category: {name}")
        page = page.replace("/blog/categories/life/atom.xml", f"/blog/categories/{cat}/atom.xml")
        page = replace_archive_body(page, group_by_year([item(e) for e in sub]))
        write(ROOT / f"blog/categories/{cat}/index.html", page)

    # 2b. tag pages
    tag_count = {t: sum(t in e["tags"] for e in essays) for t in TAGS}
    used_tags = [t for t in TAGS if tag_count[t]]
    for t in used_tags:
        slug = TAGS[t]
        sub = [e for e in essays if t in e["tags"]]
        page = re.sub(r"<title>.*?</title>", f"<title>Tag: {t} - ForgeBrain</title>", ctpl, count=1)
        page = page.replace("Category: Life", f"主题：{t}")
        page = page.replace("/blog/categories/life/atom.xml", "/atom.xml")
        page = replace_archive_body(page, group_by_year([item(e) for e in sub]))
        write(ROOT / f"blog/tags/{slug}/index.html", page)

    def cloud():
        mx = max(tag_count.values() or [1])
        return " ".join(
            f"<a href='/blog/tags/{TAGS[t]}/' style='font-size: {100 + round(60 * tag_count[t] / mx)}%'>{t}</a>"
            for t in used_tags
        )

    # 3. /essays/ landing page
    parts = ["\n<p>这里收录了我早年散落在博客园、QQ空间、公众号和邮件里的文字。可以按主题浏览，也可以按来源浏览。</p>\n",
             f'\n<h2>按主题</h2>\n<p class="essay-tags">{cloud()}</p>\n']
    for cat in CATEGORY_ORDER:
        sub = [e for e in essays if e["cat"] == cat]
        if not sub:
            continue
        name, intro = CATEGORIES[cat]
        parts.append(f'\n<h2><a href="/blog/categories/{cat}/">{name}</a> <small>({len(sub)})</small></h2>\n<p>{intro}</p>\n<ul>\n')
        for e in sorted(sub, key=lambda e: e["date"], reverse=True):
            parts.append(f'  <li><a href="{e["url"]}">{html.escape(e["title"], quote=False)}</a> <span style="color:#888">{e["date"]:%Y-%m-%d}</span></li>\n')
        parts.append("</ul>\n")
    page = re.sub(r"<title>.*?</title>", "<title>Essays - ForgeBrain</title>", ctpl, count=1)
    page = page.replace("Category: Life", "Essays 随笔")
    page = replace_archive_body(page, "".join(parts))
    page = page.replace('id="blog-archives" class="category"', 'id="essays-index"', 1)
    write(ROOT / "essays/index.html", page)

    # 4. archives: keep original entries, add ours, regroup by year
    apath = ROOT / "blog/archives/index.html"
    arch = apath.read_text(encoding="utf-8")
    body = re.search(r'<div id="blog-archives"[^>]*>(.*?)</div>\s*</article>', arch, re.S).group(1)
    old = []
    for art in re.findall(r"<article>.*?</article>", body, re.S):
        href = re.search(r'<h1><a href="([^"]+)"', art).group(1)
        if href in gen_urls or re.search(r"/blog/categories/(%s)/'|/blog/tags/" % "|".join(CATEGORIES), art):
            continue
        d = dt.datetime.strptime(re.search(r'datetime="([^"]+)"', art).group(1)[:16], "%Y-%m-%dT%H:%M")
        old.append((d, art + "\n"))
    arch = replace_archive_body(arch, group_by_year(old + [item(e) for e in essays]))
    write(apath, arch)

    # 5. nav link + sidebar tags on every page
    nav_li = '<li><a href="/essays/">Essays</a></li>'
    tags = "".join(
        f" <a href='/blog/categories/{c}' style='font-size: 120%'>{CATEGORIES[c][0]}</a> "
        for c in CATEGORY_ORDER if any(e["cat"] == c for e in essays)
    ) + " " + cloud() + " "
    for p in ROOT.rglob("*.html"):
        if ".git" in p.parts or p.parts[len(ROOT.parts)] in ("_tools", "_essays"):
            continue
        s = p.read_text(encoding="utf-8")
        orig = s
        if nav_li not in s:
            s = s.replace('<li><a href="/blog/archives">Archives</a></li>',
                          '<li><a href="/blog/archives">Archives</a></li>\n  ' + nav_li, 1)
        s = re.sub(r"<!--essay-tags-->.*?<!--/essay-tags-->", "", s, flags=re.S)
        s = s.replace("<span class='categories_tag'>", f"<span class='categories_tag'><!--essay-tags-->{tags}<!--/essay-tags-->", 1)
        if s != orig:
            p.write_text(s, encoding="utf-8")

    # 6. sitemap
    sm = ROOT / "sitemap.xml"
    s = sm.read_text(encoding="utf-8")
    s = re.sub(r"\s*<url>\s*<loc>[^<]*(?:/essays/|%s)[^<]*</loc>.*?</url>" % "|".join(
        re.escape(u) for u in sorted(gen_urls) + [f"/blog/categories/{c}/" for c in CATEGORIES] + ["/blog/tags/"]), "", s, flags=re.S)
    extra = "".join(
        f"\n  <url>\n    <loc>{SITE}{u}</loc>\n  </url>"
        for u in ["/essays/"] + [f"/blog/tags/{TAGS[t]}/" for t in used_tags] + [e["url"] for e in essays]
    )
    s = s.replace("</urlset>", extra + "\n</urlset>")
    sm.write_text(s, encoding="utf-8")

    print(f"built {len(essays)} essays")


if __name__ == "__main__":
    main()
