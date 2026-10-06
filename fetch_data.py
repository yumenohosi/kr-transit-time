#!/usr/bin/env python3
"""Download the raw sources of a city into data/<city>/.

Usage: python3 fetch_data.py <city> [--gtfs-only | --skip-gtfs | --context-only | --rivers-only | --coast-only]
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
import urllib.parse
import urllib.request
from pathlib import Path

from build_data import assemble_rings, point_in_ring
from cities import load_city

ROOT = Path(__file__).resolve().parent
USER_AGENT = "tram.camilleroux.com/0.2 (build script)"
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]


def bbox(values) -> str:
    return ",".join(str(v) for v in values)


def download(url: str, data: bytes | None = None) -> bytes:
    request = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=300) as response:
        return response.read()


def overpass(query: str) -> bytes:
    payload = urllib.parse.urlencode({"data": query}).encode()
    for attempt in range(6):
        for url in OVERPASS_URLS:
            try:
                body = download(url, payload)
                # A query out of time or memory still answers 200, with what it got so far and a remark.
                remark = json.loads(body).get("remark", "")
                if "error" in remark:
                    raise RuntimeError(remark)
                return body
            except Exception as error:  # noqa: BLE001 - Overpass is often busy, just retry
                print(f"  {url} failed ({error}), retrying…")
        time.sleep(10 * (attempt + 1))
    raise RuntimeError("Overpass unavailable")


def record(out: Path, name: str, source: str, how: str = "download") -> None:
    """Note in data/<city>/manifest.json where each raw file comes from and when it was fetched."""
    manifest_path = out / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    path = out / name
    fetched = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) if how == "manual" else datetime.now(timezone.utc)
    manifest[name] = {
        "source": source,
        "how": how,
        "fetchedAt": fetched.isoformat(timespec="seconds"),
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def boundaries_geojson(payload: dict) -> dict:
    """OSM administrative boundaries as GeoJSON features with a `nom` property, the shape build_data.py reads."""
    features = []
    for relation in payload["elements"]:
        ways = [member for member in relation.get("members", []) if member["type"] == "way" and member.get("geometry")]

        def rings(inner: bool):
            return assemble_rings(
                [[(node["lon"], node["lat"]) for node in way["geometry"] if node] for way in ways if (way.get("role") == "inner") == inner]
            )

        outers, inners = rings(False), rings(True)
        polygons = [[outer, *(hole for hole in inners if point_in_ring(hole[0], outer))] for outer in outers]
        features.append(
            {
                "type": "Feature",
                "properties": {"nom": relation["tags"]["name"], "code": str(relation["id"])},
                "geometry": {"type": "MultiPolygon", "coordinates": [[[list(point) for point in ring] for ring in polygon] for polygon in polygons]},
            }
        )
    return {"type": "FeatureCollection", "features": features}


def fetch_context(city: dict, out: Path) -> None:
    """Land around the metropolis, for coastal cities: whatever is left uncovered on the map is drawn as sea."""
    departments = city.get("seaDepartments", [])
    if departments:
        print(f"Communes voisines (départements {', '.join(departments)})…")
        features = []
        urls = []
        for code in departments:
            url = f"https://geo.api.gouv.fr/departements/{code}/communes?fields=nom,code&format=geojson&geometry=contour"
            features += json.loads(download(url))["features"]
            urls.append(url)
        (out / "context.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")
        record(out, "context.geojson", " + ".join(urls))
    relations = city.get("contextOsmRelations", [])
    if relations:
        print("Territoires voisins hors de France (OSM)…")
        query = "[out:json][timeout:110];(" + "".join(f"relation({rel});" for rel in relations) + ");out geom;"
        (out / "context_osm.json").write_bytes(overpass(query))
        record(out, "context_osm.json", f"Overpass API: {query}")


def fetch_rivers(city: dict, out: Path) -> None:
    """Rivers crossed on foot only by a bridge (`"rivers"`: names, and their « La Loire - Bras de Pirmil » parts)."""
    if not city.get("rivers"):
        return
    print("하천 (OSM)…")
    names = "|".join(re.escape(name) for name in city["rivers"])
    query = (
        f'[out:json][timeout:110];way["waterway"="river"]["name"~"^({names})( - .*)?$"]["tunnel"!~"."]'
        f'({bbox(city["osmBbox"])});out geom;'
    )
    (out / "osm_rivers.json").write_bytes(overpass(query))
    record(out, "osm_rivers.json", f"Overpass API: {query}")
    # Bridges open to pedestrians: the ones over these rivers are kept by build_data.py.
    query = (
        '[out:json][timeout:110];way["bridge"]["highway"]'
        '["highway"!~"^(motorway|motorway_link|trunk|trunk_link|construction|proposed)$"]["foot"!="no"]'
        f'({bbox(city["osmBbox"])});out geom;'
    )
    (out / "osm_bridges.json").write_bytes(overpass(query))
    record(out, "osm_bridges.json", f"Overpass API: {query}")


def fetch_coastline(city: dict, out: Path) -> None:
    """Coastline around the city (`"coastline": true`): Korean district boundaries run far out to sea, and
    build_data.py cuts them back to the land."""
    if not city.get("coastline"):
        return
    print("해안선 (OSM)…")
    points = [point for feature in json.loads((out / "communes.geojson").read_text(encoding="utf-8"))["features"]
              for polygon in feature["geometry"]["coordinates"] for point in polygon[0]]
    lons, lats = [lon for lon, _ in points], [lat for _, lat in points]
    area = bbox([round(min(lats) - 0.15, 3), round(min(lons) - 0.15, 3), round(max(lats) + 0.15, 3), round(max(lons) + 0.15, 3)])
    query = f'[out:json][timeout:110];way["natural"="coastline"]({area});out geom;'
    (out / "osm_coastline.json").write_bytes(overpass(query))
    record(out, "osm_coastline.json", f"Overpass API: {query}")


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    city = load_city(sys.argv[1])
    out = ROOT / "data" / city["slug"]
    out.mkdir(parents=True, exist_ok=True)
    if "--context-only" in sys.argv:
        fetch_context(city, out)
        return
    if "--rivers-only" in sys.argv:
        fetch_rivers(city, out)
        return
    if "--coast-only" in sys.argv:
        fetch_coastline(city, out)
        return

    if "--skip-gtfs" not in sys.argv:
        print(f"GTFS {city['network']}…")
        if city.get("gtfsManual"):
            # Some feeds need an account or a build step: the file is put in place by hand.
            if not (out / "gtfs.zip").exists():
                sys.exit(f"GTFS를 직접 준비해({city['gtfsManual']}) {out / 'gtfs.zip'}에 두세요")
            print(f"  수동 파일 사용 ({city['gtfsManual']})")
            record(out, "gtfs.zip", city["gtfsUrl"], how="manual")
        else:
            (out / "gtfs.zip").write_bytes(download(city["gtfsUrl"]))
            record(out, "gtfs.zip", city["gtfsUrl"])
    if "--gtfs-only" in sys.argv:
        return

    print(f"{city['metropole']} 경계 (OSM)…")
    boundaries = city["boundaries"]
    if boundaries.get("ids"):
        # Some districts are not found inside their city's area (Daejeon): listed by relation id instead.
        query = f'[out:json][timeout:180];relation(id:{",".join(str(i) for i in boundaries["ids"])});out geom;'
        payload = json.loads(overpass(query))
    else:
        # One area or several (수도권: Seoul, Incheon and Gyeonggi).
        areas = boundaries["area"] if isinstance(boundaries["area"], list) else [boundaries["area"]]
        payload, queries = {"elements": []}, []
        for code in areas:
            query = (
                f'[out:json][timeout:600];area["ISO3166-2"="{code}"]->.a;.a out tags;'
                f'relation["boundary"="administrative"]["admin_level"="{boundaries["adminLevel"]}"](area.a);out geom;'
            )
            # Some Overpass mirrors answer an area query with nothing, and no error: ask again.
            for _ in range(5):
                elements = json.loads(overpass(query))["elements"]
                if any(e["type"] == "relation" for e in elements):
                    break
                print(f"  {code}: 경계가 비어 있음, 다시 요청…")
            else:
                sys.exit(f"{code} 경계를 받지 못했습니다")
            region = re.sub("(특별시|광역시|특별자치도|도)$", "", next(e for e in elements if e["type"] == "area")["tags"]["name"])
            payload["elements"] += [{**e, "region": region} for e in elements if e["type"] == "relation"]
            queries.append(query)
        query = " + ".join(queries)
        # The same district name in two cities (서울 중구, 인천 중구): the later ones get their city's name.
        seen = set()
        for element in payload["elements"]:
            name = element["tags"].get("name")
            if name in seen:
                element["tags"] = {**element["tags"], "name": f"{element['region']} {name}"}
            seen.add(name)
    # The city itself sometimes comes back with its districts (부산광역시 among the 구 of Busan).
    payload["elements"] = [element for element in payload["elements"] if element["tags"].get("name") != city["metropole"]]
    (out / "communes.geojson").write_text(json.dumps(boundaries_geojson(payload), ensure_ascii=False), encoding="utf-8")
    record(out, "communes.geojson", f"Overpass API: {query}")
    if city.get("arrondissements"):
        print("Arrondissements municipaux…")
        url = (f"https://geo.api.gouv.fr/communes?type=arrondissement-municipal&codeParent={city['arrondissements']}"
               "&fields=nom,code&format=geojson&geometry=contour")
        (out / "arrondissements.geojson").write_bytes(download(url))
        record(out, "arrondissements.geojson", url)

    if city.get("railGeometry") == "osm":
        print("노선 궤적 (OSM)…")
        query = f'[out:json][timeout:110];relation["route"~"^({city.get('osmRailRoutes', 'tram|subway|light_rail|funicular')})$"]({bbox(city["osmRailBbox"])});out geom;'
        (out / "osm_rail.json").write_bytes(overpass(query))
        record(out, "osm_rail.json", f"Overpass API: {query}")

    print("물·공원 (OSM)…")
    area, parks = bbox(city["osmBbox"]), bbox(city["parksBbox"])
    query = (
        "[out:json][timeout:180];("
        f'relation["natural"="water"]({area});'
        f'way["natural"="water"]({area});'
        f'relation["leisure"="park"]({parks});'
        f'way["leisure"="park"]({parks});'
        ");out geom;"
    )
    (out / "osm_water_parks.json").write_bytes(overpass(query))
    record(out, "osm_water_parks.json", f"Overpass API: {query}")
    fetch_rivers(city, out)
    fetch_coastline(city, out)
    fetch_context(city, out)


if __name__ == "__main__":
    main()
