"""Abre en un navegador (Chromium, con Playwright) las páginas que solo muestran su contenido con JavaScript,
y guarda el texto visible, los enlaces y las respuestas JSON que la página pidió.
- Ticketeg siempre (su portada lista los eventos en venta).
- Además, reintenta con navegador las páginas de fetch_pages.py que fallaron (las que figuran en feeds/.failed).
Uso: python3 fetch_rendered.py   (escribe feeds/*.txt / feeds/*.json y deja en feeds/.failed solo lo que sigue fallando)"""
import json, os, sys

RENDER = {
    "ticketeg": "https://ticketeg.com/#/",
}
RETRY = {
    "eldeber-cultura": "https://eldeber.com.bo/cultura-y-entretenimiento",
    "bolivamos-nuevos": "https://bolivamos.com/just-announced/",
    "bolivamos-finde": "https://bolivamos.com/events/this-weekend/",
    "bolivamos-musica": "https://bolivamos.com/categories/live-music/",
    "bolivamos-cultura": "https://bolivamos.com/categories/culture/",
    "sonilum-plaza": "https://www.vamoseventos.com/venue/ad7ef1ae-b0ef-44c4-9c23-a5673c62daed",
    "sonilum-arena": "https://www.vamoseventos.com/venue/ef611e1c-de2a-423d-a023-498e710a1794",
    "cine-estrenos": "https://www.bolivia.com/cine/proximos-estrenos/",
    "cine-cartelera": "https://www.bolivia.com/cine/",
}

failed = open("feeds/.failed").read().split() if os.path.exists("feeds/.failed") else []
todo = dict(RENDER)
todo.update({n: RETRY[n] for n in failed if n in RETRY})
still = [n for n in failed if n not in todo]

try:
    from playwright.sync_api import sync_playwright
except ImportError as e:
    print(f"::warning::Playwright no está instalado ({e})")
    with open("feeds/.failed", "w") as f: f.write(" ".join(failed + list(RENDER)))
    sys.exit(0)

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 AgendaSCZ/1.0"

with sync_playwright() as p:
    browser = p.chromium.launch()
    for name, url in todo.items():
        ctx = browser.new_context(user_agent=UA, locale="es-BO", viewport={"width": 1280, "height": 2000})
        page = ctx.new_page()
        captured = []
        def on_response(r):
            try:
                if "json" in (r.headers.get("content-type") or "") and len(captured) < 40:
                    body = r.text()
                    if 20 < len(body) < 2_000_000:
                        captured.append({"url": r.url, "body": json.loads(body)})
            except Exception:
                pass
        page.on("response", on_response)
        try:
            page.goto(url, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(4000)
            for _ in range(6):  # bajar por la página para que carguen las listas largas
                page.mouse.wheel(0, 2500); page.wait_for_timeout(800)
            text = page.inner_text("body")
            links = page.eval_on_selector_all("a[href]", "els => els.map(a => [a.href, (a.innerText||a.title||'').replace(/\\s+/g,' ').trim()])")
            imgs = page.eval_on_selector_all("img[alt]", "els => els.map(i => i.alt.trim()).filter(Boolean)")
            if len(text.strip()) < 200 and not captured:
                raise ValueError("página casi vacía aun con navegador")
            seen, lines = set(), []
            for h, t in links:
                if h not in seen: seen.add(h); lines.append(f"- {t or '(sin texto)'} | {h}")
            out = [f"Fuente: {url} (abierta con navegador)", "", text.strip()[:60000], "", "Enlaces encontrados:"] + lines[:300]
            if imgs: out += ["", "Textos de imágenes:"] + [f"- {a}" for a in imgs[:200]]
            with open(f"feeds/{name}.txt", "w", encoding="utf-8") as f: f.write("\n".join(out) + "\n")
            if captured:
                with open(f"feeds/{name}-api.json", "w", encoding="utf-8") as f:
                    json.dump(captured, f, ensure_ascii=False, indent=1)
            print(f"{name}: OK con navegador ({len(text)} caracteres, {len(captured)} respuestas JSON)")
        except Exception as e:
            print(f"::warning::{name}: {e}"); still.append(name)
        finally:
            ctx.close()
    browser.close()

with open("feeds/.failed", "w") as f:
    f.write(" ".join(still))
