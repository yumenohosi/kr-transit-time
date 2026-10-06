#!/usr/bin/env python3
"""Render the home page, one page per city (cities/*.json), the credits page, the 404 page, sitemap.xml and robots.txt.

Usage: python3 build_pages.py   (run build_data.py <city> first: figures come from sources/<city>.json)
"""

from __future__ import annotations

import hashlib
import html
import json
from datetime import date
from pathlib import Path
from string import Template

from cities import load_cities

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
SITE_URL = "https://transit.yumes.net/"
UPSTREAM_URL = "https://github.com/camilleroux/montpellier-temps-transport"
REPO_URL = "https://github.com/yumenohosi/kr-transit-time"
SITE_NAME = "대중교통 시간 지도"
LICENCES = {
    "ktdb": ("국가교통DB 제공 자료", "https://www.ktdb.go.kr/www/index.do"),
    "odbl": ("ODbL", "https://opendatacommons.org/licenses/odbl/1-0/"),
}
ODBL_URL = "https://opendatacommons.org/licenses/odbl/1-0/"
CREDITS_DIR = "credits"
MODE_LABEL_SHORT = {"tram": "트램", "metro": "지하철", "metro+tram": "지하철·트램"}
MODE_NAMES = {"metro": "지하철", "tram": "트램", "funicular": "푸니쿨라", "cable": "케이블카", "busway": "BRT"}
WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]

esc = html.escape


def text_color(background: str) -> str:
    """Black or white text, whichever reads best on a line colour (yellow lines need black)."""
    value = int(background.lstrip("#")[:6] or "888888", 16)
    luminance = 0.299 * (value >> 16) + 0.587 * ((value >> 8) & 255) + 0.114 * (value & 255)
    return "#111" if luminance > 150 else "#fff"


def line_badge(color: str, name: str) -> str:
    return f'<span class="line-badge" style="background:{color};color:{text_color(color)}">{esc(name)}</span>'


def num(value: float) -> str:
    return f"{value:g}"


def short_hash(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()[:8] if path.exists() else "0"


def korean_date(value: str, weekday: bool = False) -> str:
    day = date.fromisoformat(value[:10])
    text = f"{day.year}년 {day.month}월 {day.day}일"
    return f"{text} {WEEKDAYS[day.weekday()]}요일" if weekday else text


def load_built_cities() -> list[dict]:
    """Cities whose data has been built, with their figures (sources/<city>.json)."""
    cities = []
    for city in load_cities():
        sources = ROOT / "sources" / f"{city['slug']}.json"
        if not sources.exists() or not (SITE / "data" / f"{city['slug']}.json").exists():
            print(f"  {city['slug']} 건너뜀: 먼저 build_data.py {city['slug']} 실행")
            continue
        city["sources"] = json.loads(sources.read_text(encoding="utf-8"))
        city["stats"] = city["sources"]["stats"]
        cities.append(city)
    return cities


def json_ld(data: dict) -> str:
    body = json.dumps(data, ensure_ascii=False, indent=2).replace("</", "<\\/")
    return '    <script type="application/ld+json">\n    ' + body.replace("\n", "\n    ") + "\n    </script>"


def head(*, title: str, description: str, url: str, base: str, image: str, image_alt: str, published: str, graph: list) -> str:
    """<head> content shared by every page: SEO, social previews, structured data."""
    title_text = esc(title.split(" · ")[0])
    return "\n".join(
        [
            '    <meta charset="utf-8" />',
            '    <meta name="viewport" content="width=device-width, initial-scale=1" />',
            f"    <title>{esc(title)}</title>",
            f'    <meta name="description" content="{esc(description)}" />',
            f'    <link rel="canonical" href="{url}" />',
            '    <meta name="theme-color" content="#3aa70b" />',
            f'    <link rel="icon" href="{base}favicon.svg" type="image/svg+xml" />',
            f'    <link rel="icon" href="{base}favicon-32.png" type="image/png" sizes="32x32" />',
            f'    <link rel="apple-touch-icon" href="{base}apple-touch-icon.png" />',
            '    <meta property="og:type" content="website" />',
            '    <meta property="og:locale" content="ko_KR" />',
            f'    <meta property="og:site_name" content="{SITE_NAME}" />',
            f'    <meta property="og:title" content="{title_text}" />',
            f'    <meta property="og:description" content="{esc(description)}" />',
            f'    <meta property="og:url" content="{url}" />',
            f'    <meta property="og:image" content="{image}" />',
            '    <meta property="og:image:width" content="1200" />',
            '    <meta property="og:image:height" content="630" />',
            f'    <meta property="og:image:alt" content="{esc(image_alt)}" />',
            f'    <meta property="article:published_time" content="{published}T08:00:00+09:00" />',
            '    <meta name="twitter:card" content="summary_large_image" />',
            f'    <meta name="twitter:title" content="{title_text}" />',
            f'    <meta name="twitter:description" content="{esc(description)}" />',
            f'    <meta name="twitter:image" content="{image}" />',
            json_ld({"@context": "https://schema.org", "@graph": graph}),
            '    <link rel="preconnect" href="https://fonts.bunny.net" />',
            '    <link rel="stylesheet" href="https://fonts.bunny.net/css?family=inter:400,500,600,700,800" />',
        ]
    )


def header(base: str) -> str:
    repo_link = f'\n          <a class="topbar-link" href="{REPO_URL}" rel="noopener">GitHub</a>' if REPO_URL else ""
    return f"""    <header class="topbar">
      <nav class="topbar-inner" aria-label="주 메뉴">
        <a class="brand" href="{base}"><img src="{base}favicon.svg" width="22" height="22" alt="" /> {SITE_NAME}</a>
        <div class="topbar-links">
          <a class="topbar-link" href="{base}{CREDITS_DIR}/">출처와 라이선스</a>{repo_link}
        </div>
      </nav>
    </header>"""


def footer(cities: list[dict], base: str, data_credit: str) -> str:
    links = " · ".join(f'<a href="{base}{city["path"]}">{esc(city["name"])}</a>' for city in cities)
    return f"""    <footer class="site-footer">
      <div class="footer-inner">
        <p class="footer-links">도시&nbsp;: {links}</p>
        <p class="footer-links"><a href="{base}{CREDITS_DIR}/">출처와 라이선스</a></p>
        <p class="footer-credits">
          Camille Roux의 <a href="{UPSTREAM_URL}" rel="noopener">À portée de tram</a>(MIT 라이선스)을 포크해 만들었습니다.
          원래 아이디어는 Anthony Castrio의 <a href="https://castrio.me/nyc/">NYC Transit Time Cartogram</a>과 Jules Grandin의
          파리판(<a href="https://julesgrandin.github.io/paris-temps-transport/">C'est encore loin&nbsp;?</a>)입니다.
          {data_credit} 지도·구 경계·노선 궤적 © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap 기여자</a>.
          계산된 데이터는 <a href="{ODBL_URL}">ODbL</a>, 코드는 MIT 라이선스입니다.
        </p>
      </div>
    </footer>"""


def faq_block(entries: list[tuple]) -> str:
    """Entries are (question, answer) or (question, answer, answer_html) when the visible answer carries links."""
    return "\n".join(
        f'        <details class="faq"><summary>{esc(entry[0])}</summary><p>{entry[2] if len(entry) > 2 else esc(entry[1])}</p></details>'
        for entry in entries
    )


def faq_schema(entries: list[tuple]) -> dict:
    return {
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": entry[0], "acceptedAnswer": {"@type": "Answer", "text": entry[1]}} for entry in entries
        ],
    }


def credits_entry(question: str) -> tuple:
    """« Where does this come from? »: the original authors, and the project this site is forked from."""
    text = (
        "아이디어는 Anthony Castrio의 NYC Transit Time Cartogram과, 이를 파리에 옮긴 Jules Grandin의 « C'est encore loin ? »에서 "
        "왔습니다. 코드는 Camille Roux가 프랑스 도시용으로 만든 « À portée de tram »(MIT 라이선스)을 포크했습니다."
    )
    html_text = (
        '아이디어는 Anthony Castrio의 <a href="https://castrio.me/nyc/">NYC Transit Time Cartogram</a>과, 이를 파리에 옮긴 '
        'Jules Grandin의 <a href="https://julesgrandin.github.io/paris-temps-transport/">C\'est encore loin&nbsp;?</a>에서 '
        f'왔습니다. 코드는 Camille Roux가 프랑스 도시용으로 만든 <a href="{UPSTREAM_URL}">À portée de tram</a>(MIT 라이선스)을 '
        "포크했습니다."
    )
    return (question, text, html_text)


def city_card(city: dict, base: str, heading: str = "h3") -> str:
    stats = city["stats"]
    return f"""          <a class="city-card" href="{base}{city['path']}">
            <img src="{base}og/thumb-{city['slug']}.jpg" width="600" height="315" alt="" loading="lazy" />
            <span class="city-card-body">
              <{heading}>{esc(city['title'])}</{heading}>
              <span>{esc(city['railStations'])}의 {stats['within30']}%가 중심({esc(stats['center'])})에서 30분 안 · {esc(city['network'])}</span>
            </span>
          </a>"""


def city_faq(city: dict) -> list[tuple]:
    stats, sources = city["stats"], city["sources"]
    name, rail = city["name"], city["railNoun"]
    lines = stats["lines"]
    headways = ", ".join(f"{line['name']} {num(line['headway'])}분" for line in lines)
    fastest = min(lines, key=lambda line: line["headway"])
    period = sources["gtfs"].get("servicePeriod") or [None, None]
    fetched = sources["gtfs"].get("fetchedAt")
    timetable = f"{city['network']} 계획 시간표(GTFS, {LICENCES[city['gtfsLicence']][0]})를 사용합니다."
    if fetched:
        timetable += f" {korean_date(fetched)}에 받은 자료입니다."
    if period[1]:
        timetable += f" 시간표 유효 기간은 {korean_date(period[1])}까지입니다."
    timetable += f" 소요시간은 {korean_date(sources['referenceDate'], weekday=True)} 7시~20시 기준입니다."
    entries = [
        (
            f"{name} {rail}, 끝에서 끝까지 얼마나 걸리나요?",
            f"중심({stats['center']})에서 출발하면 {city['railStations']}의 {stats['within15']}%가 15분 안에, "
            f"{stats['within30']}%가 30분 안에 닿습니다(도보·대기 포함). 가장 먼 역인 {stats['farthestStation']}까지는 "
            f"약 {stats['farthestMinutes']}분입니다.",
        ),
        (
            f"{name} {rail} 노선은 얼마나 자주 다니나요?",
            f"평일 낮 평균 배차 간격은 {headways}입니다. 가장 자주 다니는 노선은 {fastest['name']}으로, 약 "
            f"{num(fastest['headway'])}분마다 옵니다.",
        ),
        ("어떤 시간표를 쓰나요?", timetable),
    ]
    if stats["busLines"]:
        entries.append(
            (
                f"{name}에서 버스도 계산되나요?",
                f"네, 기본으로 버스까지 함께 계산합니다. 지도 아래 ‘{city['busLabel']}’ 항목을 끄면 {rail}만으로 계산합니다. "
                "드물게 오는 버스의 대기시간은 최대 15분으로 잡습니다.",
            )
        )
    entries += [
        (
            "소요시간은 어떻게 계산하나요?",
            "시속 4.5km로 정류장까지 걷고, 배차 간격의 절반만큼 기다리고, 시간표상 역 사이 소요시간을 더합니다. 환승할 때는 "
            "도보 1.5분을 더합니다"
            + (". 지하철은 승강장까지 오가는 1분도 더합니다" if any(line["mode"] == "metro" for line in lines) else "")
            + ". 실시간 정보나 운행 장애는 반영하지 않는, ‘시간표상’ 도시입니다.",
        ),
        credits_entry(f"이 {name} 지도는 어디서 왔나요?"),
    ]
    return entries


def render_city(template: Template, cities: list[dict], city: dict) -> str:
    url = SITE_URL + city["path"]
    base = "../"
    stats = city["stats"]
    rail_noun = city["railNoun"]
    description = (
        f"{city['name']} 대중교통 소요시간 지도: 출발지를 고르면 도시 곳곳까지 걸리는 시간이 색으로 표시됩니다"
        f"({city['network']})."
    )
    faq = city_faq(city)
    graph = [
        {
            "@type": "WebApplication",
            "name": city["title"],
            "url": url,
            "description": description,
            "inLanguage": "ko",
            "applicationCategory": "TravelApplication",
            "operatingSystem": "Web",
            "isAccessibleForFree": True,
            "image": f"{SITE_URL}og/{city['slug']}.jpg",
            "spatialCoverage": {"@type": "Place", "name": city["metropole"]},
            "isBasedOn": [UPSTREAM_URL, "https://castrio.me/nyc/", "https://julesgrandin.github.io/paris-temps-transport/"],
            "datePublished": city["published"],
            "dateModified": city["sources"]["builtAt"][:10],
        },
        {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": SITE_NAME, "item": SITE_URL},
                {"@type": "ListItem", "position": 2, "name": city["name"], "item": url},
            ],
        },
        faq_schema(faq),
    ]
    fastest = min(stats["lines"], key=lambda line: line["headway"])
    tiles = [
        (f"{stats['within30']}%", f"{city['railStations']} 중 중심({stats['center']})에서 30분 안에 닿는 비율"),
        (str(stats["railStations"]), city["railStations"]),
        (f"{num(fastest['headway'])}분", f"가장 자주 다니는 {fastest['name']}의 배차 간격"),
        (f"{stats['farthestMinutes']}분", f"중심에서 가장 먼 역 {stats['farthestStation']}까지"),
    ]
    stat_tiles = "\n".join(f'          <div class="stat"><strong>{esc(value)}</strong><span>{esc(label)}</span></div>' for value, label in tiles)
    line_rows = "\n".join(
        f'            <tr><td>{line_badge(line["color"], line["name"])} '
        f'{esc(MODE_NAMES.get(line["mode"], ""))}</td><td>{line["stations"]}</td><td>약 {num(line["headway"])}분</td></tr>'
        for line in stats["lines"]
    )
    # City switcher: the city name in the title opens a panel of real links (site/app.js), crawlable as well.
    items = "\n".join(
        f'            <a class="city-item{" current" if other["slug"] == city["slug"] else ""}" href="{base}{other["path"]}"'
        f'{" aria-current=\"page\"" if other["slug"] == city["slug"] else ""} data-name="{esc(other["name"].lower())}">'
        f'<img src="{base}og/thumb-{other["slug"]}.jpg" width="120" height="63" alt="" loading="lazy" />'
        f'<span><strong>{esc(other["name"])}</strong><small>{esc(MODE_LABEL_SHORT[other["kind"]])} · {esc(other["network"])}</small></span></a>'
        for other in cities
    )
    rest = esc(city["title"][len(city["name"]):])
    headline = (
        f'<button id="cityTrigger" type="button" class="city-trigger" aria-haspopup="dialog" aria-expanded="false" '
        f'title="도시 바꾸기">{esc(city["name"])}<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 6l5 5 5-5"/></svg></button>'
        + "&nbsp;".join(rest.rsplit(" ", 1))
    )
    config = {
        "slug": city["slug"],
        "name": city["name"],
        "dataVersion": short_hash(SITE / "data" / f"{city['slug']}.json"),
        "defaultFrom": city["defaultFrom"],
        "railNoun": rail_noun,
        "railStations": city["railStations"],
        "busNoun": city["busNoun"],
        "geocoderUrl": city.get("geocoderUrl"),
        "maxMinutes": city.get("maxMinutes"),
    }
    data_credit = f'시간표&nbsp;: <a href="{esc(city["gtfsDataset"])}">GTFS {esc(city["network"])}</a> ({esc(city["metropole"])}).'
    hidden = "" if stats["busLines"] else " hidden"
    others = [other for other in cities if other["slug"] != city["slug"]]
    other_cities = (
        f"""
      <section class="section" aria-labelledby="cities-title">
        <h2 id="cities-title">다른 도시</h2>
        <div class="city-grid">
{chr(10).join(city_card(other, base) for other in others)}
        </div>
      </section>"""
        if others
        else ""
    )
    values = {
        "head": head(
            title=f"{city['title']} · {city['titleSuffix']}",
            description=description,
            url=url,
            base=base,
            image=f"{SITE_URL}og/{city['slug']}.jpg?v={short_hash(SITE / 'og' / (city['slug'] + '.jpg'))}",
            image_alt=city["ogAlt"],
            published=city["published"],
            graph=graph,
        ),
        "header": header(base),
        "footer": footer(cities, base, data_credit),
        "base": base,
        "site_name": SITE_NAME,
        "city_config": json.dumps(config, ensure_ascii=False).replace("</", "<\\/"),
        "city_items": items,
        "headline": headline,
        "name": esc(city["name"]),
        "area": esc(city["area"]),
        "rail_noun": esc(rail_noun),
        "rail_label": esc(city["railLabel"]),
        "bus_toggle": f'            <label class="pill-toggle"{hidden}><input id="busToggle" type="checkbox" /> {esc(city["busLabel"])}</label>',
        "search_placeholder": esc(
            f"주소나 역·정류장 검색… (예: {city['searchExample']})" if city.get("geocoderUrl") else f"역·정류장 검색… (예: {city['searchExample']})"
        ),
        "search_step": "주소나 역·정류장을 검색하거나 초록 점을 끌어 옮기세요." if city.get("geocoderUrl") else "역·정류장을 검색하거나 초록 점을 끌어 옮기세요.",
        "network": esc(city["network"]),
        "stat_tiles": stat_tiles,
        "line_rows": line_rows,
        "faq_html": faq_block(faq),
        "other_cities": other_cities,
        "styles_version": short_hash(SITE / "styles.css"),
        "app_version": short_hash(SITE / "app.js"),
    }
    return template.substitute(values)


def render_home(template: Template, cities: list[dict]) -> str:
    names = ", ".join(city["name"] for city in cities)
    networks = ", ".join(f"{city['network']}({city['name']})" for city in cities)
    description = f"{names}의 대중교통 소요시간 지도: 출발지를 고르면 도시가 소요시간에 따라 색칠됩니다."
    faq = [
        (
            "소요시간은 어디서 오나요?",
            f"각 노선망의 공식 계획 시간표({networks})를 GTFS 형식으로 받아 씁니다. 평일 낮 7시~20시 기준입니다.",
        ),
        (
            "표시되는 시간은 믿을 만한가요?",
            "‘시간표상’ 평균입니다. 정류장까지 걷는 시간, 배차 간격 절반의 대기, 시간표상 역 사이 소요시간, 환승을 더합니다. "
            "실시간 정보나 운행 장애는 반영하지 않습니다.",
        ),
        (
            "버스도 계산되나요?",
            "네, 기본으로 버스까지 함께 계산합니다. 지도마다 버스를 끄면 지하철·경전철 같은 도시철도만으로 계산해 노선망의 "
            "뼈대를 볼 수 있습니다.",
        ),
        (
            "우리 도시는 왜 없나요?",
            "도시철도 노선이 있고, 그 시간표가 GTFS로 공개돼 있어야 합니다.",
        ),
        credits_entry("이 사이트는 어디서 왔나요?"),
    ]
    graph = [
        {
            "@type": "WebSite",
            "@id": SITE_URL + "#site",
            "name": SITE_NAME,
            "url": SITE_URL,
            "description": description,
            "inLanguage": "ko",
        },
        {
            "@type": "ItemList",
            "name": "도시별 소요시간 지도",
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "name": city["title"], "url": SITE_URL + city["path"]}
                for i, city in enumerate(cities)
            ],
        },
        faq_schema(faq),
    ]
    published = min(city["published"] for city in cities)
    values = {
        "head": head(
            title=f"{SITE_NAME} · 도시별 대중교통 소요시간",
            description=description,
            url=SITE_URL,
            base="./",
            image=SITE_URL + "og/home.jpg?v=" + short_hash(SITE / "og" / "home.jpg"),
            image_alt=f"{names}의 대중교통 소요시간 지도.",
            published=published,
            graph=graph,
        ),
        "header": header("./"),
        "footer": footer(cities, "./", f'시간표&nbsp;: 도시별 노선망의 GTFS(<a href="./{CREDITS_DIR}/">출처</a>).'),
        "site_name": SITE_NAME,
        "city_count": str(len(cities)),
        "city_cards": "\n".join(city_card(city, "./", "h2") for city in cities),
        "city_links": "\n".join(
            f'          <a class="chip" href="./{city["path"]}">{esc(city["name"])}</a>'
            for city in cities
        ),
        "faq_html": faq_block(faq),
        "styles_version": short_hash(SITE / "styles.css"),
    }
    return template.substitute(values)


def render_credits(cities: list[dict]) -> str:
    """Privacy, licences, and the timetable used for every city."""
    rows = "\n".join(
        f'          <tr><td>{esc(city["name"])}</td><td><a href="{esc(city["gtfsDataset"])}">GTFS {esc(city["network"])}</a></td>'
        f'<td><a href="{LICENCES[city["gtfsLicence"]][1]}">{LICENCES[city["gtfsLicence"]][0]}</a></td>'
        f'<td>{korean_date(city["sources"]["gtfs"]["fetchedAt"]) if city["sources"]["gtfs"].get("fetchedAt") else "—"}</td></tr>'
        for city in cities
    )
    geocoding = (
        " 주소 검색어는 검색할 때 외부 지오코딩 서비스로 전송됩니다." if any(city.get("geocoderUrl") for city in cities) else ""
    )
    return f"""<!doctype html>
<html lang="ko">
  <head>
{head(title=f"출처와 라이선스 · {SITE_NAME}", description=f"{SITE_NAME}이 쓰는 데이터의 출처와 라이선스.", url=SITE_URL + CREDITS_DIR + "/", base="../", image=SITE_URL + "og/home.jpg", image_alt=SITE_NAME, published=date.today().isoformat(), graph=[])}
    <link rel="stylesheet" href="../styles.css?v={short_hash(SITE / 'styles.css')}" />
  </head>
  <body>
{header('../')}
    <main class="page">
      <nav class="breadcrumb" aria-label="현재 위치">
        <a href="../">{SITE_NAME}</a> <span aria-hidden="true">›</span> <span aria-current="page">출처와 라이선스</span>
      </nav>
      <section class="section">
        <h1 class="page-title">출처와 라이선스</h1>
        <h2>개인정보</h2>
        <p>소요시간은 브라우저 안에서 계산하며, 위치나 검색어를 저장하지 않습니다.{geocoding}</p>
        <h2>라이선스</h2>
        <p>코드는 MIT 라이선스입니다. Camille Roux의 <a href="{UPSTREAM_URL}">À portée de tram</a>을 포크했습니다.
        계산된 데이터(<code>data/*.json</code>)는 파생 데이터베이스로, <a href="{ODBL_URL}">ODbL</a>로 공개합니다.
        지도·구 경계·노선 궤적&nbsp;: © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap 기여자</a> (ODbL).</p>
        <table class="lines-table">
          <caption>도시별 시간표 출처</caption>
          <thead><tr><th scope="col">도시</th><th scope="col">출처</th><th scope="col">라이선스</th><th scope="col">받은 날</th></tr></thead>
          <tbody>
{rows}
          </tbody>
        </table>
      </section>
    </main>
{footer(cities, "../", "")}
  </body>
</html>
"""


def write_sources_readme(cities: list[dict]) -> None:
    lines = [
        "# 데이터 출처",
        "",
        "`build_pages.py`가 `sources/<도시>.json`에서 생성합니다.",
        "",
        "| 도시 | 노선망 | 라이선스 | GTFS 받은 날 | GTFS 유효 기간 | 기준일 |",
        "|---|---|---|---|---|---|",
    ]
    for city in cities:
        gtfs = city["sources"]["gtfs"]
        period = gtfs.get("servicePeriod") or ["?", "?"]
        how = " (수동)" if gtfs.get("how") == "manual" else ""
        lines.append(
            f"| [{city['name']}]({city['slug']}.json) | {city['network']} | {LICENCES[city['gtfsLicence']][0]} | "
            f"{gtfs.get('fetchedAt', '?')[:10]}{how} | {period[0]} → {period[1]} | {city['sources']['referenceDate']} |"
        )
    (ROOT / "sources" / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_404(cities: list[dict]) -> str:
    links = "\n".join(f'          <a class="chip" href="/{city["path"]}">{esc(city["name"])}</a>' for city in cities)
    return f"""<!doctype html>
<html lang="ko">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>페이지 없음 · {SITE_NAME}</title>
    <meta name="robots" content="noindex" />
    <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
    <link rel="stylesheet" href="https://fonts.bunny.net/css?family=inter:400,500,600,700,800" />
    <link rel="stylesheet" href="/styles.css?v={short_hash(SITE / 'styles.css')}" />
  </head>
  <body>
{header('/')}
    <main class="page">
      <section class="hero">
        <h1>종점입니다!</h1>
        <p class="lede">없는 페이지입니다. 도시를 골라 다시 출발하세요.</p>
        <nav class="city-switch" aria-label="도시">
{links}
        </nav>
      </section>
    </main>
  </body>
</html>
"""


def main() -> None:
    cities = load_built_cities()
    city_template = Template((ROOT / "templates" / "city.html").read_text(encoding="utf-8"))
    for city in cities:
        page = SITE / city["path"] / "index.html"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(render_city(city_template, cities, city), encoding="utf-8")
        print(f"Wrote {page.relative_to(ROOT)}")

    home_template = Template((ROOT / "templates" / "home.html").read_text(encoding="utf-8"))
    (SITE / "index.html").write_text(render_home(home_template, cities), encoding="utf-8")
    (SITE / "404.html").write_text(render_404(cities), encoding="utf-8")
    (SITE / CREDITS_DIR).mkdir(exist_ok=True)
    (SITE / CREDITS_DIR / "index.html").write_text(render_credits(cities), encoding="utf-8")
    write_sources_readme(cities)
    print("Wrote site/index.html, site/404.html")

    today = date.today().isoformat()
    urls = [f"  <url><loc>{SITE_URL}</loc><lastmod>{today}</lastmod></url>"]
    urls += [
        f"  <url><loc>{SITE_URL}{city['path']}</loc><lastmod>{city['sources']['builtAt'][:10]}</lastmod></url>" for city in cities
    ]
    (SITE / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n",
        encoding="utf-8",
    )
    (SITE / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}sitemap.xml\n", encoding="utf-8")
    print("Wrote site/sitemap.xml, site/robots.txt")


if __name__ == "__main__":
    main()
