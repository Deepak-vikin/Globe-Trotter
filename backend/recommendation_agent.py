"""
recommendation_agent.py — Returns top 5 tourist spots nearest to the user's city,
ranked by global popularity (Wikidata sitelinks), loaded from a static India cache.
"""

import httpx
import asyncio
import hashlib
import math
import time
import json
import os
from typing import Optional

# ── Config ────────────────────────────────────────────────────────────────────
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
MEDIAWIKI_API = "https://en.wikipedia.org/w/api.php"
WIKIDATA_API  = "https://www.wikidata.org/w/api.php"
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
HEADERS_OSM  = {"User-Agent": "GlobeTrotter/1.0", "Accept": "application/json"}
HEADERS_WIKI = {"User-Agent": "GlobeTrotterApp/1.0", "Accept": "application/json"}

FINAL_LIMIT = 5
CACHE_TTL   = 1800   # 30 minutes
MAX_RETRIES = 3
BASE_DELAY  = 10     # seconds

_cache: dict[str, tuple[float, dict]] = {}

SKIP_WORDS = {
    "junction", "corner", "circle", "stop", "bus stand",
    "entrance", "water sports", "rope way", "ropeway", "boating",
}


# ── Utilities ─────────────────────────────────────────────────────────────────
def haversine_distance(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def _retry_request(client, method, url, retries=MAX_RETRIES, **kwargs):
    for attempt in range(retries):
        resp = await (client.get(url, **kwargs) if method == "GET"
                      else client.post(url, **kwargs))
        if resp.status_code not in (429, 504):
            return resp
        wait = BASE_DELAY * (2 ** attempt)
        print(f"[REC] {resp.status_code} from {url[:50]}… retry {attempt+1}/{retries} in {wait}s")
        await asyncio.sleep(wait)
    return resp


async def _overpass_query(client, query_str):
    for url in OVERPASS_URLS:
        try:
            resp = await _retry_request(client, "POST", url, retries=2, data={"data": query_str})
            if resp.status_code == 200:
                return resp
        except Exception as e:
            print(f"[REC] Overpass mirror {url[:40]} failed: {e}")
    raise RuntimeError("All Overpass mirrors failed")


# ── Geocoding ─────────────────────────────────────────────────────────────────
async def geocode_location(city: str, state: str = "", country: str = "") -> Optional[tuple]:
    query = ", ".join(p for p in (city, state, country) if p)
    async with httpx.AsyncClient(headers=HEADERS_OSM, timeout=15) as client:
        resp = await _retry_request(client, "GET", NOMINATIM_URL,
                                    params={"q": query, "format": "json", "limit": 1})
        resp.raise_for_status()
        data = resp.json()
    if not data:
        return None
    return float(data[0]["lat"]), float(data[0]["lon"])


# ── Overpass: radius-based tourist spot search ────────────────────────────────
def _is_good_name(name: str) -> bool:
    lower = name.lower().strip()
    if len(lower) < 4:
        return False
    return not any(lower == w or lower.endswith(f" {w}") for w in SKIP_WORDS)


async def fetch_tourist_spots_radius(lat: float, lon: float,
                                     radius: int = 500_000, limit: int = 200) -> list[dict]:
    query = f"""
    [out:json][timeout:30];
    (
      nwr["tourism"~"attraction|museum|viewpoint|zoo|theme_park|gallery"]["name"]["wikidata"](around:{radius},{lat},{lon});
      nwr["historic"~"castle|fort|monument|memorial|ruins|archaeological_site|temple"]["name"]["wikidata"](around:{radius},{lat},{lon});
      nwr["leisure"~"park|garden|nature_reserve"]["name"]["wikidata"](around:{radius},{lat},{lon});
      nwr["natural"~"beach|peak|waterfall|cave_entrance"]["name"]["wikidata"](around:{radius},{lat},{lon});
    );
    out center tags qt;
    """
    async with httpx.AsyncClient(headers=HEADERS_OSM, timeout=90) as client:
        resp = await _overpass_query(client, query)
        resp.raise_for_status()
        data = resp.json()

    seen, spots = set(), []
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        name = tags.get("name:en") or tags.get("name")
        if not name or name.lower() in seen or not _is_good_name(name):
            continue
        seen.add(name.lower())
        spot_type = (tags.get("tourism") or tags.get("historic") or
                     tags.get("leisure") or tags.get("natural") or "attraction")
        spots.append({
            "name": name,
            "lat":  el.get("lat") or el.get("center", {}).get("lat"),
            "lon":  el.get("lon") or el.get("center", {}).get("lon"),
            "type": spot_type.replace("_", " ").title(),
            "wikidata_id": tags.get("wikidata", ""),
        })
    return spots[:limit]


# ── Wikidata: popularity score ─────────────────────────────────────────────────
async def _fetch_sitelinks(wikidata_ids: list[str], client) -> dict[str, int]:
    result = {}
    valid = [q for q in set(wikidata_ids) if q.startswith("Q")]
    for i in range(0, len(valid), 50):
        try:
            resp = await client.get(WIKIDATA_API, params={
                "action": "wbgetentities", "ids": "|".join(valid[i:i+50]),
                "props": "sitelinks", "format": "json",
            }, timeout=15)
            if resp.status_code == 200:
                for qid, entity in resp.json().get("entities", {}).items():
                    result[qid] = len(entity.get("sitelinks", {}))
        except Exception:
            continue
    return result


async def rank_spots_by_popularity(spots: list[dict]) -> list[dict]:
    ids = [s["wikidata_id"] for s in spots if s.get("wikidata_id")]
    async with httpx.AsyncClient(headers=HEADERS_WIKI, timeout=20,
                                  follow_redirects=True) as client:
        sitelinks = await _fetch_sitelinks(ids, client)
    for spot in spots:
        spot["popularity"] = sitelinks.get(spot.get("wikidata_id", ""), 0)
    spots.sort(key=lambda x: x["popularity"], reverse=True)
    return spots


# ── Wikipedia images ───────────────────────────────────────────────────────────
def _placeholder(name: str) -> str:
    seed = hashlib.md5(name.encode()).hexdigest()[:8]
    return f"https://picsum.photos/seed/{seed}/480/320"


async def _wiki_image(name: str, state: str, client) -> Optional[str]:
    for term in ([f"{name} {state}", name] if state else [name]):
        try:
            resp = await client.get(MEDIAWIKI_API, params={
                "action": "query", "generator": "search", "gsrsearch": term,
                "gsrlimit": 1, "prop": "pageimages", "piprop": "thumbnail",
                "pithumbsize": 480, "format": "json",
            }, timeout=8)
            if resp.status_code == 200:
                for pid, page in resp.json().get("query", {}).get("pages", {}).items():
                    thumb = page.get("thumbnail", {}).get("source")
                    if thumb:
                        return thumb
        except Exception:
            continue
    return None


async def enrich_with_images(spots: list[dict], state: str,
                              limit: int = FINAL_LIMIT) -> list[dict]:
    async with httpx.AsyncClient(headers=HEADERS_WIKI, timeout=15,
                                  follow_redirects=True) as client:
        images = await asyncio.gather(
            *[_wiki_image(s["name"], state, client) for s in spots[:limit * 3]],
            return_exceptions=True,
        )
    famous, rest = [], []
    for spot, img in zip(spots, images):
        spot.pop("wikidata_id", None)
        spot.pop("popularity", None)
        spot.pop("dist", None)
        if isinstance(img, str) and img:
            spot["image"] = img
            famous.append(spot)
        else:
            spot["image"] = _placeholder(spot["name"])
            rest.append(spot)
    final = famous[:limit]
    if len(final) < limit:
        final.extend(rest[:limit - len(final)])
    return final


# ── Public entry-point ────────────────────────────────────────────────────────
async def get_recommendations(city: str, state: str = "", country: str = "") -> dict:
    cache_key = f"{city}|{state}|{country}".lower()
    if cache_key in _cache:
        ts, data = _cache[cache_key]
        if time.time() - ts < CACHE_TTL:
            print(f"[REC] Cache hit for '{city}' (age {int(time.time()-ts)}s)")
            return data

    coords = await geocode_location(city, state, country)
    if not coords:
        return {"location": city, "spots": [], "error": "Could not geocode location."}
    lat, lon = coords
    print(f"[REC] Processing search from {city} @ ({lat}, {lon})")

    # Try static India cache first
    spots = []
    if "india" in country.lower() or not country:
        spots_file = os.path.join(os.path.dirname(__file__), "india_spots.json")
        try:
            with open(spots_file, "r", encoding="utf-8") as f:
                spots = json.load(f)
            print(f"[REC] Loaded {len(spots)} spots from static India cache.")
        except IOError:
            print("[REC] Static cache not found, falling back to live APIs.")

    if not spots:
        spots = await fetch_tourist_spots_radius(lat, lon, radius=500_000, limit=200)
        if spots:
            spots = await rank_spots_by_popularity(spots)
            spots = await enrich_with_images(spots, state or city)

    if not spots:
        return {"location": city, "spots": [], "error": "No cities found."}

    # Sort top 100 by distance, return nearest 5
    for s in spots[:100]:
        s["dist"] = haversine_distance(lat, lon, s["lat"], s["lon"])
    top = sorted(spots[:100], key=lambda x: x["dist"])[:FINAL_LIMIT]

    print(f"[REC] Top nearest to '{city}': " +
          ", ".join(f"{s['name']} ({round(s.get('dist',0),1)}km)" for s in top))

    result = {
        "location": ", ".join(p for p in (state, country) if p) or city,
        "region": state or city,
        "lat": lat, "lon": lon,
        "spots": top,
    }
    _cache[cache_key] = (time.time(), result)
    return result
