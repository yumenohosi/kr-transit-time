#!/usr/bin/env python3
"""Turn the KTDB nationwide GTFS pilot (국가교통DB 대중교통 GTFS) into a standard GTFS of the urban rail lines around
a city: data/<city>/gtfs.zip, read by build_data.py.

Usage: python3 tools/ktdb_gtfs.py <city> <KTDB zip> [--bus]

The pilot is not standard GTFS: its files sit in a sub-folder, route_type 1 means urban rail (0 is bus), each line is
split into one route per direction and branch, trips have no direction_id and stop names carry the line
(« 시청(1호선) »). Lines are merged by name, directions are read from the route_id suffix (D/I: 0, U/O: 1), and a line
is kept when one of its stops lies in the city's OSM area.

--bus adds the city buses (route_type 0), cut to their stops inside the city boundaries (data/<city>/communes.geojson,
from fetch_data.py): a suburban bus keeps its stretch through the city.
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from build_data import point_in_ring  # noqa: E402
from cities import load_city  # noqa: E402

# Line colours by region and line code in the pilot route_id (RR_ACC1_S-<region>-<code>-…; region 1 Seoul area,
# 2 Busan, 3 Daegu, 4 Gwangju, 5 Daejeon), from ko.wikipedia « 틀:한국 철도 노선색 » (the Seoul area ones as listed by
# seoul-route, MIT, github.com/SIDED00R/seoul-route, gtfs/internal/build/colors.go).
COLORS = {
    "1-01": "0052A4", "1-02": "00A84D", "1-03": "EF7C1C", "1-04": "00A5DE", "1-05": "996CAC",
    "1-06": "CD7C2F", "1-07": "747F00", "1-08": "E6186C", "1-09": "BDB092",
    "1-KJ": "77C4A3", "1-SD": "F5A200", "1-GC": "0C8E72", "1-KK": "003DA5", "1-AP": "0090D2", "1-SB": "D4003B",
    "1-UI": "FDA600", "1-SL": "6789CA", "1-WS": "B0CE18", "1-KP": "A17800", "1-I1": "7CA8D5", "1-I2": "ED8B00",
    "2-01": "F06A00", "2-02": "81BF48", "2-03": "BB8C00", "2-04": "217DCB", "2-BG": "8652A1", "2-DH": "003DA5",
    "3-01": "D93F5C", "3-02": "00AA80", "3-03": "FFB100", "3-DG": "003DA5",
    "4-01": "009088",
    "5-01": "007448",
}
COLORS_BY_NAME = {"서해선": "81A914", "GTX-A": "9A6292"}


def line_name(route: dict, prefix: str) -> str:
    """« 서울2호선 » → « 2호선 » for the city's own lines (`linePrefix`), as signs say; other lines keep their name."""
    return re.sub(rf"^{prefix}(\d)호선$", r"\1호선", route["route_short_name"]) if prefix else route["route_short_name"]


def boundary_test(path: Path):
    """Point-in-boundaries test on (lon, lat), with a bounding box per polygon."""
    polygons = []
    for feature in json.loads(path.read_text(encoding="utf-8"))["features"]:
        for polygon in feature["geometry"]["coordinates"]:
            ring = [tuple(point) for point in polygon[0]]
            xs, ys = [x for x, _ in ring], [y for _, y in ring]
            polygons.append(((min(xs), min(ys), max(xs), max(ys)), ring, [[tuple(p) for p in hole] for hole in polygon[1:]]))

    def inside(lon: float, lat: float) -> bool:
        return any(
            x0 <= lon <= x1 and y0 <= lat <= y1 and point_in_ring((lon, lat), ring) and not any(point_in_ring((lon, lat), h) for h in holes)
            for (x0, y0, x1, y1), ring, holes in polygons
        )

    return inside


def write_table(archive: zipfile.ZipFile, name: str, header: list, rows) -> None:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    archive.writestr(name, buffer.getvalue())


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    city = load_city(sys.argv[1])
    south, west, north, east = city["osmBbox"]
    with_bus = "--bus" in sys.argv
    prefix = city.get("linePrefix", "")
    with zipfile.ZipFile(sys.argv[2]) as archive:
        folder = next(name for name in archive.namelist() if name.endswith("routes.txt"))[: -len("routes.txt")]

        def table(name: str) -> list[dict]:
            with archive.open(folder + name) as handle:
                return list(csv.DictReader(io.TextIOWrapper(handle, encoding="utf-8-sig")))

        all_routes = {row["route_id"]: row for row in table("routes.txt")}
        routes = {route_id: row for route_id, row in all_routes.items() if row["route_type"] == "1"}
        buses = {route_id: row for route_id, row in all_routes.items() if with_bus and row["route_type"] == "0"}
        stops = {row["stop_id"]: row for row in table("stops.txt")}
        trips = {row["trip_id"]: row for row in table("trips.txt") if row["route_id"] in routes}
        bus_trips = {row["trip_id"]: row for row in table("trips.txt") if row["route_id"] in buses}
        in_city = boundary_test(ROOT / "data" / city["slug"] / "communes.geojson") if with_bus else None
        city_stops = {
            stop_id for stop_id, stop in stops.items() if with_bus and stop_id.startswith("BS_") and in_city(float(stop["stop_lon"]), float(stop["stop_lat"]))
        }
        calendar = table("calendar.txt")
        agency = table("agency.txt")
        print(f"도시철도 {len(routes)}개 노선, {len(trips)}회 운행: stop_times 읽는 중…")
        with archive.open(folder + "stop_times.txt") as handle:
            reader = csv.reader(io.TextIOWrapper(handle, encoding="utf-8-sig"))
            stop_times_header = next(reader)
            trip_col, stop_col = stop_times_header.index("trip_id"), stop_times_header.index("stop_id")
            stop_times, bus_stop_times = [], []
            for row in reader:
                if row[trip_col] in trips:
                    stop_times.append(row)
                elif row[trip_col] in bus_trips and row[stop_col] in city_stops:
                    bus_stop_times.append(row)

    def inside(stop_id: str) -> bool:
        stop = stops[stop_id]
        return south <= float(stop["stop_lat"]) <= north and west <= float(stop["stop_lon"]) <= east

    lines = {line_name(routes[trips[row[trip_col]]["route_id"]], prefix) for row in stop_times if inside(row[stop_col])}
    kept_trips = {trip_id for trip_id, trip in trips.items() if line_name(routes[trip["route_id"]], prefix) in lines}
    stop_times = [row for row in stop_times if row[trip_col] in kept_trips]
    # A bus trip needs two stops in the city to ride between them.
    bus_counts = {}
    for row in bus_stop_times:
        bus_counts[row[trip_col]] = bus_counts.get(row[trip_col], 0) + 1
    kept_bus_trips = {trip_id for trip_id, count in bus_counts.items() if count >= 2}
    stop_times += [row for row in bus_stop_times if row[trip_col] in kept_bus_trips]
    bus_lines = {bus_trips[trip_id]["route_id"] for trip_id in kept_bus_trips}
    used_stops = {row[stop_col] for row in stop_times}

    colors = {}
    for route in routes.values():
        name = line_name(route, prefix)
        if name in lines:
            parts = route["route_id"].split("-")
            code = f"{parts[1]}-{parts[2]}" if len(parts) >= 4 else ""
            colors.setdefault(name, COLORS.get(code) or COLORS_BY_NAME.get(name, "888888"))

    out = ROOT / "data" / city["slug"] / "gtfs.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        write_table(archive, "agency.txt", list(agency[0]), [list(row.values()) for row in agency])
        write_table(
            archive, "routes.txt", ["route_id", "agency_id", "route_short_name", "route_type", "route_color"],
            [[name, agency[0]["agency_id"], name, "1", colors[name]] for name in sorted(lines)]
            + [[route_id, agency[0]["agency_id"], buses[route_id]["route_short_name"], "3", "888888"] for route_id in sorted(bus_lines)],
        )
        write_table(
            archive, "trips.txt", ["route_id", "service_id", "trip_id", "direction_id"],
            [
                [line_name(routes[trip["route_id"]], prefix), trip["service_id"], trip_id, "1" if trip["route_id"][-1] in "UO" else "0"]
                for trip_id, trip in trips.items()
                if trip_id in kept_trips
            ]
            + [
                [trip["route_id"], trip["service_id"], trip_id, "1" if trip["route_id"][-1] in "UO" else "0"]
                for trip_id, trip in bus_trips.items()
                if trip_id in kept_bus_trips
            ],
        )
        write_table(archive, "stop_times.txt", stop_times_header, stop_times)
        write_table(
            archive, "stops.txt", ["stop_id", "stop_name", "stop_lat", "stop_lon"],
            [
                [
                    stop_id,
                    re.sub(r"\(.*\)$", "", stops[stop_id]["stop_name"]) if stop_id.startswith("RS_") else stops[stop_id]["stop_name"],
                    stops[stop_id]["stop_lat"],
                    stops[stop_id]["stop_lon"],
                ]
                for stop_id in sorted(used_stops)
            ],
        )
        write_table(archive, "calendar.txt", list(calendar[0]), [list(row.values()) for row in calendar])
    print(
        f"Wrote {out.relative_to(ROOT)}: 도시철도 {len(lines)}개 노선 {len(kept_trips)}회, 버스 {len(bus_lines)}개 노선 "
        f"{len(kept_bus_trips)}회, {len(used_stops)}개 정류장"
    )
    print("  " + ", ".join(sorted(lines)))


if __name__ == "__main__":
    main()
