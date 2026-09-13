"""
데이터 분석가 / 백엔드 개발자 채용공고 지역별 분포 지도 시각화 v4
-----------------------------------------------------------------
변경사항:
  - 위험도 제거
  - 툴팁: 공고수 + 적합도 / 품질점수 / 위험신호점수 / 최종점수 평균 포함
  - 레이어: [직무] × [지표] 조합으로 색상 기준 전환 가능
    → "강남구 공고 많지만 품질은?" / "품질 좋은 공고 어느 지역?" 답변 가능

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

DATA_PATH   = "posting_analysis_table_최종.xlsx"
GEO_PATH    = "skorea-municipalities-2018-geo.json"
OUTPUT_PATH = "채용공고_지역별_지도_v4.html"

SIDO_CODE_MAP = {
    "11": "서울", "21": "부산", "22": "대구", "23": "인천",
    "24": "광주", "25": "대전", "26": "울산", "29": "세종",
    "31": "경기", "32": "강원", "33": "충북", "34": "충남",
    "35": "전북", "36": "전남", "37": "경북", "38": "경남", "39": "제주",
}

OVERSEAS_SIDOS = {"동경", "미국", "베트남", "일본", "헝가리"}

# 직무별 기본 색상 (공고수 레이어)
JOB_BASE_COLOR = {
    "전체 공고":    ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"],
    "데이터 분석가": ["#fcfbfd", "#dadaeb", "#9e9ac8", "#6a51a3", "#3f007d"],
    "백엔드 개발자": ["#fff5eb", "#fdd0a2", "#fd8d3c", "#d94801", "#7f2704"],
}

# 지표별 색상 (직무 공통)
METRIC_COLOR = {
    "공고수":       None,           # 직무별 색상 사용
    "적합도":       ["#fff7ec", "#fee8c8", "#fdd49e", "#fc8d59", "#b30000"],
    "품질점수":     ["#f7fcf5", "#c7e9c0", "#74c476", "#238b45", "#00441b"],
    "위험신호점수":  ["#ffffcc", "#fed976", "#fd8d3c", "#e31a1c", "#800026"],
    "최종점수":     ["#f0f9e8", "#bae4bc", "#7bccc4", "#2b8cbe", "#084081"],
}

LABEL_WHITELIST = {
    "서울 강남구", "서울 서초구", "서울 영등포구", "서울 구로구", "서울 송파구",
    "서울 강서구", "서울 금천구", "서울 중구", "서울 성동구", "서울 마포구",
    "경기 성남시", "경기 고양시", "경기 수원시", "경기 용인시", "경기 안양시",
}

FONT = "'Malgun Gothic', 'Apple SD Gothic Neo', 'NanumGothic', sans-serif"

# 지표 표시명
METRIC_ALIAS = {
    "공고수":      "공고 수",
    "적합도":      "공고 적합도 (평균)",
    "품질점수":    "공고 품질점수 (평균)",
    "위험신호점수": "위험신호 점수 (평균)",
    "최종점수":    "최종점수 (평균)",
}


# ── 1. 데이터 로드 및 집계 ────────────────────────────────────────────────────

def load_and_clean(path: str) -> pd.DataFrame:
    df = pd.read_excel(path)
    df = df[~df["region_sido"].isin(OVERSEAS_SIDOS)].copy()
    df = df[df["시각화용_지역"].str.contains(" ", na=False)].copy()
    df["region_key"] = df["시각화용_지역"].str.strip().str.split().str[:2].str.join(" ")
    return df


def aggregate(df: pd.DataFrame) -> pd.DataFrame:
    agg = df.groupby("region_key").agg(
        공고수          =("posting_id",            "count"),
        적합도          =("posting_fit_score",      "mean"),
        품질점수        =("posting_quality_score",  "mean"),
        위험신호점수     =("risk_signal_score",      "mean"),
        최종점수        =("posting_final_score",     "mean"),
    ).reset_index()
    for col in ["적합도", "품질점수", "위험신호점수", "최종점수"]:
        agg[col] = agg[col].round(1)
    # 로그 스케일 공고수 (색상용)
    agg["공고수_log"] = np.log1p(agg["공고수"])
    return agg


# ── 2. GeoDataFrame 구성 (경기 시 단위 dissolve) ──────────────────────────────

def extract_gyeonggi_si(name: str) -> str:
    m = re.match(r"(.+?시|.+?군)", name)
    return m.group(1) if m else name


def build_geodataframe() -> gpd.GeoDataFrame:
    gdf = gpd.read_file(GEO_PATH)

    def make_key(row):
        code = row["code"]
        sido = SIDO_CODE_MAP.get(code[:2], "")
        name = row["name"]
        gu   = extract_gyeonggi_si(name) if code[:2] == "31" else name
        return f"{sido} {gu}"

    gdf["sido_gu"] = gdf.apply(make_key, axis=1)

    gyeonggi = gdf[gdf["code"].str[:2] == "31"].copy()
    others   = gdf[gdf["code"].str[:2] != "31"].copy()

    gyeonggi_d = (
        gyeonggi.dissolve(by="sido_gu")
        .reset_index()[["sido_gu", "geometry"]]
    )
    result = gpd.GeoDataFrame(
        pd.concat([others[["sido_gu", "geometry"]], gyeonggi_d], ignore_index=True),
        crs="EPSG:4326",
    )
    return result


def inject_stats(gdf: gpd.GeoDataFrame, agg: pd.DataFrame, prefix: str) -> None:
    lookup = agg.set_index("region_key")
    for col in ["공고수", "공고수_log", "적합도", "품질점수", "위험신호점수", "최종점수"]:
        gdf[f"{prefix}_{col}"] = gdf["sido_gu"].map(lookup[col])


# ── 3. 레이어 추가 ────────────────────────────────────────────────────────────

def get_colors(job: str, metric: str) -> list:
    """지표가 공고수면 직무별 색상, 나머지는 지표별 공통 색상"""
    if metric == "공고수":
        return JOB_BASE_COLOR[job]
    return METRIC_COLOR[metric]


def add_layer(
    m: folium.Map,
    gj: dict,
    job: str,
    metric: str,
    prefix: str,
    vmin: float,
    vmax: float,
    show: bool = False,
) -> None:
    # 색상 기준 컬럼
    color_prop = f"{prefix}_공고수_log" if metric == "공고수" else f"{prefix}_{metric}"

    colors   = get_colors(job, metric)
    colormap = cm.LinearColormap(
        colors=colors,
        vmin=vmin, vmax=vmax,
        caption=f"{job} — {METRIC_ALIAS[metric]}",
    )

    layer_label = f"{job} / {METRIC_ALIAS[metric]}"
    group = folium.FeatureGroup(name=layer_label, show=show)

    def style_fn(feature):
        val = feature["properties"].get(color_prop)
        if val is None or (metric == "공고수" and val == 0):
            return {"fillColor": "#e0e0e0", "color": "#bbb",
                    "weight": 0.4, "fillOpacity": 0.28}
        return {"fillColor": colormap(val), "color": "#444",
                "weight": 0.8, "fillOpacity": 0.78}

    def highlight_fn(feature):
        return {"weight": 2.5, "color": "#111", "fillOpacity": 0.93}

    # 툴팁: 모든 지표 항상 표시
    def make_tooltip_style():
        return (
            "background-color:white;"
            "border:1px solid #ddd;"
            "border-radius:7px;"
            "padding:10px 14px;"
            f"font-family:{FONT};"
            "font-size:13px;"
            "box-shadow:0 3px 8px rgba(0,0,0,0.13);"
            "min-width:200px;"
        )

    p = prefix  # 짧게
    tooltip = folium.GeoJsonTooltip(
        fields=[
            "sido_gu",
            f"{p}_공고수",
            f"{p}_적합도",
            f"{p}_품질점수",
            f"{p}_위험신호점수",
            f"{p}_최종점수",
        ],
        aliases=[
            "📍 지역",
            "📋 공고 수",
            "🎯 공고 적합도 (평균)",
            "⭐ 품질점수 (평균)",
            "⚠️ 위험신호점수 (평균)",
            "🏆 최종점수 (평균)",
        ],
        localize=True,
        sticky=True,
        style=make_tooltip_style(),
        labels=True,
    )

    popup = folium.GeoJsonPopup(
        fields=[
            "sido_gu",
            f"{p}_공고수",
            f"{p}_적합도",
            f"{p}_품질점수",
            f"{p}_위험신호점수",
            f"{p}_최종점수",
        ],
        aliases=[
            "📍 지역",
            "📋 공고 수",
            "🎯 공고 적합도 (평균)",
            "⭐ 품질점수 (평균)",
            "⚠️ 위험신호점수 (평균)",
            "🏆 최종점수 (평균)",
        ],
        localize=True,
        style=f"font-family:{FONT};font-size:13px;min-width:210px;",
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


# ── 4. 지역 레이블 ────────────────────────────────────────────────────────────

def add_labels(m: folium.Map, gdf: gpd.GeoDataFrame, agg_total: pd.DataFrame) -> None:
    lookup_cnt   = agg_total.set_index("region_key")["공고수"].to_dict()
    lookup_score = agg_total.set_index("region_key")["최종점수"].to_dict()
    label_group  = folium.FeatureGroup(name="지역 레이블", show=True)

    for _, row in gdf.iterrows():
        key = row["sido_gu"]
        if key not in LABEL_WHITELIST:
            continue
        cnt = lookup_cnt.get(key, 0)
        if cnt == 0:
            continue
        score    = lookup_score.get(key, 0)
        centroid = row["geometry"].centroid
        short    = key.split(" ", 1)[1] if " " in key else key

        folium.Marker(
            location=[centroid.y, centroid.x],
            icon=folium.DivIcon(
                html=(
                    f"<div style='font-family:{FONT};font-size:10px;"
                    f"font-weight:bold;color:#1a1a2e;text-align:center;"
                    f"white-space:nowrap;"
                    f"text-shadow:1px 1px 2px white,-1px -1px 2px white,"
                    f"1px -1px 2px white,-1px 1px 2px white;'>"
                    f"{short}<br>"
                    f"<span style='font-size:9px;color:#444;font-weight:normal;'>"
                    f"{cnt}건 · {score:.0f}점</span></div>"
                ),
                icon_size=(70, 32),
                icon_anchor=(35, 16),
            ),
        ).add_to(label_group)

    label_group.add_to(m)


# ── 5. 지도 조립 ──────────────────────────────────────────────────────────────

def build_map(gdf: gpd.GeoDataFrame, dfs: dict) -> folium.Map:
    m = folium.Map(location=[36.5, 127.8], zoom_start=7, tiles=None)

    folium.TileLayer("CartoDB positron",    name="밝은 지도",  show=True).add_to(m)
    folium.TileLayer("CartoDB dark_matter", name="어두운 지도", show=False).add_to(m)

    prefix_map = {
        "전체 공고":    "total",
        "데이터 분석가": "da",
        "백엔드 개발자": "be",
    }

    # 집계 및 GDF 주입
    aggs = {}
    for job, df in dfs.items():
        agg = aggregate(df)
        aggs[job] = agg
        inject_stats(gdf, agg, prefix_map[job])

    gj = json.loads(gdf.to_json())

    # 전역 범위 (스케일 통일)
    all_agg  = aggs["전체 공고"]
    log_max  = float(all_agg["공고수_log"].max())
    vrange   = {
        "공고수":      (0, log_max),
        "적합도":      (all_agg["적합도"].min(),      all_agg["적합도"].max()),
        "품질점수":    (all_agg["품질점수"].min(),    all_agg["품질점수"].max()),
        "위험신호점수": (all_agg["위험신호점수"].min(), all_agg["위험신호점수"].max()),
        "최종점수":    (all_agg["최종점수"].min(),    all_agg["최종점수"].max()),
    }

    # 레이어: 직무 3 × 지표 5 = 15개
    # 기본 표시: 전체 공고 / 공고수
    first = True
    for job in ["전체 공고", "데이터 분석가", "백엔드 개발자"]:
        for metric in ["공고수", "품질점수", "적합도", "위험신호점수", "최종점수"]:
            vmin, vmax = vrange[metric]
            add_layer(
                m, gj,
                job=job,
                metric=metric,
                prefix=prefix_map[job],
                vmin=vmin,
                vmax=vmax,
                show=first,
            )
            first = False

    # 레이블 (전체 공고 기준)
    add_labels(m, gdf, aggs["전체 공고"])

    # 부가 기능
    folium.LayerControl(collapsed=False).add_to(m)
    plugins.Fullscreen(position="topright").add_to(m)
    plugins.MiniMap(toggle_display=True, position="bottomright").add_to(m)
    plugins.MousePosition(position="bottomleft").add_to(m)
    plugins.ScrollZoomToggler().add_to(m)

    # 타이틀
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
            직무 · 지표별 레이어 전환 가능 | 색상 = 선택 지표 기준
        </span>
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

    # 범례 안내
    legend_html = f"""
    <div style="
        position:fixed; bottom:60px; left:16px; z-index:1000;
        background:rgba(255,255,255,0.93);
        padding:10px 14px; border-radius:8px;
        box-shadow:0 2px 8px rgba(0,0,0,0.14);
        font-family:{FONT};
        font-size:12px; color:#333; line-height:2;
    ">
        <b>레이어 패널 사용법</b><br>
        📋 공고수   → 어느 지역에 공고 많은가<br>
        ⭐ 품질점수 → 품질 좋은 공고 많은 지역<br>
        🏆 최종점수 → 종합 우수 지역<br>
        🖱️ 호버·클릭 → 모든 지표 동시 확인<br>
        <span style="color:#999;font-size:11px;">■ 회색 = 해당 직무 공고 없음</span>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    return m


# ── 6. 실행 ───────────────────────────────────────────────────────────────────

def main():
    print("▶ 데이터 로드 중...")
    df = load_and_clean(DATA_PATH)
    print(f"  국내 공고: {len(df)}건")

    dfs = {
        "전체 공고":    df.copy(),
        "데이터 분석가": df[df["job"] == "데이터 분석가"].copy(),
        "백엔드 개발자": df[df["job"] == "백엔드 개발자"].copy(),
    }
    for k, v in dfs.items():
        print(f"  {k}: {len(v)}건")

    print("▶ GeoJSON 처리 중 (경기 시 단위 dissolve)...")
    gdf = build_geodataframe()
    print(f"  총 지역 수: {len(gdf)}개")

    print("▶ 지도 생성 중...")
    m = build_map(gdf, dfs)

    m.save(OUTPUT_PATH)
    print(f"✅ 저장 완료: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
