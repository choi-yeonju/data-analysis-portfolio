from matplotlib import pyplot as plt 
import seaborn as sb
import platform
import numpy as np
from pandas import pivot_table
from scipy.spatial import ConvexHull

from . import my_stats

# # 한글 폰트 설정
# if platform.system() == 'Windows':
#     plt.rcParams['font.family'] = 'Malgun Gothic'
# elif platform.system() == 'Darwin':  # Mac
#     plt.rcParams['font.family'] = 'AppleGothic'
# else:  # Linux
#     plt.rcParams['font.family'] = 'NanumGothic'

# plt.rcParams['axes.unicode_minus'] = False  # 마이너스 기호 깨짐 방지

import os
import glob as gl
import matplotlib.font_manager as fm

# 한글 폰트 적용
fpath = "../helpers/fonts"
font_files = gl.glob(os.path.join(fpath, "*.ttf"))

for f in font_files:
    fm.fontManager.addfont(f)
    fprop = fm.FontProperties(fname=f)
    fname = fprop.get_name()
    plt.rcParams['font.family'] = fname

plt.rcParams['axes.unicode_minus'] = False

# ----------------------------------
def init(width=1280, height=640, rows=1, cols=1, 
         title=None, xlabel=None, ylabel=None, grid=True, twinx=False):

    """
    그래프의 크기와 dpi를 설정하여 fig와 ax 객체를 반환하는 함수 

    Parameters: 
        - width : 그래프의 가로 크기 ( 픽셀 단위)
        - height : 그래프의 세로 크기 ( 픽셀 단위) 
        - rows : 그래프의 행 수 
        - cols : 그래프의 열 수 
        - title : 그래프의 제목 ( 기본값 : None) 
        - xlabel : x축 레이블 ( 기본값 : None) 
        - ylabel : y축 레이블 (기본값 : None) 
        - grid : 그래프에 그리드를 표시할지 여부 (기본값 : True)

    Returns : 
        - fig : 생성된 Figure 객체 
        - ax : 생성된 Axes 객체 또는 Axes 배열 
    """
    # my_figsize = (width / 100, height/100) 
    # fig, ax = plt.subplots(rows, cols, figsize=my_figsize)
    # ax.grid(grid, alpha=0.5) 
    
    my_figsize = ((width/100) * cols, (height/100)*rows )
    fig, ax = plt.subplots(rows, cols, figsize=my_figsize, dpi=200)

    if rows > 1 or cols > 1: 
        ax = ax.flatten() # 2차원 배열을 1차원으로 평탄화하여 반복처리 
        fig.suptitle(title, fontsize=32, fontweight=500)

        for a in ax: 
            a.grid(grid, alpha=0.5)
    else: 
        ax.grid(grid, alpha=0.5)

        if title: 
            ax.set_title(title, fontsize=24, fontweight=500, pad=15)
        if xlabel: 
            ax.set_xlabel(xlabel, fontsize=16, fontweight=400, labelpad=5)
        if ylabel: 
            ax.set_ylabel(ylabel, fontsize=16, fontweight=400, labelpad=5)
        
    if twinx: 
        ax_right = ax.twinx()
        ax = (ax, ax_right)
        
    return fig, ax

def show(save_path=None): 
    """
    그래프를 화면에 표시하는 함수 

    Parameters : 
        - grig : 그리드를 표시할지 여부 (기본값 = True) 
        - save_path : 그래프를 저장할 파일 경로, None이면 저장하지 않음. 
    """       
    if save_path: 
        plt.savefig(save_path)

    plt.tight_layout()
    plt.show()
    plt.close()





def lineplot(data=None, x=None, y=None, hue=None, 
             title=None, xlabel=None, ylabel=None, 
             color=None, linewidth=2.0, linestyle="-",
             palette=None, marker=None, markersize=None, 
             markeredgewidth=None, markeredgecolor=None, 
             markerfacecolor=None, 
             width=1280, height=540, save_path=None, ax=None, **params):
    """
    선 그래프를 그린다. 

    Args : 
        data : 시각화할 데이터 
        x : x축 컬럼명 혹은 x축 값 시퀀스 
        y : y축 컬럼명 혹은 y축 값 시퀀스 
        hue : 범주 구분 컬럼명
        title : 그래프 제목 
        xlabel : x축 레이블
        ylabel : y축 레이블 
        color : 선 색상 
        linewidth : 선 굵기 
        linestyle : 선 스타일 
        palete : 색상 팔레트 이름 
        marker : 마커 모양 
        markersize : 마커 크기 
        markerdgewidth : 마커 테두리 두께 
        markeredecolor : 마커 테두리 색상 
        markerfacecolor : 마커 배경 색상 
        width : 캔버스 가로 픽셀 
        height : 캔버스 세로 픽셀 
        save_path : 이미지 저장 경로 
    """

    # 그래프 초기화 
    # init(width=width, height=height, title=title, xlabel=xlabel,
    #      ylabel=ylabel)
    fig = None
    if ax is None: 
        fig, ax = init(width=width, height=height, title=title, xlabel=xlabel,
                       ylabel=ylabel)
    
    # 선 그래프 그리기 
    sb.lineplot(data=data, x=x, y=y, hue=hue, 
                color=color, linewidth=linewidth, linestyle=linestyle, 
                palette=palette, marker=marker, markersize=markersize, 
                markeredgewidth=markeredgewidth, 
                markeredgecolor=markeredgecolor,
                markerfacecolor=markerfacecolor, 
                ax=ax, **params)
    # 그래프 표시 
    if fig is not None: 
        show(save_path=save_path)

def kdeplot(data=None, x=None, y=None, hue=None,
            meanline=False,  clevel=0, 
             title=None, xlabel=None, ylabel=None, 
             fill=False, linewidth=2.0, 
             palette=None, width=1280, height=540, save_path=None,
             ax=None):
    """
    단변량 커널 밀도 그래프를 그린다. 평균선은 hue가 설정된 경우 지원하지 않는다. 

    Args : 
        data: 시각화할 데이터 
        x : x축 컬럼명 혹은 x축 값 시퀀스 
        meanline : 평균선 표시 여부 
        title : 그래프 제목 
        xlabel : x축 레이블 
        ylabel : y축 레이블 
        fill : 면적 채우기 여부 
        linewidth : 선 굵기 
        palette : 색상 팔레트 이름 
        width : 캔버스 가로 픽셀 
        height : 캔버스 세로 픽셀 
        save_path : 이미지 저장 경로 
    """

    # 그래프 초기화 
    fig = None
    if ax is None:
        fig, ax = init(width=width, height=height, title=title, xlabel=xlabel, ylabel=ylabel)

    # 단변량 커널 밀도 그래프 그리기 
    sb.kdeplot(data=data, x=x, hue=hue, fill=fill, 
               linewidth=linewidth, palette=palette, ax=ax)
    
    # 신뢰구간 표시 (신뢰수준이 0이 아닌 경우에만) 
    if clevel : 
        ymin, ymax = ax.get_ylim() # 그래프의 y축 범위 조회 

        if hue is None : 
            # 그래프에 적용된 팔레트의 첫번째 색상을 따른다. (팔레트가 없으면 기본 파란색)
            color = sb.color_palette(palette)[0] if palette else '#0066ff'  
            # 전체 데이터에 대한 신뢰구간 표시 
            _draw_ci(ax, my_stats.ci(data, column=x, clevel=clevel), color, ymax)
        else : 
            # hue 범주별로 신뢰구간 표시 (kdeplot이 그린 라인의 색상과 일치시킴)
            categories = list(data[hue].unique())
            # 팔레트에서 범주의 수에 맞는 색상값 추출 
            colors = sb.color_palette(palette, n_colors=len(categories))

            # 각 범주에 대해 신뢰구간 표시 
            for i, cat in enumerate(categories):
                cdata = data.loc[data[hue]==cat, x]
                _draw_ci(ax, my_stats.ci(cdata, clevel=clevel), colors[i], ymax)
        
        ax.set_ylim(ymin, ymax)

    # 평균선 표시 
    if meanline: 
        y_max = ax.get_ylim()[1]

        if hue is None: 
            mv = data[x].mean()
            ax.axvline(x=mv, color='red', linestyle='--', linewidth=linewidth*0.5)
            ax.text(x=mv+0.05, y=y_max*0.95, s=f'Mean: {mv:.2f}', color='red', fontsize=14, ha='center')
        else:
            # hue 범주별 평균선 표시 (kdeplot이 그린 라인의 색상과 일치시킴) 
            categories = list(data[hue].unique())
            # 팔레트에서 범주의 수에 맞는 색상값 추출 
            colors = sb.color_palette(palette, n_colors=len(categories))

            # 각 범주에 대해 평균선 표시 
            for i, cat in enumerate(categories):
                mv = data.loc[data[hue] == cat, x ].mean()
                ax.axvline(x=mv, color=colors[i], linestyle='--', linewidth=linewidth*0.5)
                ax.text(x=mv +0.05, y=y_max*(0.95- i*0.07), s=f'{cat} Mean: {mv:.2f}', 
                        color=colors[i], fontsize=14, ha='center')
                
    # 그래프 표시 
    if fig is not None:
        show(save_path=save_path)

def histplot(data=None, x=None,hue=None, bins="auto", 
              title=None, xlabel=None, ylabel=None, 
              linewidth=1, palette=None, kde=False, 
              width=1280, height=640, save_path=None, 
              ax=None):
    """
    히스토그램을 그린다. 

    Args: 
        data : 시각화할 데이터 
        x : 히스토그램 대상 컬럼명 
        bins : 구간 수 또는 경계 
        hue : 범주 컬럼명 
        title : 그래프 제목 
        xlabel : x축 레이블 
        ylabel : y축 레이블 
        linewidth : 선 굵기 
        palette : 색상 팔레트 이름 
        kde : 커널 밀도 그래프 겹쳐 그릴지 여부 
        width : 캔버스 가로 픽셀 
        height : 캔버스 세로 픽셀 
        save_path : 이미지 저장 경로 
    """

    # 그래프 초기화 
    fig = None
    if ax is None:
        fig, ax = init(width=width, height=height, title=title, xlabel=xlabel,
                   ylabel=ylabel)
    
    # 구간 산정 
    if isinstance(bins, int): 
        hist, bins = np.histogram(data[x], bins=bins)
        bins = np.round(bins, 1)
        ax.set_xticks(bins, bins) 
    elif isinstance(bins, (list, np.ndarray)):
        ax.set_xticks(bins, bins)

    # 히스토그램 그리기 
    sb.histplot(data=data, x=x, hue=hue, linewidth=linewidth, 
                palette=palette, kde=kde, bins=bins, ax=ax)
    
    # 그래프 표시 
    if fig is not None:
        show(save_path=save_path)


def boxplot(data=None, x=None, y=None, hue=None, orient=None, palette=None, 
            order=None, title=None, xlabel=None, ylabel=None,
            width=1280, height=640, save_path=None, ax=None): 
    """
    상자그림(boxplot)을 그린다. 

    Args: 
        data : 시각화할 데이터 
        x : 히스토그램 대상 컬럼명 
        y : x축 범주 컬럼명 
        hue : 범주 구분 컬럼명 
        orient : 상자그림 방향(None, 'v' 또는 'h')
        palette : 색상 팔레트 이름 
        order : 상자그림 순서를 의미하는 연속형 자료형 
        title : 그래프 제목 
        xlabel : x축 레이블 
        ylabel : y축 레이블 
        width : 캔버스 가로 픽셀 
        height : 캔버스 세로 픽셀 
        save_path : 이미지 저장 경로 
    """

    # 그래프 초기화 
    fig = None
    if ax is None:
        fig, ax = init(width=width, height=height, title=title, xlabel=xlabel, ylabel=ylabel)

    # 상자그림 그리기 
    sb.boxplot(data=data, x=x, y=y, hue=hue, orient=orient, order=order, palette=palette, ax=ax, dodge="auto", legend="auto")

    # 그래프 표시 
    if fig is not None:
        show(save_path=save_path)


def violinPlot(data=None, x=None, y=None, hue=None, orient=None, palette=None, 
            title=None, xlabel=None, ylabel=None, 
            width=1280, height=640, save_path=None, ax=None): 
    """
    바이올린 플롯(violinPlot)을 그린다. 

    Args : 
        data : 시각화할 데이터 
        x : x축 범주 컬럼명
        y : y축 값 컬럼명 
        hue : 범주 구분 컬럼명 
        orient : 바이린 그림 방향 (None, 'v'또는 'h')
        palette : 색상 팔레트 이름 
        title : 그래프 제목 
        xlabel : x축 레이블 
        ylabel : y축 레이블 
        width : 캔버스 가로 픽셀 
        height : 캔버스 세로 픽셀 
        save_path : 이미지 저장 경로 
    """

    # 그래프 초기화 
    fig = None
    if ax is None:
        fig, ax = init(width=width, height=height, title=title, xlabel=xlabel, ylabel=ylabel)

    # 바이올린 플롯 그리기 
    sb.violinplot(data=data, x=x, y=y, hue=hue, orient=orient, 
                  palette=palette, ax=ax)

    # 그래프 표시 
    if fig is not None: 
        show(save_path=save_path)

# 히트맵 모듈화 
def heatmap(data=None, annot=True, fmt="0.2f", linewidths=0.5, 
            palette=None, title=None, xlabel=None, ylabel=None,
            width=1280, height=640, save_path=None, ax=None, **params):
    """
    히트맵을 그린다. 

    Args : 
        data : 시각화할 데이터 (2차원 배열 또는 DataFrame)
        annot : 셀에 값 표시 여부 
        fmt : 셀에 표시할 값의 형식 
        linewidths : 셀 간격 선 두께
        palette : 색상 팔레트 이름 
        title : 그래프 제목 
        xlabel : x축 레이블 
        ylabel : y축 레이블 
        width : 캔버스 가로 픽셀 
        height : 캔버스 세로 픽셀 
        save_path : 이미지 저장 경로 
    """

    # 그래프 초기화 
    fig = None
    if ax is None:
        fig, ax = init(width=width, height=height, title=title, xlabel=xlabel, ylabel=ylabel)

    # 그리드 제거 
    ax.grid(False) 

    # 히트맵 그리기
    sb.heatmap(data=data, annot=annot, fmt=fmt, linewidths=linewidths, cmap=palette, ax=ax, **params)

    # 그래프 표시 
    if fig is not None:
        show(save_path=save_path)


def barplot(data=None, x=None, y=None, hue=None, estimator=np.mean,
            order=None, palette=None, title=None, xlabel=None, ylabel=None, 
            width=1280, height=640, save_path=None, ax=None):
    """
    막대그래프를 그린다. 

    Args: 
        data : 시각화할 데이터 (2차원 배열 또는 DataFrame )
        x : x축 범주 컬럼명 
        y : y축 값 컬럼명 
        hue : 범주 구분 컬럼명 
        estimator : 막대 높이 계산 함수 (기본값 : np.mean)
        order : 정렬순서를 의미하는 연속형 자료형 
        palette : 색상 팔레트 이름 
        title : 그래프 제목 
        xlabel : x축 레이블 
        ylabel : y축 레이블 
        width : 캔버스 가로 픽셀
        height : 캔버스 세로 픽셀 
        save_path : 이미지 저장 경로 
    """

    # 그래프 초기화 
    fig = None
    if ax is None:
        fig, ax = init(width=width, height=height, 
                   title=title, xlabel=xlabel, ylabel=ylabel)
    
    # 막대 그래프 그리기 
    sb.barplot(data=data, x=x, y=y, hue=hue, estimator=estimator, 
               order=order, palette=palette, ax=ax)
    
    # 그래프 표시 
    if fig is not None:
        show(save_path=save_path)


# CountPlot
def countplot(data=None, x=None, y=None, hue=None, order=None, 
              palette=None, title=None, xlabel=None, ylabel=None, 
              width=1280, height=640, save_path=None, ax=None):
    """
    막대그래프를 그린다. 

    Args: 
        data : 시각화할 데이터 (2차원 배열 또는 DataFrame )
        x : x축 범주 컬럼명 
        y : y축 값 컬럼명 
        hue : 범주 구분 컬럼명 
        order : 정렬순서를 의미하는 연속형 자료형 
        palette : 색상 팔레트 이름 
        title : 그래프 제목 
        xlabel : x축 레이블 
        ylabel : y축 레이블 
        width : 캔버스 가로 픽셀
        height : 캔버스 세로 픽셀 
        save_path : 이미지 저장 경로 
    """
    # 그래프 초기화 
    fig = None
    if ax is None: 
        fig, ax = init(width=width, height=height, 
                   title=title, xlabel=xlabel, ylabel=ylabel)
    
    # 막대 그래프 그리기 
    sb.countplot(data=data, x=x, y=y, hue=hue, order=order, palette=palette, ax=ax)
    
    # 그래프 표시 
    if fig is not None:
        show(save_path=save_path)

def pieplot(x, labels, autopct="%0.1f%%", startangle=90, counterclock=False,
            explode=None, donutchart=False, 
            wedge_width=0.7, wedge_color="#ffffff", wedge_linewidth=3,
            palette=None, title=None, xlabel=None, ylabel=None,
            width=1280, height=640, save_path=None, ax=None):
    """
    파이 그래프 혹은 도넛 그래프를 그린다. 

    Args: 
        x : x축 범주 컬럼명 
        labels : 파이 조각에 대한 라벨 
        autopct : 퍼센트 표시 형식 
        startangle : 시작 각도
        counterclock : 시계 반대 방향으로 그릴지 여부 
        explode : 조각 간격 
        donutchart : 도넛 차트 여부 
        wedge_width : 도넛 차트일때 조각 너비 비율 
        wedge_color : 도넛 차트일때 조각 사이 경계선 색상 
        wedge_linewidth : 도넛 차트일때 조각 사이 경계선 굵기 
        palette : 색상 팔레트 이름 
        title : 그래프 제목 
        xlabel : x축 레이블 
        ylabel : y축 레이블 
        width : 캔버스 가로 픽셀
        height : 캔버스 세로 픽셀 
        save_path : 이미지 저장 경로 
    """

    # 그래프 초기화 
    fig = None
    if ax is None:
        fig, ax = init(width=width, height=height, title=title, 
                   xlabel=xlabel, ylabel=ylabel)
    
    # 색상값을 팔레트로 부터 추출 
    color_list = None
    if palette: 
        color_list = sb.color_palette(palette, n_colors=len(labels))

    # 도넛 그래프 그리기 옵션 생성 
    wedgeprops = None 
    if donutchart: 
        wedgeprops={"width":wedge_width, "edgecolor":wedge_color,
                    "linewidth":wedge_linewidth}
    
    # 파이 차트 그리기 
    ax.pie(x, labels=labels, autopct=autopct, startangle=startangle,
           counterclock=counterclock, explode=explode,
           colors=color_list, wedgeprops=wedgeprops)
    
    # 그래프 표시 
    if fig is not None:
        show(save_path=save_path)

def stackplot(data, x, y, hue, aggfunc=np.sum, orient='v', ratio=False, 
              text=True, text_color='#ffffff', text_fontsize=12,
              text_format= None,
              palette=None, title=None, xlabel=None, ylabel=None,
              width=1280, height=640, save_path=None, ax=None):
    
    """
    누적 막대 그래프를 그린다. 

    Args : 
        data : 시각화할 데이터 
        x : x축 범주 컬럼명 
        y : y축 값 컬럼명 
        hue : 범주 구분 컬럼명 
        aggfunc : 누적할 값 계산 함수 (기본값 : np.sum)
        orient : 막대방향 ( 'v' 또는 'h' )
        ratio : 누적값을 비율로 표시할지 여부 
        text : 누적값 텍스트 표시 여부 
        text_color : 누적값 텍스트 색상 
        text_fontsize : 누적값 텍스트 폰트 크기 
        palette : 색상 팔레트 이름 
        title : 그래프 제목 
        xlabel : x축 레이블 
        ylabel : y축 레이블 
        width : 캔버스 가로 픽셀
        height : 캔버스 세로 픽셀 
        save_path : 이미지 저장 경로 
    """

    # 그래프 초기화 
    fig = None
    if ax is None:
        fig, ax = init(width=width, height=height, title=title, 
                   xlabel=xlabel, ylabel=ylabel)
    
    # 데이터 피벗팅 (fill_value =0 -> 결측치를 0으로 채움) 후 인덱스를 문자열 카테고리로 변환 
    df = pivot_table(data=data, index=x, values=y, columns=hue, aggfunc=aggfunc,
                     fill_value=0)
    df.index = df.index.astype("str").astype("category")

    # 누적값을 비율로 변환하는 경우 
    if ratio : 
        if text_format is None: 
            text_format = "{:.1f}%" # 텍스트 포멧이 없다면 강제 지정 
        
        df['sum'] = df.sum(axis=1) # 각 행의 합 계산하여 'sum'열에 저장 

        for col in df.columns: 
            df[col] = df[col] / df['sum'] * 100

        df.drop(columns='sum', inplace=True) # 'sum' 열 제거 
        
        if orient == 'v': 
            ax.set_ylim(0, 100)
        else: 
            ax.set_xlim(0, 100)
    else: 
        if text_format is None: # 텍스트 포멧이 없다면 강제 지정 
            text_format = "{:.1f}"

    # 색상값 생성하기 
    color_list = None 
    if palette is not None:
        color_list = sb.color_palette(palette, n_colors=len(df.columns))

    # 피벗 테이블의 각 열에 대해 누적 막대 그래프 그리기 
    for i, col in enumerate(df.columns): 
        color = None 

        if color_list is not None: 
            color = color_list[i]

        if orient == 'v': 
            ax.bar(df.index, df[col], bottom=df.iloc[:, :i].sum(axis=1), color=color,
                   label = col) 
        else: 
            ax.barh(df.index, df[col], left=df.iloc[:, :i].sum(axis=1), color=color,
                    label=col)
            # 누적값 텍스트 표시 
        if text: 
            for j, val in enumerate(df[col]): 
                if val ==0 : # 누적값이 0인경우 텍스트 표시하지 않음 
                        continue 
                if orient == 'v': 
                    ax.text(x=j, y=df.iloc[j, :i].sum() + val/2,
                                s=text_format.format(val), ha='center', va='center',
                                color=text_color, fontsize=text_fontsize)
                else: 
                    ax.text(x=df.iloc[j, :i].sum() + val/2, y=j, 
                                s=text_format.format(val), ha='center', va='center',
                                color=text_color, fontsize=text_fontsize)
    # 범례표시 
    ax.legend(bbox_to_anchor=(1,1))

    # 그래프 표시 
    if fig is not None:
        show(save_path=save_path)

def scatterplot(data, x, y, hue=None, marker='o', color=None, size=100,
                edgecolor='#ffffff', linewidth=1.5, alpha=1, 
                legend=True,  palette=None, label=None, 
                outline=True, title=None, xlabel=None, ylabel=None,
                width=1280, height=640, save_path=None, ax=None):
    """
    산점도를 그린다. 

    Args : 
        data : 시각화할 데이터 
        x : x축 값 컬럼명 
        y : y축 값 컬럼명 
        hue : 범주 구분 컬럼명 
        marker : 마커 모양 (기본값 : "O" )
        color : 마커 색상 ( hue가 None일 때 적용 )
        size : 마커 크기 (기본값 : 100)
        edgecolor : 마커 테두리 색상 (기본값 : "#ffffff")
        linewidth : 마커 테두리 두께 (기본값 : 1.5)
        alpha : 마커 투명도 (0~1, 기본값 : 1) 
        palette : 색상 팔레트 이름 
        title : 그래프 제목 
        xlabel : x축 레이블 
        ylabel : y축 레이블 
        width : 캔버스 가로 픽셀
        height : 캔버스 세로 픽셀 
        save_path : 이미지 저장 경로 
    """    

    # 그래프 초기화 
    fig = None
    if ax is None:
        fig, ax = init(width=width, height=height, title=title, 
                    xlabel=xlabel, ylabel=ylabel)
    
    # 군집을 구분할 분류값이 없다면 palette 옵션이 무의미 하므로 None으로 설정 
    if hue == None : 
        if color is None and palette is not None: 
            color = sb.color_palette(palette)[0]

            palette = None
    else: 
        color = None

    # # 산점도 그리기 
    # sb.scatterplot(data=data, x=x, y=y, 
    #                hue = hue,                # 군집을 구분할 분류값이 있는 컬럼명,
    #                color = color,            # 마커 색상 
    #                palette=palette,          # 색상 팔레트 설정 
    #                marker=marker,            # 마커 모양 
    #                s = size,                 # 마커 크기 (기본값 = 100) 
    #                edgecolor = edgecolor,    # 마커 테두리 색상 
    #                linewidth=linewidth,      # 마커 테두리 두께
    #                alpha = alpha,            # 마커 투명도
    #                legend=legend,            # 추가
    #                ax=ax
    #                )
    
    # # hue가 없을 때만 label 적용 (hue가 있으면 seaborn이 자동으로 범례 생성) 추가
    # if hue is None and label is not None:
    #     scatter_kwargs['label'] = label

    # sb.scatterplot(**scatter_kwargs) 추가

    # # 외곽선 그리기 
    # if outline and hue is not None : 
    #     # 외곽선 그리기 
    #     plot_hull(data=data, x=x, y=y, hue=hue, palette=palette, ax=ax)


    # # 그래프 표시 
    # if fig is not None:
    #     show(save_path=save_path)

    # 산점도 그리기 위한 인자 구성
    scatter_kwargs = dict(
        data=data, x=x, y=y,
        hue=hue,                 # 군집을 구분할 분류값이 있는 컬럼명
        color=color,             # 마커 색상
        palette=palette,         # 색상 팔레트 설정
        marker=marker,           # 마커 모양
        s=size,                  # 마커 크기 (기본값 = 100)
        edgecolor=edgecolor,     # 마커 테두리 색상
        linewidth=linewidth,     # 마커 테두리 두께
        alpha=alpha,             # 마커 투명도
        legend=legend,           # 범례 표시 여부
        ax=ax
    )

    # hue가 없을 때만 label 적용 (hue가 있으면 seaborn이 자동으로 범례 생성)
    if hue is None and label is not None:
        scatter_kwargs['label'] = label

    # 산점도 그리기 
    sb.scatterplot(**scatter_kwargs)

    # 외곽선 그리기 
    if outline and hue is not None : 
        plot_hull(data=data, x=x, y=y, hue=hue, palette=palette, ax=ax)

    # 그래프 표시 
    if fig is not None:
        show(save_path=save_path)

def plot_hull(data, x, y, hue, palette, ax):
    """
    ConvexHull 을 이용하여 각 군집의 외곽선을 그리는 함수 

    Args : 
        data : 시각화할 데이터 
        x : x축 값 컬럼명 
        y : y축 값 컬럼명
        hue : 범주 구분 컬럼명
        palette : 색상 팔레트 이름 
        ax : ConvexHull로 외곽선을 그릴 Axes 객체 
    """
    
    # 데이터의 군집 종류 얻기 
    classes = list(data[hue].unique())

    # 각 클래스에 대하여 반복 수행 
    for i, v in enumerate(classes): 
        # 현재 클래스에 해당하는 데이터 포인트 추출 
        df_c = data.loc[data[hue] == v, [x, y]]

        # ConvexHull은 3개 이상의 점이 필요하므로, 데이터 포인트가 3개 미만인 경우 중단해야 함 
        if len(df_c) < 3: 
            continue

        hull = ConvexHull(df_c)
        points = np.append(hull.vertices, hull.vertices[0])

        # 현재 클래스에 적용될 색상값 생성 
        color = sb.color_palette(palette)[i]

        # points를 index로 하는 데이터 포인트를 선과 면으로 표시 
        ax.plot(df_c.iloc[points, 0], df_c.iloc[points,1], linewidth=1, linestyle=":", color=color)
        ax.fill(df_c.iloc[points, 0], df_c.iloc[points,1], alpha=0.1 , color=color)

def lmplot(data, x, y, hue=None, palette=None, col=None, row=None, markers="o",
           scatter_edgecolor="#ffffff", scatter_linewidths=1, scatter_size=50,
           scatter_alpha=0.8, linestyle="-", linecolor=None, linewidth=2, 
           title=None, xlabel=None, ylabel=None, width=1280, height=640,
           save_path=None) : 
    """
    seaborn lmplot으로 산점도 그래프와 회귀선을 시각화 한다. 

    Args : 
        data (DataFrame) : 시각화할 데이터 
        x (str) : 독립변수 컬럼
        y (str) : 종속변수 컬럼 
        hue (str|None) : 범주 컬럼 
        palette (str|None) : 팔레트 이름 
        col (str|None) : 열 패싯 컬럼 
        row (str|None) : 행 패싯 컬럼 
        markers (str|list[str]) : 산점도 점 모양 
        scatter_edgecolor (str|None) : 산점도 점 외곽선 색상 
        scatter_linewidths (float) : 산점도 점 외곽선 굵기 
        scatter_size (int) : 산점도 점 크기 
        scatter_alpha (float) : 산점도 점 투명도 
        linestyle (str) : 회귀선 스타일 
        linecolor (str|None) : 회귀선 색상
        linewidth (float) : 회귀선 굵기 
        title (str|None) : 그래프 제목 
        xlabel (str|None) : x축 레이블 
        ylabel (str|None) : y축 레이블 
        width (int) : 캔버스 가로 픽셀 
        height (int) : 캔버스 세로 픽셀 
        save_path (str|None) : 이미지 저장 경로. None이면 화면에 표시 

    Returns : 
        None
    """

    # 1) 그래프 초기화 
    w = width / 100 # 가로 크기 
    h = height / 100 # 세로 크기 
    my_dpi = 200 # 해상도 설정 

    # hue가 지정되지 않았는데 palette와 linecolor가 지정된 경우, 무의미하므로 None으로 설정 
    if not hue and palette: 
        palette = None
        linecolor = None

    # 2) lmplot 그리기 
    g = sb.lmplot(data=data, x=x, y=y, height=h, aspect=w/h, hue=hue, col=col, row=row, 
                  legend=False, markers=markers, palette=palette, 
                  scatter_kws={
                      "edgecolor": scatter_edgecolor, "linewidths": scatter_linewidths, 
                      "s": scatter_size, "alpha": scatter_alpha } , 
                      line_kws={
                          "linestyle" : linestyle, "color": linecolor, 
                          "linewidth": linewidth}
                  )

    # 3) 그래프 설정 및 표시 
    g.fig.set_dpi(my_dpi)
    g.fig.set_tight_layout(True)

    if title :
        g.fig.suptitle(title, fontsize=24, fontweight=500, y=1)

    for x in g.axes.flatten():
        x.grid(True, alpha=0.5)
        x.set_axisbelow(True) 

        if xlabel: x.set_xlabel(xlabel, fontsize=16, fontweight=400, labelpad=5)
        if ylabel: x.set_ylabel(ylabel, fontsize=16, fontweight=400, labelpad=5)
        
        if hue is not None: 
            x.legend(bbox_to_anchor=(1,1), loc='upper left') # 범례 위치 조정

    show(save_path=save_path) 

def pairplot(data, x=None, y=None, hue=None, palette=None, diag_kind="kde", reg=False, 
             markers="o", scatter_size=20, scatter_alpha=0.8, 
             linecolor=None, linewidth=1.5, linestyle="-", 
             title=None, width=1280, height=640, save_path=None): 
    """
    산점도 행렬 시각화 

    Args : 
        data (DataFrame) : 시각화할 데이터 
        x (str|list[str]|None) : 대상 컬럼명 혹은 컬럼명 리스트 
        y (str|list[str]|None) : 대상 컬럼명 혹은 컬럼명 리스트 
        hue (str|None) : 범주 컬럼명 
        palette (str|None) : 팔레트 이름 
        diag_kind (str): 대각선에 표시할 그래프 종류, 'hist' 또는 'kde' 
        reg (bool) : 회귀선 표시 여부 
        markers (str|list[str]) : 산점도 점 모양 
        scatter_size (int) : 산점도 점 크기 
        scatter_alpha (float) : 산점도 점 투명도 
        linecolor (str|None) : 회귀선 색상
        linewidth (float) : 회귀선 굵기 
        linestyle (str) : 회귀선 스타일 
        title (str|None) : 그래프 제목 
        width (int) : 캔버스 가로 픽셀 
        height (int) : 캔버스 세로 픽셀 
        save_path (str|None) : 이미지 저장 경로. None이면 화면에 표시 
    """    

    # 1) 그래프 초기화 
    figsize = (width/ 100, height/ 100)

    # hue가 지정되지 않았는데 palette와 linecolor가 지정된 경우, 무의미하므로 None으로 설정
    if not hue and palette: 
        palette = None
    
    # 회귀선의 표시 여부를 따라서 plot_kws 분기 
    if reg: 
        plot_kws = {
            "scatter_kws" : {"s" : scatter_size, "alpha": scatter_alpha}, 
            "line_kws" : {"color": linecolor, "linewidth": linewidth, 
                          "linestyle": linestyle}
        }
    else: 
        plot_kws = {"s": scatter_size, "alpha": scatter_alpha}

    # 2) pairplot 그리기 
    g = sb.pairplot(data=data, hue=hue, markers=markers, palette=palette, 
                    kind="reg" if reg else "scatter", 
                    diag_kind=diag_kind, plot_kws=plot_kws)
    
    g.fig.set_dpi(200)
    g.fig.set_figwidth(figsize[0])
    g.fig.set_figheight(figsize[1])

    if title: 
        g.fig.suptitle(title, fontsize=24, fontweight='bold')

    # 3) 개별 그래프 설정 및 화면 출력 
    for ax in g.axes.flatten():
        ax.set_axisbelow(True)      # 격자를 그래프 뒤로 이동
        ax.grid(True, alpha=0.5)    # 격자 추가 
    
    show(save_path)                 # 화면 출력 


def _draw_ci(ax, interval, color, ymax):
    """
    kdeplot 에서 단일 신뢰구간(하한~상한)을 지정한 색상으로 그리는 보조함수 

    Args : 
        ax : 그래프를 그릴 Axes 객체
        interval : (신뢰구간 하한, 신뢰구간 상한) 튜플 
        color : 신뢰구간 선/텍스트/영역에 적용할 색상 
        ymax : 영역 채우기와 텍스트 위치 계산에 사용할 y축 상한 
    """

    cmin, cmax = interval 

    # 신뢰구간 범위에 대한 세로 직선 그리기 (cmin ~ cmax)
    ax.axvline(cmin, linestyle=':', color=color, linewidth=0.5)
    ax.axvline(cmax, linestyle=':', color=color, linewidth=0.5)

    # 신뢰구간 범위에 대한 텍스트 추가 
    ax.text(cmin, ymax*0.9, f'{cmin:.2f}', color=color, fontsize=11, ha='right')
    ax.text(cmax, ymax*0.9, f'{cmax:.2f}', color=color, fontsize=11, ha='left')

    # 신뢰구간 범위에 대한 영역 채우기 (cmin ~ cmax)
    ax.fill_between([cmin, cmax], 0, ymax, alpha=0.1, color=color)


def pointplot(data=None, x=None, y=None, hue=None, order=None, hue_order=None,
              estimator ="mean", errorbar="se", capsize=0.1,dodge = False, markers="o", 
              linestyles="-", palette=None, color=None, title=None, xlabel=None, ylabel=None,
              legend_title=None, width=1280, height=640, save_path=None, ax=None):
    """
    점 그래프(pointplot)를 그린다. 범주별 추정치(기본: 평균)와 오차범위를 점과 선으로 표현하므로 
    분산분석의 상호작용 플롯(interaction plot) 등에 활용한다. 

    Args : 
        data : 시각화할 데이터 
        x : x축 범주 컬럼명 
        y : y축 값 컬럼명 
        hue : 범주 구분 컬럼명 
        order : x축 표시 순서 
        hue_order : hue 범주의 표시 순서 
        estimator : 각 범주의 대표값 추정 방법 ( 기본 'mean' )
        errorbar : 오차범위 표현 방식 (예: 'se', 'sd', ('ci', 95))
        capsize : 오차범위 막대 끝 모자의 크기
        dodge : hue별 점이 겹치지 않도록 좌우로 분리할지 여부 또는 분리 폭
        markers : 점 마커 모양 
        linestyles : 선 스타일 
        palette : 색상 팔레트 이름
        color : 단일 색상 (hue가 없을때 사용) 
        title : 그래프 제목 
        xlabel : x축 레이블 
        ylabel : y축 레이블 
        legend_title : 범례 제목 (지정하지 않으면 hue 컬럼명 사용)
        width : 캔버스 가로 픽셀
        height : 캔버스 세로 픽셀 
        save_path : 이미지 저장 경로 
        ax : 그래프를 그릴 Axes 객체. None이면 init 함수로 새로 생성 
    """

    # 그래프 초기화 
    fig = None
    if ax is None:
        fig, ax = init(width=width, height=height, 
                   title=title, xlabel=xlabel, ylabel=ylabel)

    # 점 그래프 그리기 
    sb.pointplot(data=data, x=x, y=y, hue=hue, order=order, hue_order=hue_order,
                 estimator=estimator, errorbar=errorbar, capsize=capsize, dodge=dodge, 
                 markers=markers, linestyles=linestyles, palette=palette, color=color, ax=ax)

    # 범례 제목 지정 (hue가 있을때) 
    if hue is not None and legend_title is not None:
        legend = ax.get_legend()
        if legend is not None: 
            legend.set_title(legend_title)

    # 그래프 표시 
    if fig is not None:
        show(save_path=save_path)
