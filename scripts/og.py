"""The link preview (public/og.png, 1200x630): today's verdict beside a dot map of every store, drawn from stock.json.

Rendered after each poll so a shared link always shows the latest numbers. The map is MapLibre + OpenFreeMap tiles.
"""

import json
import os
from html import escape

from scripts.history import CODE

WIDTH, HEIGHT = 1200, 630
COLOURS = {"in": "#1F9D5A", "low": "#E8891C", "out": "#D23A4E", "unknown": "#8C7B70"}
COMPASS = ('<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="none" '
           'stroke="currentColor" stroke-width="2.5"/><path d="M15.8 8.2 13.6 13.6 8.2 15.8 10.4 10.4Z" '
           'fill="currentColor" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>')
# Draw the good news last so it sits on top.
DRAW_ORDER = ("not_sold", "out", "low", "in")


def first_product(stock):
    """The preview shows the first product in data/products.json, as the old single-product shape."""
    product = stock["products"][0]
    status = {code: name for name, code in CODE.items()}
    stores = [{**s, "status": status[c]} for s, c in zip(stock["stores"], product["statuses"])]
    return {"counts": product["counts"], "stores": stores}


def verdict(have, pct):
    """Same words as the page: 'NOPE.', 'BARELY.', 'SORT OF.', 'YES!'."""
    if have == 0:
        return "NOPE."
    if pct < 15:
        return "BARELY."
    if pct < 50:
        return "SORT OF."
    return "YES!"


def summary(counts):
    # Stores with no reading are left out everywhere a visitor could see them.
    sold = counts["in"] + counts["low"] + counts["out"]
    have = counts["in"] + counts["low"]
    return have, sold, round(100 * have / sold) if sold else 0


def features(stores):
    """Visible stores as GeoJSON, good news last so it draws on top. Stores with no reading are left out."""
    order = sorted((s for s in stores if s["status"] in DRAW_ORDER), key=lambda s: DRAW_ORDER.index(s["status"]))
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [s["lng"], s["lat"]]},
         "properties": {"status": s["status"]}} for s in order]}


def html(stock):
    have, sold, pct = summary(stock["counts"])
    # The site's Mapbox token only works on the live site, so the preview draws its map with MapLibre and
    # OpenFreeMap's keyless OpenStreetMap tiles, recoloured to match. window.ogReady flips once tiles and dots are in.
    return f"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Bagel+Fat+One&family=DM+Sans:wght@500;700&display=block"
  rel="stylesheet">
<link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet">
<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<style>
  html, body {{ margin: 0; width: {WIDTH}px; height: {HEIGHT}px; overflow: hidden; background: #F3E6D3;
    font-family: "DM Sans", sans-serif; color: #3B2216; }}
  #map {{ position: absolute; inset: 0; }}
  .card {{ position: absolute; left: 40px; top: 40px; bottom: 40px; width: 470px; padding: 40px 40px 34px;
    box-sizing: border-box; background: #F6C344; border: 5px solid #3B2216; border-radius: 36px;
    box-shadow: 0 8px 0 #3B2216; display: flex; flex-direction: column; }}
  .eyebrow {{ font-weight: 700; font-size: 20px; letter-spacing: .14em; text-transform: uppercase; opacity: .75; }}
  .live {{ display: inline-block; width: 14px; height: 14px; margin: 0 10px 1px 0; border-radius: 50%;
    background: #D23A4E; box-shadow: 0 0 0 5px rgba(210,58,78,.25); }}
  h1 {{ margin: 6px 0 0; font: 400 60px/0.95 "Bagel Fat One"; color: #B5328C; }}
  .answer {{ margin: 18px 0 0; font: 400 92px/1 "Bagel Fat One"; }}
  .stat {{ margin: 14px 0 0; font-size: 27px; line-height: 1.3; }}
  .stat b {{ font-weight: 700; }}
  .cta {{ margin-top: auto; display: inline-block; align-self: flex-start; padding: 12px 24px; background: #B5328C;
    color: #fff; border: 4px solid #3B2216; border-radius: 999px; font-weight: 700; font-size: 24px;
    box-shadow: 0 5px 0 #3B2216; }}
  .cta .icon {{ width: 26px; height: 26px; vertical-align: -5px; margin-right: 6px; }}
  .credit {{ position: absolute; right: 12px; bottom: 8px; font-size: 12px; opacity: .6; }}
</style></head><body>
<div id="map"></div>
<div class="card">
  <div class="eyebrow"><span class="live"></span>Live</div>
  <h1>Is the Pudding In?</h1>
  <div class="answer">{escape(verdict(have, pct))}</div>
  <div class="stat"><b>{have}</b> of {sold} M&amp;S stores have the banana, caramel &amp; pecan pudding
    right now</div>
  <div class="cta">{COMPASS} See the live map</div>
</div>
<div class="credit">© OpenFreeMap © OpenStreetMap</div>
<script>
  window.ogReady = false;
  setTimeout(() => (window.ogReady = true), 20000);  // never hang the poll: fall back to whatever has drawn
  const map = new maplibregl.Map({{ container: "map", style: "https://tiles.openfreemap.org/styles/positron",
    bounds: [[-0.4, 51.425], [0.12, 51.595]],
    fitBoundsOptions: {{ padding: {{ top: 20, bottom: 20, left: 520, right: 20 }} }},
    interactive: false, attributionControl: false, fadeDuration: 0 }});
  map.on("load", () => {{
    for (const {{ id, type }} of map.getStyle().layers) {{
      if (type === "background") map.setPaintProperty(id, "background-color", "#F3E6D3");
      else if (type === "fill") map.setPaintProperty(id, "fill-color", id.includes("water") ? "#EBC6DD" : "#EFE0CB");
      else if (type === "symbol" && !/city|town|place/.test(id)) map.setLayoutProperty(id, "visibility", "none");
    }}
    map.addSource("stores", {{ type: "geojson", data: {json.dumps(features(stock["stores"]))} }});
    map.addLayer({{ id: "not_sold", type: "circle", source: "stores", filter: ["==", ["get", "status"], "not_sold"],
      paint: {{ "circle-color": "rgba(0,0,0,0)", "circle-radius": 4, "circle-stroke-color": "#9A8473",
        "circle-stroke-width": 2 }} }});
    map.addLayer({{ id: "stores", type: "circle", source: "stores", filter: ["!=", ["get", "status"], "not_sold"],
      paint: {{ "circle-color": ["match", ["get", "status"], "in", "{COLOURS['in']}", "low", "{COLOURS['low']}",
          "{COLOURS['out']}"],
        "circle-radius": ["match", ["get", "status"], "in", 11, "low", 9, 7],
        "circle-stroke-color": "#3B2216", "circle-stroke-width": 2.5 }} }});
    map.once("idle", () => (window.ogReady = true));
  }});
</script>
</body></html>"""


def render(stock, path):
    """Screenshot the preview with headless Chromium."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel=os.environ.get("BROWSER_CHANNEL") or None)
        try:
            page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
            page.set_content(html(stock), wait_until="domcontentloaded")
            page.wait_for_function("window.ogReady === true", timeout=30_000)
            page.evaluate("document.fonts.ready")
            page.screenshot(path=str(path))
        finally:
            browser.close()
