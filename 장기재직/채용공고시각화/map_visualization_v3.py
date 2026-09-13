"""
데이터 분석가 / 백엔드 개발자 채용공고 지역별 분포 지도 시각화 v3
-----------------------------------------------------------------
수정사항 반영:
  [내용]
  1. 서울 구 단위 + 경기 주요 시 단위 동시 표현
     - 경기도 GeoJSON은 구 단위 → geopandas dissolve로 시 단위 병합
  2. 직무별 레이어 분리 (전체 공고 / 데이터 분석가 / 백엔드 개발자)
  3. 툴팁에 공고수 + 지역별 평균 품질점수 + 위험신호 비율 포함

  [시각화 품질]
  4. 색상 스케일 로그 변환 (공고수 편중 해결)
  5. 구/시 레이블 겹침 방지 (주요 지역만 선택적 표시)
  6. 공고 없는 지역: 회색 + 툴팁에 "데이터 없음" 명시
  7. 발표용 색상·폰트 통일

사용 파일:
  - posting_analysis_table_최종.xlsx
  - skorea-municipalities-2018-geo.json
"""

import json
import re
import numpy as np
import pandas as pd
import geopandas as gpd
import folium
from folium import plugins
import branca.colormap as cm


# ── 상수 ──────────────────────────────────────────────────────────────────────

DATA_PATH   = r"C:\py_temp\중간프로젝트\posting_analysis_table_최종.xlsx"
GEO_PATH    = r"C:\py_temp\중간프로젝트\skorea-municipalities-2018-geo.json"
OUTPUT_PATH = r"C:\py_temp\중간프로젝트\채용공고_지역별_지도_v3.html"

SIDO_CODE_MAP = {
    "11": "서울", "21": "부산", "22": "대구", "23": "인천",
    "24": "광주", "25": "대전", "26": "울산", "29": "세종",
    "31": "경기", "32": "강원", "33": "충북", "34": "충남",
    "35": "전북", "36": "전남", "37": "경북", "38": "경남", "39": "제주",
}

OVERSEAS_SIDOS = {"동경", "미국", "베트남", "일본", "헝가리"}

# 레이어별 색상 팔레트 (발표용)
PALETTE = {
    "전체 공고":    ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"],   # Blue
    "데이터 분석가": ["#fcfbfd", "#dadaeb", "#9e9ac8", "#6a51a3", "#3f007d"],   # Purple
    "백엔드 개발자": ["#fff5eb", "#fdd0a2", "#fd8d3c", "#d94801", "#7f2704"],   # Orange
}

# 레이블 표시할 주요 지역 (겹침 방지용 화이트리스트)
LABEL_WHITELIST = {
    "서울 강남구", "서울 서초구", "서울 영등포구", "서울 구로구", "서울 송파구",
    "서울 강서구", "서울 금천구", "서울 중구", "서울 성동구", "서울 마포구",
    "경기 성남시", "경기 고양시", "경기 수원시", "경기 용인시", "경기 안양시",
    "경기 과천시", "경기 화성시",
}

FONT = "'Malgun Gothic', 'Apple SD Gothic Neo', 'NanumGothic', sans-serif"


# ── 1. 데이터 로드 및 전처리 ───────────────────────────────────────────────────

def load_and_clean(path: str) -> pd.DataFrame:
    df = pd.read_excel(path)
    df = df[~df["region_sido"].isin(OVERSEAS_SIDOS)].copy()
    df = df[df["시각화용_지역"].str.contains(" ", na=False)].copy()
    df["region_key"] = df["시각화용_지역"].str.strip().str.split().str[:2].str.join(" ")
    return df


def aggregate(df: pd.DataFrame) -> pd.DataFrame:
    """지역별 공고수 / 평균 품질점수 / 위험도 집계"""
    agg = df.groupby("region_key").agg(
        공고수=("posting_id", "count"),
        품질점수=("posting_quality_score", "mean"),
        위험도=("risk_signal_score", "mean"),
    ).reset_index()
    agg["품질점수"] = agg["품질점수"].round(1)
    # 위험도: risk_signal_score가 낮을수록 위험 → 반전해서 '위험도'로 표현
    agg["위험도"] = (100 - agg["위험도"]).round(1)
    # 로그 스케일 공고수 (색상 매핑용) — 원본 공고수는 툴팁에 별도 보존
    agg["공고수_log"] = np.log1p(agg["공고수"])
    return agg


# ── 2. GeoJSON 전처리 (서울 구 단위 + 경기 시 단위 병합) ───────────────────────

def extract_gyeonggi_si(name: str) -> str:
    """'성남시수정구' → '성남시', '부천시' → '부천시', '연천군' → '연천군'"""
    m = re.match(r"(.+?시|.+?군)", name)
    return m.group(1) if m else name


def build_geodataframe() -> gpd.GeoDataFrame:
    """
    GeoJSON 로드 후:
    - 서울 등 일반 지역: 구 단위 그대로
    - 경기도: 시 단위로 dissolve
    sido_gu 컬럼을 기준 키로 사용
    """
    gdf = gpd.read_file(GEO_PATH)

    # sido_gu 생성
    def make_key(row):
        code = row["code"]
        sido = SIDO_CODE_MAP.get(code[:2], "")
        name = row["name"]
        if code[:2] == "31":   # 경기도 → 시 단위 키
            gu = extract_gyeonggi_si(name)
        else:
            gu = name
        return f"{sido} {gu}"

    gdf["sido_gu"] = gdf.apply(make_key, axis=1)

    # 경기도는 dissolve
    gyeonggi = gdf[gdf["code"].str[:2] == "31"].copy()
    others   = gdf[gdf["code"].str[:2] != "31"].copy()

    gyeonggi_dissolved = (
        gyeonggi.dissolve(by="sido_gu")
        .reset_index()[["sido_gu", "geometry"]]
    )
    others_clean = others[["sido_gu", "geometry"]].copy()

    result = gpd.GeoDataFrame(
        pd.concat([others_clean, gyeonggi_dissolved], ignore_index=True),
        crs="EPSG:4326"
    )
    return result


def inject_stats(gdf: gpd.GeoDataFrame, agg: pd.DataFrame, prefix: str) -> gpd.GeoDataFrame:
    """집계값을 prefix_{컬럼} 형태로 GeoDataFrame에 주입"""
    lookup = agg.set_index("region_key")
    for col in ["공고수", "품질점수", "위험도", "공고수_log"]:
        gdf[f"{prefix}_{col}"] = gdf["sido_gu"].map(lookup[col])
    return gdf


# ── 3. 레이어 생성 ────────────────────────────────────────────────────────────

def make_colormap(colors: list, vmin: float, vmax: float, caption: str):
    return cm.LinearColormap(colors=colors, vmin=vmin, vmax=vmax, caption=caption)


def add_layer(
    m: folium.Map,
    gj: dict,            # 집계값이 주입된 GeoJSON dict
    layer_name: str,
    prefix: str,
    colors: list,
    log_max: float,
    show: bool = False,
) -> None:
    prop_log  = f"{prefix}_공고수_log"
    prop_cnt  = f"{prefix}_공고수"
    prop_qual = f"{prefix}_품질점수"
    prop_risk = f"{prefix}_위험도"

    colormap = make_colormap(colors, 0, log_max, f"{layer_name} 공고수 (log)")
    group    = folium.FeatureGroup(name=layer_name, show=show)

    def style_fn(feature):
        val = feature["properties"].get(prop_log)
        if val is None or val == 0:
            return {
                "fillColor": "#e0e0e0",
                "color": "#bbbbbb",
                "weight": 0.4,
                "fillOpacity": 0.3,
            }
        return {
            "fillColor": colormap(val),
            "color": "#444",
            "weight": 0.8,
            "fillOpacity": 0.78,
        }

    def highlight_fn(feature):
        return {"weight": 2.5, "color": "#111", "fillOpacity": 0.93}

    # ── 툴팁 ──
    def tooltip_html(feature):
        props    = feature["properties"]
        sido_gu  = props.get("sido_gu", "")
        cnt      = props.get(prop_cnt)
        qual     = props.get(prop_qual)
        risk     = props.get(prop_risk)

        if cnt is None:
            body = "<span style='color:#999;'>데이터 없음</span>"
        else:
            body = (
                f"<b>공고 수:</b> {int(cnt)}건<br>"
                f"<b>평균 품질점수:</b> {qual:.1f}점<br>"
                f"<b>위험도:</b> {risk:.1f}"
            )
        return (
            f"<div style='font-family:{FONT};font-size:13px;"
            f"min-width:160px;'>"
            f"<div style='font-size:14px;font-weight:bold;"
            f"margin-bottom:5px;border-bottom:1px solid #eee;"
            f"padding-bottom:4px;'>{sido_gu}</div>"
            f"{body}</div>"
        )

    tooltip = folium.GeoJsonTooltip(
        fields=["sido_gu", prop_cnt, prop_qual, prop_risk],
        aliases=["지역", "공고 수", "평균 품질점수", "위험도"],
        localize=True,
        sticky=True,
        style=(
            "background-color:white;"
            "border:1px solid #ddd;"
            "border-radius:7px;"
            "padding:9px 13px;"
            f"font-family:{FONT};"
            "font-size:13px;"
            "box-shadow:0 3px 8px rgba(0,0,0,0.13);"
        ),
        labels=True,
    )

    # ── 팝업 ──
    popup = folium.GeoJsonPopup(
        fields=["sido_gu", prop_cnt, prop_qual, prop_risk],
        aliases=["📍 지역", "📋 공고 수", "⭐ 평균 품질점수", "⚠️ 위험도"],
        localize=True,
        style=(
            f"font-family:{FONT};"
            "font-size:13px;"
            "min-width:190px;"
        ),
    )

    folium.GeoJson(
        gj,
        style_function=style_fn,
        highlight_function=highlight_fn,
        tooltip=tooltip,
        popup=popup,
    ).add_to(group)

    group.add_to(m)
    colormap.add_to(m)


# ── 4. 주요 지역 레이블 마커 ──────────────────────────────────────────────────

def add_labels(m: folium.Map, gdf: gpd.GeoDataFrame, agg_total: pd.DataFrame) -> None:
    """공고 많은 주요 지역에만 구/시 이름 + 공고수 레이블 표시"""
    lookup = agg_total.set_index("region_key")["공고수"].to_dict()
    label_group = folium.FeatureGroup(name="지역 레이블", show=True)

    for _, row in gdf.iterrows():
        key = row["sido_gu"]
        if key not in LABEL_WHITELIST:
            continue
        cnt = lookup.get(key, 0)
        if cnt == 0:
            continue

        centroid = row["geometry"].centroid
        short_name = key.split(" ", 1)[1] if " " in key else key

        folium.Marker(
            location=[centroid.y, centroid.x],
            icon=folium.DivIcon(
                html=(
                    f"<div style='"
                    f"font-family:{FONT};"
                    f"font-size:10px;"
                    f"font-weight:bold;"
                    f"color:#1a1a2e;"
                    f"text-align:center;"
                    f"white-space:nowrap;"
                    f"text-shadow:1px 1px 2px white,-1px -1px 2px white,"
                    f"1px -1px 2px white,-1px 1px 2px white;'>"
                    f"{short_name}<br>"
                    f"<span style='font-size:9px;color:#555;font-weight:normal;'>"
                    f"{cnt}건</span></div>"
                ),
                icon_size=(60, 30),
                icon_anchor=(30, 15),
            ),
        ).add_to(label_group)

    label_group.add_to(m)


# ── 5. 지도 조립 ──────────────────────────────────────────────────────────────

def build_map(gdf: gpd.GeoDataFrame, dfs: dict) -> folium.Map:
    m = folium.Map(
        location=[36.5, 127.8],
        zoom_start=7,
        tiles=None,
    )

    # 베이스맵
    folium.TileLayer("CartoDB positron",    name="밝은 지도",  show=True).add_to(m)
    folium.TileLayer("CartoDB dark_matter", name="어두운 지도", show=False).add_to(m)

    prefix_map = {
        "전체 공고":    "total",
        "데이터 분석가": "da",
        "백엔드 개발자": "be",
    }

    # 집계 및 GDF 주입
    aggs = {}
    for layer_name, df in dfs.items():
        agg = aggregate(df)
        aggs[layer_name] = agg
        inject_stats(gdf, agg, prefix_map[layer_name])

    # GeoJSON 변환 (주입 완료 후 한 번만)
    gj = json.loads(gdf.to_json())

    # 로그 스케일 최대값 (전체 기준으로 통일)
    log_max = float(aggs["전체 공고"]["공고수_log"].max())

    # 레이어 추가 (전체 공고만 기본 표시)
    for i, (layer_name, _) in enumerate(dfs.items()):
        add_layer(
            m, gj,
            layer_name=layer_name,
            prefix=prefix_map[layer_name],
            colors=PALETTE[layer_name],
            log_max=log_max,
            show=(i == 0),
        )

    # 지역 레이블
    add_labels(m, gdf, aggs["전체 공고"])

    # ── 부가 기능 ──────────────────────────────────────────────────────────────
    folium.LayerControl(collapsed=False).add_to(m)
    plugins.Fullscreen(position="topright").add_to(m)
    plugins.MiniMap(toggle_display=True, position="bottomright").add_to(m)
    plugins.MousePosition(position="bottomleft").add_to(m)
    plugins.ScrollZoomToggler().add_to(m)

    # ── 타이틀 ────────────────────────────────────────────────────────────────
    title_html = f"""
    <div style="
        position:fixed; top:16px; left:50%; transform:translateX(-50%);
        z-index:1000; background:rgba(255,255,255,0.96);
        padding:10px 28px; border-radius:10px;
        box-shadow:0 3px 12px rgba(0,0,0,0.18);
        font-family:{FONT};
        font-size:15px; font-weight:bold; color:#1a1a2e;
        border-left:5px solid #2171b5;
    ">
        📊 채용공고 지역별 분포
        <span style="font-size:11px;font-weight:normal;color:#666;margin-left:10px;">
            서울 구 단위 · 경기 시 단위 | 색상 = 공고수 (로그 스케일)
        </span>
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

    # ── 범례 안내 ──────────────────────────────────────────────────────────────
    legend_html = f"""
    <div style="
        position:fixed; bottom:60px; left:16px;
        z-index:1000; background:rgba(255,255,255,0.93);
        padding:10px 14px; border-radius:8px;
        box-shadow:0 2px 8px rgba(0,0,0,0.14);
        font-family:{FONT};
        font-size:12px; color:#333; line-height:2;
    ">
        <b>사용 방법</b><br>
        🖱️ 호버 → 공고수 · 품질 · 위험도 확인<br>
        🖱️ 클릭 → 상세 팝업<br>
        ☰ 우측 패널 → 직무 레이어 전환<br>
        <span style="color:#999;font-size:11px;">
            ■ 회색 = 해당 직무 공고 없음
        </span>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    return m


# ── 6. 실행 ───────────────────────────────────────────────────────────────────

def main():
    print("▶ 데이터 로드 중...")
    df = load_and_clean(DATA_PATH)
    print(f"  국내 공고: {len(df)}건")

    df_total = df.copy()
    df_da    = df[df["job"] == "데이터 분석가"].copy()
    df_be    = df[df["job"] == "백엔드 개발자"].copy()
    print(f"  데이터 분석가: {len(df_da)}건 / 백엔드 개발자: {len(df_be)}건")

    print("▶ GeoJSON 처리 중 (경기도 시 단위 dissolve)...")
    gdf = build_geodataframe()
    print(f"  총 지역 수: {len(gdf)}개")

    print("▶ 지도 생성 중...")
    dfs = {
        "전체 공고":    df_total,
        "데이터 분석가": df_da,
        "백엔드 개발자": df_be,
    }
    m = build_map(gdf, dfs)

    m.save(OUTPUT_PATH)
    print(f"✅ 저장 완료: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
