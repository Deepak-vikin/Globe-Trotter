"""
recommendation_agent.py — Globe Trotter State-Level Tourist Recommender
Returns the top 5 tourist destinations in the user's STATE (derived from
their registered city), ranked by real-time tourist popularity.

Pipeline:
  1. Geocode the *state* to get its Nominatim area ID → Overpass area ID.
  2. Query Overpass for major tourist/historic/natural POIs inside the
     state boundary that have a Wikidata tag (quality filter).
  3. Fetch Wikidata sitelinks count for each POI (proxy for global fame /
     tourist rating — more sitelinks = more notable worldwide).
  4. Sort by sitelinks count (descending) and pick the top 5.
  5. Fetch Wikipedia thumbnail images for each.

Example: city=Chennai → state=Tamil Nadu → returns top 5 tourist
destinations across Tamil Nadu by global notability.
"""

import httpx
import asyncio
import hashlib
import math
from typing import Optional

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL  = "https://overpass-api.de/api/interpreter"
MEDIAWIKI_API = "https://en.wikipedia.org/w/api.php"
WIKIDATA_API  = "https://www.wikidata.org/w/api.php"

HEADERS_OSM = {
    "User-Agent": "GlobeTrotter/1.0",
    "Accept": "application/json",
}

HEADERS_WIKI = {
    "User-Agent": "GlobeTrotterApp/1.0 (https://github.com/student; globetrotter@example.com)",
    "Accept": "application/json",
}

FINAL_LIMIT = 5   # Show top 5 on frontend

# Names to skip — too generic to be useful tourist recommendations
SKIP_WORDS = {
    "junction", "corner", "circle", "stop", "bus stand",
    "entrance", "water sports", "rope way", "ropeway", "boating",
}


# ──────────────────────────────────────────────
# Step 1 — Resolve state → Overpass area ID
# ──────────────────────────────────────────────
async def _get_state_osm_id(
    state: str, country: str = ""
) -> Optional[int]:
    """
    Use Nominatim to find the OSM relation ID for the given state,
    then convert it to an Overpass area ID (relation_id + 3_600_000_000).
    """
    query = ", ".join(p for p in (state, country) if p)
    params = {
        "q": query,
        "format": "json",
        "limit": 5,
        "featuretype": "state",
    }
    async with httpx.AsyncClient(headers=HEADERS_OSM, timeout=15) as client:
        resp = await client.get(NOMINATIM_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    if not data:
        return None

    # Prefer administrative boundary results
    for item in data:
        osm_type = item.get("osm_type", "")
        osm_id   = int(item.get("osm_id", 0))
        if osm_type == "relation" and osm_id > 0:
            return 3_600_000_000 + osm_id  # Overpass area ID

    # Fallback: use first result
    osm_type = data[0].get("osm_type", "")
    osm_id   = int(data[0].get("osm_id", 0))
    if osm_type == "relation" and osm_id > 0:
        return 3_600_000_000 + osm_id
    return None


async def geocode_location(
    city: str, state: str = "", country: str = ""
) -> Optional[tuple[float, float]]:
    """Return (lat, lon) for the given location, or None."""
    query = ", ".join(p for p in (city, state, country) if p)
    params = {"q": query, "format": "json", "limit": 1}

    async with httpx.AsyncClient(headers=HEADERS_OSM, timeout=15) as client:
        resp = await client.get(NOMINATIM_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    if not data:
        return None
    return float(data[0]["lat"]), float(data[0]["lon"])


# ──────────────────────────────────────────────
# Step 2 — Overpass: tourism POIs across the STATE
# ──────────────────────────────────────────────
def _is_good_name(name: str) -> bool:
    """Filter out names that are too generic to be real tourist spots."""
    lower = name.lower().strip()
    if len(lower) < 4:
        return False
    for skip in SKIP_WORDS:
        if lower == skip or lower.endswith(f" {skip}"):
            return False
    return True


async def fetch_state_tourist_spots(
    area_id: int, limit: int = 100
) -> list[dict]:
    """
    Query Overpass for tourism/historic/leisure/natural POIs
    inside the state area boundary. Only returns spots with a
    Wikidata tag for quality filtering.
    """
    overpass_query = f"""
    [out:json][timeout:60];
    area({area_id})->.searchArea;
    (
      nwr["tourism"~"attraction|museum|viewpoint|zoo|theme_park|gallery"]["name"]["wikidata"](area.searchArea);
      nwr["historic"~"castle|fort|monument|memorial|ruins|archaeological_site|temple"]["name"]["wikidata"](area.searchArea);
      nwr["leisure"~"park|garden|nature_reserve"]["name"]["wikidata"](area.searchArea);
      nwr["natural"~"beach|peak|waterfall|cave_entrance"]["name"]["wikidata"](area.searchArea);
    );
    out center tags qt;
    """

    async with httpx.AsyncClient(headers=HEADERS_OSM, timeout=60) as client:
        resp = await client.post(OVERPASS_URL, data={"data": overpass_query})
        resp.raise_for_status()
        data = resp.json()

    seen: set[str] = set()
    spots: list[dict] = []

    for el in data.get("elements", []):
        tags = el.get("tags", {})
        name = tags.get("name:en") or tags.get("name")
        if not name or name.lower() in seen:
            continue
        if not _is_good_name(name):
            continue
        seen.add(name.lower())

        spot_lat = el.get("lat") or el.get("center", {}).get("lat")
        spot_lon = el.get("lon") or el.get("center", {}).get("lon")

        spot_type = (
            tags.get("tourism")
            or tags.get("historic")
            or tags.get("leisure")
            or tags.get("natural")
            or "attraction"
        )

        wikidata_id = tags.get("wikidata", "")

        spots.append({
            "name": name,
            "lat":  spot_lat,
            "lon":  spot_lon,
            "type": spot_type.replace("_", " ").title(),
            "wikidata_id": wikidata_id,
        })

    return spots[:limit]


# ──────────────────────────────────────────────
# Step 2b — Fallback: radius-based search
# ──────────────────────────────────────────────
async def fetch_tourist_spots_radius(
    lat: float, lon: float, radius: int = 150_000, limit: int = 100
) -> list[dict]:
    """
    Fallback: query Overpass for tourist POIs within a radius.
    Used when we cannot resolve a state area ID.
    """
    overpass_query = f"""
    [out:json][timeout:30];
    (
      nwr["tourism"~"attraction|museum|viewpoint|zoo|theme_park|gallery"]["name"]["wikidata"](around:{radius},{lat},{lon});
      nwr["historic"~"castle|fort|monument|memorial|ruins|archaeological_site|temple"]["name"]["wikidata"](around:{radius},{lat},{lon});
      nwr["leisure"~"park|garden|nature_reserve"]["name"]["wikidata"](around:{radius},{lat},{lon});
      nwr["natural"~"beach|peak|waterfall|cave_entrance"]["name"]["wikidata"](around:{radius},{lat},{lon});
    );
    out center tags qt;
    """

    async with httpx.AsyncClient(headers=HEADERS_OSM, timeout=35) as client:
        resp = await client.post(OVERPASS_URL, data={"data": overpass_query})
        resp.raise_for_status()
        data = resp.json()

    seen: set[str] = set()
    spots: list[dict] = []

    for el in data.get("elements", []):
        tags = el.get("tags", {})
        name = tags.get("name:en") or tags.get("name")
        if not name or name.lower() in seen:
            continue
        if not _is_good_name(name):
            continue
        seen.add(name.lower())

        spot_lat = el.get("lat") or el.get("center", {}).get("lat")
        spot_lon = el.get("lon") or el.get("center", {}).get("lon")

        spot_type = (
            tags.get("tourism")
            or tags.get("historic")
            or tags.get("leisure")
            or tags.get("natural")
            or "attraction"
        )

        wikidata_id = tags.get("wikidata", "")

        spots.append({
            "name": name,
            "lat":  spot_lat,
            "lon":  spot_lon,
            "type": spot_type.replace("_", " ").title(),
            "wikidata_id": wikidata_id,
        })

    return spots[:limit]


# ──────────────────────────────────────────────
# Step 3 — Wikidata: fetch sitelinks count (popularity proxy)
# ──────────────────────────────────────────────
async def _fetch_sitelinks_count(
    wikidata_ids: list[str], client: httpx.AsyncClient
) -> dict[str, int]:
    """
    Fetch the number of sitelinks for each Wikidata entity.
    More sitelinks = more globally notable = higher tourist rating.
    Processes in batches of 50 (Wikidata API limit).
    """
    result: dict[str, int] = {}
    if not wikidata_ids:
        return result

    # De-duplicate and filter valid IDs
    valid_ids = [qid for qid in set(wikidata_ids) if qid.startswith("Q")]

    for i in range(0, len(valid_ids), 50):
        batch = valid_ids[i:i + 50]
        try:
            resp = await client.get(WIKIDATA_API, params={
                "action": "wbgetentities",
                "ids": "|".join(batch),
                "props": "sitelinks",
                "format": "json",
            }, timeout=15)
            if resp.status_code != 200:
                continue
            data = resp.json()
            entities = data.get("entities", {})
            for qid, entity in entities.items():
                sitelinks = entity.get("sitelinks", {})
                result[qid] = len(sitelinks)
        except Exception:
            continue

    return result


async def rank_spots_by_popularity(spots: list[dict]) -> list[dict]:
    """
    Rank spots by Wikidata sitelinks count (popularity).
    Spots with more sitelinks are more famous / higher tourist rating.
    """
    wikidata_ids = [s["wikidata_id"] for s in spots if s.get("wikidata_id")]

    async with httpx.AsyncClient(headers=HEADERS_WIKI, timeout=20,
                                  follow_redirects=True) as client:
        sitelinks_map = await _fetch_sitelinks_count(wikidata_ids, client)

    # Assign popularity score
    for spot in spots:
        qid = spot.get("wikidata_id", "")
        spot["popularity"] = sitelinks_map.get(qid, 0)

    # Sort by popularity descending
    spots.sort(key=lambda x: x["popularity"], reverse=True)
    return spots


# ──────────────────────────────────────────────
# Step 4 — Wikipedia image search (MediaWiki API)
# ──────────────────────────────────────────────
async def _wiki_image_search(
    place_name: str, state: str, client: httpx.AsyncClient
) -> Optional[str]:
    """
    Use MediaWiki action=query API with generator=search and pageimages
    to find a thumbnail for a tourist spot.
    Tries 'place_name state' first, then just 'place_name'.
    """
    search_terms = []
    if state:
        search_terms.append(f"{place_name} {state}")
    search_terms.append(place_name)

    for term in search_terms:
        try:
            resp = await client.get(MEDIAWIKI_API, params={
                "action": "query",
                "generator": "search",
                "gsrsearch": term,
                "gsrlimit": 1,
                "prop": "pageimages",
                "piprop": "thumbnail",
                "pithumbsize": 480,
                "format": "json",
            }, timeout=8)

            if resp.status_code != 200:
                continue

            data = resp.json()
            pages = data.get("query", {}).get("pages", {})

            for pid, page in pages.items():
                thumb = page.get("thumbnail", {}).get("source")
                if thumb:
                    return thumb
        except Exception:
            continue

    return None


def _placeholder(place_name: str) -> str:
    """Generate a deterministic placeholder image using picsum.photos."""
    seed = hashlib.md5(place_name.encode()).hexdigest()[:8]
    return f"https://picsum.photos/seed/{seed}/480/320"


async def enrich_with_images(
    spots: list[dict], state: str, limit: int = FINAL_LIMIT
) -> list[dict]:
    """
    Add images to spots. Prioritize famous spots (ones with Wikipedia
    images). Returns at most `limit` spots.
    """
    async with httpx.AsyncClient(headers=HEADERS_WIKI, timeout=15,
                                  follow_redirects=True) as client:
        tasks = [_wiki_image_search(s["name"], state, client) for s in spots[:limit * 3]]
        images = await asyncio.gather(*tasks, return_exceptions=True)

    famous_spots = []
    remaining_spots = []

    for spot, img in zip(spots, images):
        # Remove internal fields before sending to frontend
        spot.pop("wikidata_id", None)
        spot.pop("popularity", None)
        spot.pop("dist", None)

        if isinstance(img, str) and img:
            spot["image"] = img
            famous_spots.append(spot)
        else:
            spot["image"] = _placeholder(spot["name"])
            remaining_spots.append(spot)

    final_spots = famous_spots[:limit]
    if len(final_spots) < limit:
        needed = limit - len(final_spots)
        final_spots.extend(remaining_spots[:needed])

    return final_spots


# ──────────────────────────────────────────────
# Public entry-point
# ──────────────────────────────────────────────
async def get_recommendations(
    city: str, state: str = "", country: str = ""
) -> dict:
    """
    Main function called by the API route.
    Returns the top 5 tourist destinations in the user's STATE,
    ranked by tourist popularity (Wikidata sitelinks).

    Example: city=Chennai, state=Tamil Nadu, country=India
    → returns top 5 tourist destinations across Tamil Nadu.
    """
    # Try state-level area search first
    spots = []
    if state:
        area_id = await _get_state_osm_id(state, country)
        if area_id:
            print(f"[REC] State area ID for '{state}': {area_id}")
            spots = await fetch_state_tourist_spots(area_id)

    # Fallback: radius-based search from the city
    if not spots:
        coords = await geocode_location(city, state, country)
        if coords is None:
            return {"location": city, "spots": [], "error": "Could not geocode location."}
        lat, lon = coords
        print(f"[REC] Fallback: radius search from {city} @ ({lat}, {lon})")
        spots = await fetch_tourist_spots_radius(lat, lon)

    if not spots:
        location_str = ", ".join(p for p in (city, state, country) if p)
        return {"location": location_str, "spots": [], "error": "No tourist spots found."}

    # Rank by popularity (Wikidata sitelinks count)
    spots = await rank_spots_by_popularity(spots)

    print(f"[REC] Top spots in '{state or city}': "
          + ", ".join(f"{s['name']} ({s.get('popularity', 0)})" for s in spots[:FINAL_LIMIT]))

    # Enrich top candidates with images
    spots = await enrich_with_images(spots, state or city)

    location_str = ", ".join(p for p in (state, country) if p) or city

    # Geocode the city for map centering
    coords = await geocode_location(city, state, country)
    lat, lon = coords if coords else (0, 0)

    return {
        "location": location_str,
        "region": state or city,
        "lat": lat,
        "lon": lon,
        "spots": spots,
    }
