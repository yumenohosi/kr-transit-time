"""City configurations (cities/<slug>.json), completed with defaults shared by every script.

A config only needs what cannot be deduced: name, network, sources (GTFS, OSM boundaries), centre of the map and the
`kind` of rail network ("tram", "metro" or "metro+tram"). Everything else (titles, labels, OSM areas…) has a
default below and can be overridden in the JSON when a city needs it.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CITIES_DIR = ROOT / "cities"

RAIL_NOUN = {"tram": "트램", "metro": "지하철", "metro+tram": "지하철·트램"}
RAIL_LABEL = {"tram": "트램", "metro": "지하철", "metro+tram": "지하철·트램"}
RAIL_STATIONS = {"tram": "트램 정류장", "metro": "지하철역", "metro+tram": "지하철역·트램 정류장"}
# Half-sizes (degrees of latitude, longitude) of the OSM areas around the centre.
OSM_HALF_SIZE = (0.22, 0.32)
PARKS_HALF_SIZE = (0.06, 0.08)


def with_defaults(raw: dict) -> dict:
    city = dict(raw)
    kind = city.setdefault("kind", "tram")
    lat, lon = city["defaultFrom"]["lat"], city["defaultFrom"]["lon"]
    city.setdefault("path", f"{city['slug']}/")
    city.setdefault("railNoun", RAIL_NOUN[kind])
    city.setdefault("railLabel", RAIL_LABEL[kind])
    city.setdefault("railStations", RAIL_STATIONS[kind])
    city.setdefault("title", f"{city['name']} 대중교통 시간 지도")
    city.setdefault("titleSuffix", f"지하철·버스 소요시간 · {city['network']}")
    city.setdefault("busNoun", "버스")
    city.setdefault("busLabel", "버스")
    city.setdefault("area", city["metropole"])
    city.setdefault("railGeometry", "gtfs")
    city.setdefault("lat0", round(lat, 2))
    city.setdefault("osmBbox", [round(lat - OSM_HALF_SIZE[0], 2), round(lon - OSM_HALF_SIZE[1], 2),
                                round(lat + OSM_HALF_SIZE[0], 2), round(lon + OSM_HALF_SIZE[1], 2)])
    city.setdefault("parksBbox", [round(lat - PARKS_HALF_SIZE[0], 2), round(lon - PARKS_HALF_SIZE[1], 2),
                                  round(lat + PARKS_HALF_SIZE[0], 2), round(lon + PARKS_HALF_SIZE[1], 2)])
    city.setdefault("osmRailBbox", city["osmBbox"])
    city.setdefault(
        "ogAlt",
        f"{city['defaultFrom']['label']}에서 출발하는 대중교통 소요시간으로 색칠한 {city['name']} 지도, "
        "15분·30분 등시선 포함.",
    )
    return city


def load_city(slug: str) -> dict:
    return with_defaults(json.loads((CITIES_DIR / f"{slug}.json").read_text(encoding="utf-8")))


def load_cities(include_rankings_only: bool = False) -> list[dict]:
    """Cities with a map. Some cities only appear in the rankings (`rankingsOnly`, Paris: its map is Jules Grandin's)."""
    cities = [with_defaults(json.loads(path.read_text(encoding="utf-8"))) for path in CITIES_DIR.glob("*.json")]
    cities = [city for city in cities if include_rankings_only or not city.get("rankingsOnly")]
    return sorted(cities, key=lambda city: city["order"])
