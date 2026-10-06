# 대중교통 시간 지도 (kr-transit-time)

한국 도시를 대중교통 소요시간으로 다시 그린 지도. 출발지를 고르면 도시 곳곳까지 걸리는 시간이 색과 15·30·45·60분 등시선으로
표시된다. 기본은 지하철과 버스를 함께 계산하고, 버스를 끄면 도시철도만으로 계산한다. 수도권(서울·인천·경기), 서울, 부산, 대구, 대전, 광주.

서버 없는 정적 사이트다. 경로 계산(다익스트라)과 지도 그리기(Canvas)는 모두 브라우저에서 하고, 서버는 `site/`의 파일만 내준다.

Camille Roux의 [À portée de tram](https://github.com/camilleroux/montpellier-temps-transport)(MIT, 프랑스 도시판)을
가져와 한국 도시용으로 바꿨다. 원래 아이디어는 Anthony Castrio의 [NYC Transit Time Cartogram](https://castrio.me/nyc/)과
Jules Grandin의 [파리판](https://github.com/JulesGrandin/paris-temps-transport).

## 실행

```bash
python3 -m http.server 8000 --directory site   # http://localhost:8000
```

`site/`에 빌드 결과가 들어 있어 바로 열린다. 다시 만들려면 아래 순서로.

## 빌드

시간표는 국가교통DB GTFS를 쓴다. 공개 주소가 없어 신청해서 받는다(ktdb.go.kr › 정보공개 › 자료신청 › 교통분석자료 신청 ›
교통망 GIS DB › 대중교통). 받은 zip은 저장소에 넣지 않는다.

```bash
python3 fetch_data.py busan --skip-gtfs                                   # OSM: 구 경계, 노선 궤적, 물·공원, 강·다리, 해안선
python3 tools/ktdb_gtfs.py busan "대중교통GTFS(2025년 기준).zip" --bus     # → data/busan/gtfs.zip
python3 fetch_data.py busan --gtfs-only                                   # GTFS 출처 기록
python3 build_data.py busan                                               # → site/data/busan.json, sources/busan.json
python3 build_pages.py                                                    # 모든 도시의 HTML
python3 tools/render_og.py busan && python3 tools/render_og.py home       # 미리보기 이미지 (Chrome, macOS sips)
python3 build_pages.py                                                    # 이미지 버전 반영
```

배포는 `npx wrangler deploy`(Cloudflare Workers 정적 에셋, `wrangler.jsonc`, https://transit.yumes.net).

원본 데이터(`data/`)는 저장소에 넣지 않고, 출처 URL·날짜·SHA-256은 `sources/<도시>.json`에 남는다. Overpass가 504를 내면
`fetch_data.py`가 다른 서버로 재시도한다.

### 국가교통DB GTFS 변환 (`tools/ktdb_gtfs.py`)

표준 GTFS가 아니어서 변환한다. 파일이 하위 폴더에 있고, 도시철도는 `route_type` 1·시내버스는 0이며, 노선이 방향·분기별로
나뉘어 있고, `direction_id`·`shapes.txt`가 없다. 역 이름에는 노선이 붙어 있다(「시청(1호선)」).

- 도시철도: `osmBbox` 안에 역이 하나라도 있는 노선을 이름으로 합친다. 방향은 `route_id` 끝 글자(U·O는 1)로 정한다.
  노선 궤적은 OSM에서 그린다(`railGeometry: "osm"`, `osmRefAliases`).
- `--bus`: 시내버스를 도시 경계(`data/<도시>/communes.geojson`) 안 정류장만 남겨 자른다. 정류장이 둘 이상 남은 운행만 쓴다.
- 노선 색은 `COLORS`(지역-노선 코드)에 있다.

## 도시 설정 (`cities/<도시>.json`)

필수: `slug`, `order`(목록 순서, 인구순), `name`, `kind`(`metro`·`tram`·`metro+tram`), `network`, `metropole`,
`boundaries`, `gtfsUrl`, `gtfsDataset`, `gtfsLicence`(`build_pages.py`의 `LICENCES` 키), `defaultFrom`, `searchExample`,
`published`. 제목·문구 기본값은 `cities.py`.

- `boundaries`: `{"area": ISO3166-2 코드, "adminLevel": "6"}`(시·구·군). 여러 지역은 코드 목록(수도권: `["KR-11", "KR-28", "KR-41"]`,
  두 곳에 같은 이름이 있으면 뒤의 것에 지역명을 붙인다: 「인천 중구」). 영역 검색에 안 걸리는 구가 있으면 `{"ids": [OSM relation id, …]}`(대전).
- `linePrefix`: 노선 이름 앞의 도시명을 뗀다(「부산1호선」 → 「1호선」).
- `coastline: true`: 한국 행정 경계는 바다까지 뻗어 있어, OSM 해안선으로 바다를 잘라낸다(부산, 수도권). 지하철역이 없고 육지와 오가는
  버스도 없는 섬은 정류장과 함께 뺀다(`ktdb_gtfs.py --bus`).
- `gridCell`: 열지도 칸 크기(m, 기본 200, 수도권 400). `maxMinutes`: 색 범위 기본값(분, 기본 45, 수도권 90).
- `communes: "served"`: 정류장이 있고 도시철도가 닿는 구·군만 남긴다(대구).
- `view: "land"`: 지도 범위를 노선 끝이 아니라 땅에 맞춘다(서울 전철은 천안·춘천까지 간다).
- `rivers`: 다리로만 건너는 강(한강, 낙동강…). `osmRailRoutes`: OSM 노선 종류(기본 `tram|subway|light_rail|funicular`).
- 그 밖에 `parksBbox`, `osmBbox`, `geocoderUrl`(주소 검색, 없으면 역·정류장 검색만), `modeAccess`, `excludeRouteTypes`.

## 모델

화·목요일 7~20시 시간표 기준. 역 사이 시간은 계획 소요시간의 중앙값, 대기는 배차 간격의 절반(1~15분), 같은 역 환승은
도보 1.5분 + 대기, 450m 안 정류장 사이는 걸어서 환승, 도보는 직선거리 시속 4.5km, 지하철은 지상에서 승강장까지 1분.
실시간 정보는 반영하지 않는다.

지도는 200m 칸으로 나눈 열지도다. 데이터 크기를 줄이려고 정류장 사이 도보 환승은 저장하지 않고 브라우저에서 만들고
(서울 버스 포함 36.8MB → 9.4MB), JSON은 노선을 번호로, 정류장·칸을 배열로, 좌표를 1m 단위로 줄여 쓴 뒤 브라우저가 펼친다
(`build_data.py`의 `compact`, `site/app.js`의 `expandData`; 서울 9.4MB → 4.0MB, 수도권 17.7MB). Cloudflare는 파일 하나에 25MiB까지 받는다.

## 라이선스

코드는 MIT([LICENSE](LICENSE)). 계산된 데이터(`site/data/*.json`, `sources/*.json`)는 OpenStreetMap 파생이라 ODbL이고,
시간표는 국가교통DB 자료라 그 이용 조건을 따른다.
