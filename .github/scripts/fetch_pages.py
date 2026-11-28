"""Descarga páginas de cartelera (cine y gastronomía) y las guarda como texto en feeds/.
Uso: python3 fetch_pages.py   (escribe feeds/*.txt y devuelve los nombres que fallaron en feeds/.failed)"""
import html, json, os, re, sys, urllib.request, xml.etree.ElementTree as ET
from html.parser import HTMLParser

UA = "Mozilla/5.0 (compatible; AgendaSCZ/1.0; +https://kkscz.github.io/agenda-scz/)"

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "es-BO,es;q=0.9"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode(r.headers.get_content_charset() or "utf-8", "replace")

class Text(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "head", "template"}
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article", "header", "footer", "td", "figcaption"}
    def __init__(self):
        super().__init__(); self.out = []; self.skip = 0; self.links = []
    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP: self.skip += 1
        elif tag in self.BLOCK: self.out.append("\n")
        if tag == "a":
            href = dict(attrs).get("href")
            if href: self.links.append(href)
    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip: self.skip -= 1
        elif tag in self.BLOCK: self.out.append("\n")
    def handle_data(self, d):
        if not self.skip: self.out.append(d)

def to_text(page):
    p = Text(); p.feed(page)
    t = html.unescape("".join(p.out))
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t)
    return t.strip(), p.links

def save(name, url, text):
    with open(f"feeds/{name}.txt", "w", encoding="utf-8") as f:
        f.write(f"Fuente: {url}\n\n{text}\n")
    print(f"{name}: OK ({len(text)} caracteres)")

failed = []

# Cine: estrenos y cartelera de Bolivia.com
for name, url in [("cine-estrenos", "https://www.bolivia.com/cine/proximos-estrenos/"),
                  ("cine-cartelera", "https://www.bolivia.com/cine/")]:
    try:
        text, _ = to_text(get(url))
        if len(text) < 500: raise ValueError("página casi vacía")
        save(name, url, text)
    except Exception as e:
        print(f"::warning::{name}: {e}"); failed.append(name)

# Gastronomía: las publicaciones más recientes de Gourmet Magazine Bolivia
try:
    base = "https://www.gourmetmagazinebolivia.com"
    posts = []
    try:
        rss = ET.fromstring(get(base + "/blog-feed.xml").encode("utf-8"))
        for it in rss.iter("item"):
            posts.append({"title": (it.findtext("title") or "").strip(), "url": (it.findtext("link") or "").strip(),
                          "date": (it.findtext("pubDate") or "").strip()})
    except Exception as e:
        print(f"gourmet: sin RSS ({e}); se usa la portada")
        _, links = to_text(get(base + "/"))
        seen = set()
        for h in links:
            if "/post/" in h:
                u = h if h.startswith("http") else base + h
                if u not in seen: seen.add(u); posts.append({"title": "", "url": u, "date": ""})
    if not posts: raise ValueError("no se encontraron publicaciones")
    parts = ["Publicaciones recientes:"] + [f"- {p['date']} | {p['title']} | {p['url']}" for p in posts[:15]]
    for p in posts[:4]:
        try:
            text, _ = to_text(get(p["url"]))
            parts.append(f"\n\n===== {p['title'] or p['url']} ({p['date']})\n{p['url']}\n\n{text[:20000]}")
        except Exception as e:
            parts.append(f"\n\n===== {p['url']}: no se pudo leer ({e})")
    save("gourmet", base, "\n".join(parts))
except Exception as e:
    print(f"::warning::gourmet: {e}"); failed.append("gourmet")

with open("feeds/.failed", "w") as f:
    f.write(" ".join(failed))
