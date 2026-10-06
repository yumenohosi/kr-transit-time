# 대중교통 시간 지도

지하철 소요시간으로 다시 그린 도시 지도. 출발지를 고르면 도시 곳곳까지 걸리는 시간이 색과 15·30분 등시선으로 표시된다.

Camille Roux의 [À portée de tram](https://github.com/camilleroux/montpellier-temps-transport)(MIT)을 포크해 서울용으로 바꿨다.
원래 아이디어는 Anthony Castrio의 [NYC Transit Time Cartogram](https://castrio.me/nyc/)과 Jules Grandin의
[파리판](https://github.com/JulesGrandin/paris-temps-transport).

## 실행

```bash
python3 fetch_data.py seoul --skip-gtfs   # OSM: 구 경계, 물·공원, 한강·다리
python3 build_data.py seoul               # data/seoul/gtfs.zip 필요
python3 build_pages.py
python3 -m http.server 8000 --directory site
```

`python3 build.py seoul --fetch`로 한 번에 돌릴 수 있다. 미리보기 이미지(`tools/render_og.py`)에는 Chrome과 ImageMagick이 필요하고, 없으면 `--no-og`.

## 서울 GTFS

공개 GTFS 주소가 없어 국가교통DB GTFS를 신청해 받는다(ktdb.go.kr › 정보공개 › 자료신청 › 교통분석자료 신청 ›
교통망 GIS DB › 대중교통). 표준 GTFS가 아니어서(하위 폴더, 도시철도 `route_type` 1·버스 0, 노선이 방향·분기별로 나뉨,
`direction_id`·`shapes.txt` 없음) 변환한다:

```bash
python3 tools/ktdb_gtfs.py seoul "대중교통GTFS(2025년 기준).zip"   # → data/seoul/gtfs.zip
```

도시철도 중 `osmBbox` 안에 역이 하나라도 있는 노선만 남기고, 노선 궤적은 OSM에서 그린다(`railGeometry: "osm"`, `osmRefAliases`).
버스는 넣지 않았다.

## 도시 설정 (`cities/<도시>.json`)

필수: `slug`, `order`, `name`, `kind`(`tram`·`metro`·`metro+tram`), `network`, `metropole`, `boundaries`
(`{"area": ISO3166-2 코드, "adminLevel": OSM 행정 레벨}`), `gtfsUrl`, `gtfsDataset`, `gtfsLicence`(`build_pages.py`의 `LICENCES` 키),
`defaultFrom`, `searchExample`, `published`. 제목·문구 기본값은 `cities.py`.

선택: `rivers`(다리로만 건너는 강), `geocoderUrl`(주소 검색, 없으면 역 검색만), `excludeRouteTypes`, `excludeRouteNames`,
`agencies`, `modeAccess`, `railGeometry: "osm"`·`osmRefAliases`·`osmRailRoutes`(GTFS에 궤적이 없을 때), `view: "land"`(지도 범위를 땅에 맞춤), `parksBbox`.

## 모델

평일(화·목) 7~20시 시간표 기준. 역 사이 시간은 계획 소요시간의 중앙값, 대기는 배차 간격의 절반(1~15분), 환승은 도보 1.5분 + 대기,
450m 안 정류장 사이 도보 환승, 도보는 직선거리 시속 4.5km. 실시간 정보는 반영하지 않는다.

## 라이선스

코드 MIT([LICENSE](LICENSE)). 계산된 데이터(`site/data/*.json`, `sources/*.json`)는 OpenStreetMap 파생이라 ODbL.
