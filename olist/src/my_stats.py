import numpy as np 
from math import sqrt 
from itertools import combinations
from IPython.display import display
from pandas import DataFrame, Series, melt, concat, crosstab
from scipy.stats import t 
from scipy.stats import normaltest, bartlett, levene
from scipy.stats import ttest_1samp, wilcoxon, ttest_rel, ttest_ind, mannwhitneyu
from scipy.stats import pearsonr, spearmanr
from scipy.stats import chisquare, chi2_contingency, fisher_exact

from statsmodels.stats.diagnostic import linear_reset
from statannotations.Annotator import Annotator

from pingouin import anova, welch_anova, pairwise_gameshowell, pairwise_tukey

from . import my_plot
from . import my_prep

from statsmodels.formula.api import ols 
from statsmodels import api as sm 
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.tools.tools import add_constant

def ci(data, column=None, clevel=0.95):
    """
    주어진 데이터에 대한 모평균의 신뢰구간을 계산하는 함수 

    Args : 
        data (Series | list | ndarray | DataFrame) : 연속형 데이터 또는 데이터 프레임 
        column (str) : data가 데이터프레임인 경우 대상 컬럼명 (기본값 : None) 
        clevel (float) : 신뢰수준 (기본값 : 0.95)

    Returns: 
        tuple : (신뢰구간 하한, 신뢰구간 상한)
    """

    # 데이터 프레임 + 컬럼명 형태로 전달된 경우 해당 컬럼만 추출
    if column is not None:
        data = data[column]

    n =len(data)        # 표본 크기 
    dof = n-1           # 자유도
    sample_mean = data.mean()   # 표본 평균 
    sample_std = data.std()     # 표본 표준편차 
    sample_std_error = sample_std / sqrt(n) # 표준오차 

    # 신뢰구간을 계산하여 리턴한다. 
    return t.interval(clevel, dof, loc=sample_mean, scale=sample_std_error)

def test_assumptions(data, columns=None, alpha=0.05, center="median"):
    """
    가설 검정의 가정 ( 정규성, 등분산성)을 일괄적으로 검정하여 결과표를 반환하는 함수 

    각 변수에 대해 정규성 검정(normaltest)을 수행하고, 변수가 두 개 이상인 경우 등분산성 검정을 수행한다.
    이때 모든 변수가 정규성을 충족하면 Bartlett 검정을,
    하나라도 충족하지 못하면 Levene검정을 선택적으로 사용한다. 

    Args:   
        data (DataFrame) : 검정대상이 되는 데이터프레임
        columns (list) : 검정에 사용할 컬럼명 목록 (기본값: None -> 수치형 컬럼 전체)
        alpha (float) : 유의수준 (기본값 : 0.05)
        center (str) : Levene 검정시 사용할 중심 경향값 (기본값: "median")

    Returns : 
        DataFrame : field를 인덱스로 하는 검정 결과표
                    (test, statistic, p-value, result 컬럼 포함)
    """
    # 검정에 사용할 컬럼 결정 ( 지정하지 않으면 수치형 컬럼 전체 사용) 
    if columns is None: 
        columns = data.select_dtypes(include="number").columns.tolist()

    # 하나의 컬럼명이 문자열로 전달된 경우 리스트로 감싸준다. 
    if type(columns) == str: 
        columns = [columns]

    report = [] # 결과를 누적할 리스트 
    normal_dist = True # 모든 변수가 정규성을 충족하는지 여부 

    # 각 변수에 대한 정규성 검정
    for c in columns: 
        s, p = normaltest(data[c].dropna())
        normalize = p >= alpha

        report.append({
            "field" : c, 
            "test" : "normaltest", 
            "statistic" : s, 
            "p-value" : p, 
            "result" : normalize
        })

        normal_dist = normal_dist and normalize

    # 변수가 두 개 이상인 경우 등분산성 검정 
    if len(columns) > 1 : 
        # 각 컬럼을 실수형으로 변환하여 리스트로 추출 (Bartlett은 실수형 필요)
        samples = [data[c].dropna().astype("float") for c in columns]

        if normal_dist : # 모든 변수가 정규성을 충족 -> Bartlett 검정 
            name = "Bartlett"
            s, p = bartlett(*samples)

        else :          # 하나라도 정규성을 충족하지 못함 -> Levene 검정
            name = "Levene"
            s, p = levene(*samples, center=center)

        report.append({
            "field" : name, 
            "test" : "equal_var", 
            "statistic" : s, 
            "p-value" : p, 
            "result" : p >= alpha 
        })


    #  결과표 리턴 
    return DataFrame(report).set_index("field")

def test_1sample(data, column, popmean=0, alpha=0.05): 
    """
    한 집단의 평균이 기준값(popmean)과 같은지 검정하는 함수 

    정규성 충족시 일표본 t검정, 미충족시 Wilcoxon 부호순위 검정을 수행하며,
    양측 / 좌측단측 / 우측단측 세가지 대립가설을 일괄 검정한다. 

    Args : 
        data (DataFrame) : 검정 대상 데이터 프레임 
        column (str) : 검정할 연속형 컬럼명 
        popmean (float) : 비교 기준이 되는 모평균 μ0 (기본값: 0)
        alpha (float) : 유의수준 (기본값 : 0.05)

    Returns : 
        DataFrame : 대립가설(alternative)별 검정/통계량/p-value 유의성 결과표
                    ( two-sided / less/ greater 3행 )
    """

    # 대상 컬럼을 결측 제거하여 추출
    sample = data[[column]].dropna()

    # test_assumptions로 정규성 검정 (단일 컬럼이라 등분산성은 수행되지 않음)
    report = test_assumptions(sample, columns=column, alpha=alpha)

    # 정규성 충족 여부 추출
    is_normal = bool(report.loc[column, "result"])

    # 정규성 충족 여부에 따라 적용할 컬럼 이름 결정 
    test_name = "One-sample t-test" if is_normal else "Wilcoxon signed-rank"

    # 대립가설 방향별 가설을 부등식으로 표현 (H0:귀무가설, H1:대립가설, μ: 모평균)
    hypotheses = {
        "two-sided" : {"H0": f"μ = {popmean}", "H1":f"μ ≠ {popmean}"}, 
        "less" : {"H0": f"μ ≥ {popmean}", "H1":f"μ < {popmean}"}, 
        "greater" : {"H0": f"μ ≤ {popmean}", "H1":f"μ > {popmean}"}, 
    }

    rows = [] 
    # 양측/ 좌측단측/ 우측단측을 일괄 검정 
    for alt in ("two-sided", "less", "greater"): 
        if is_normal: # 정규성 충족 -> 일표본 t검정 
            stat, p = ttest_1samp(sample[column], popmean, alternative=alt)
        else: 
            stat, p = wilcoxon(sample[column] - popmean, alternative=alt)

        # p < alpha 이면 통계적으로 유의 (귀무가설 기각)
        significant = p < alpha 

        rows.append({
            "test": test_name,
            "alternative": alt, 
            "statistic" : round(float(stat), 4), 
            "p-value": round(float(p), 4), 
            "significant" : significant, 
            # 유의하면 대립가설(H1)채택 , 아니면 귀무가설(H0) 유지 
            "result": hypotheses[alt]["H1"] if significant else hypotheses[alt]["H0"]
        })

    # 세 방향 결과를 표로 정리하여 반환 
    return DataFrame(rows).set_index(["test", "alternative"])

def test_paired(data, before, after, alpha=0.05, 
                plot=True, palette=None, title=None, xlabel=None, ylabel=None,
                width=1280, height=640, save_path=None): 
    """
    짝지어진 두 측정값(전/후)의 차이가 있는지 검정하는 함수 (wide 형식)

    차이값 d = after - before의 정규성 충족시 대응표본 t검정, 
    미충족 시 Wilcoxon 부호순위 검정을 수행하며,
    양측/ 좌측단측/ 우측단측 세가지 대립가설을 일괄 검정한다. 

    Args : 
        data (DataFrame) : 검정 대상 데이터프레임 
        before (str) : 사전 측정값 컬럼명 
        after (str) : 사후 측정값 컬럼명 
        alpha (float) : 유의수준 (기본값: 0.05)
        plot (bool) : 결과를 시각화할지 여부 (기본값 : True)
        palette (str or list, optional) : 색상 팔레트 
        title (str, optional) : 그래프 제목 
        xlabel (str, optional) : x축 라벨 
        ylabel (str, optional) : y축 라벨 
        width (int, optional) : 그래프 가로 크기 
        height (int, optional) : 그래프 세로 크기 
        save_path (str, optional) : 그래프 저장 경로 

    Returns :
        DataFrame : 대립가설 (alternative)별 검정/통계량/p-value 유의성 결과표 
    """

    # 검정을 위한 전처리 및 변수 준비 
    # 같은 행끼리 짝지어야 하므로 두 컬럼을 함께 결측 행 제거 
    paired = data[[before, after]].dropna()

    # 차이값 d = after - before 를 계산 
    d = (paired[after] - paired[before]).rename("diff")

    # test_assumptions로 차이값의 정규성만 검정 (단일 컬럼) 
    report = test_assumptions(DataFrame({"diff": d}), columns=["diff"], alpha=alpha)

    # 차이값의 정규성 충족 여부 
    is_normal = bool(report.loc["diff","result"])

    # 정규성 충족 여부에 따라 적용할 검정 이름 결정 
    test_name = "Paired t-test" if is_normal else "Wilcoxon signed-rank test"

    # 대립가설 방향별 가설을 부등식으로 표현 ( H0: 귀무가설, H1: 대립가설)
    hypotheses = {
        "two-sided" : {"H0": f"{after} = {before}", "H1": f"{after} =/= {before}"}, 
        "less" : {"H0": f"{after} >= {before}", "H1": f"{after} < {before}"}, 
        "greater": {"H0": f"{after} <= {before}", "H1": f"{after} > {before}"}
    }

    rows = []
    # 양측 / 좌측단측/ 우측단측을 일괄 검정 ( 항상 after, before 순) 
    for alt in ("two-sided", "less", "greater"): 
        if is_normal: # 정규성 충족 -> 대응표본 t검정 
            stat, p = ttest_rel(paired[after], paired[before], alternative=alt)
        else: 
            stat, p = wilcoxon(paired[after], paired[before], alternative=alt)

        significant = p < alpha # p < alpha 이면 통계적으로 유의 (귀무가설 기각) 

        rows.append({
            "test" : test_name, 
            "alternative" : alt, 
            "statistic": round(float(stat), 4), 
            "p-value" : round(float(p), 4), 
            "significant" : significant, 
            # 유의하면 대립가설(H1) 채택, 아니면 귀무가설(H0) 유지 
            "result": hypotheses[alt]["H1"] if significant else hypotheses[alt]["H0"]
        })

    # 세 방향 결과를 표로 정리하여 반환 -- > 함수 맨 마지막에 return문 필요 
    result_df = DataFrame(rows).set_index(["test", "alternative"])

    # 시각화 옵션이 True인 경우, 시각화 수행 
    if plot : 
        melt_df = melt(paired, value_vars=[before, after], 
                    var_name="group", value_name="value")
        fig, ax = my_plot.init(title=title, width=width, height=height, xlabel=xlabel,
                            ylabel=ylabel)
        my_plot.boxplot(data=melt_df, x="group", y="value", 
                        hue="group", palette=palette, ax=ax)
        
        # 독립 표본 T검정 결과를 시각화에 추가 
        annotator = Annotator (data=melt_df, 
                            x='group', 
                            y='value', 
                            pairs=[(before, after)], 
                            ax=ax)
        # 가설검정 알고리즘 종류 
        annotator.configure(test='t-test_paired' if is_normal else 'Wilcoxon')
        annotator.apply_and_annotate()
        my_plot.show()

    return result_df
        
def test_independent(data, group1, group2, alpha=0.05, plot=True, palette=None, 
                     title=None, xlabel=None, ylabel=None, width=1280, height=640, save_path=None):
    
    """
    두 집단 모두 정규성 충족시 등분산성에 따라 Student/ Welch t검정, 
    하나라도 미충족시 Mann-Whitney U 검정을 수행하며,
    양측/ 좌측단측/ 우측단측 세가지 대립가설을 일괄 검정한다. 

    Args : 
        data (DataFrame) : 검정 대상 데이터 프레임 
        group1 (str) : 첫번째 집단의 측정값 컬럼명 
        group2 (str) : 두번째 집단의 측정값 컬럼명 
        alpha (float) : 유의수준 (기본값 : 0.05) 
        plot (bool) : 결과를 시각화할지 여부 (기본값: True) 
        palette (str or list) : 색상 팔레트 (기본값: None) 
        title (str) : 그래프 제목 (기본값: None)
        xlabel (str) : x축 라벨 (기본값 : None)
        ylabel (str) : y축 라벨 (기본값 : None)
        width (int) : 그래프 너비 (기본값: 1280)
        height (int) : 그래프 높이 (기본값 : 640) 
        save_path (str) : 그래프 저장 경로(기본값: None)

    Returns : 
        DataFrmae : 대립가설(alternative)별 검정/통계량/p-value/유의성 결과표 
    """

    # 두 집단의 컬럼명을 수준(level)으로 사용 
    lv = [group1, group2]

    # 각 집단 컬럼을 분리하고 결측 제거 (독립표본이므로 컬럼별로 따로 제거)
    a = data[group1].dropna()
    b = data[group2].dropna()

    # 두 집단을 컬럼으로 묶어 정규성 + 등분산성을 동시에 검정 (길이가 달라도 무방)
    paired = concat([a.reset_index(drop=True), b.reset_index(drop=True)], axis=1)
    paired.columns = [str(lv[0]), str(lv[1])]
    report = test_assumptions(paired, columns=list(paired.columns), alpha=alpha)

    # 두 집단 모두 정규성을 충족하는지 확인 
    group1_normal = bool(report.loc[str(lv[0]), "result"])
    group2_normal = bool(report.loc[str(lv[1]), "result"])
    both_normal = group1_normal and group2_normal

    # 등분산성 충족 여부 추출
    equal_var = bool(report[report["test"] == "equal_var"]["result"].iloc[0])

    # 가정 검정 결과에 따라 적용할 검정 이름 결정 
    if not both_normal: 
        test_name = "Mann-Whitney U test"   # 정규성 미충족 -> 비모수 검정
    elif equal_var :
        test_name = "Student t-test"        # 정규성 충족 + 등분산 
    else: 
        test_name = "Welch t-test"          # 정규성 충족 + 이분산 

    # 대립가설 방향별 가설을 부등식으로 표현 
    # (H0:귀무가설, H1:대립가설, A=lv[0] / B=lv[1])    
    hypotheses = {
        "two-sided" : {"H0": f"{lv[0]} = {lv[1]}", "H1":f"{lv[0]} =/= {lv[1]}"}, 
        "less" : {"H0": f"{lv[0]} >= {lv[1]}", "H1":f"{lv[0]} < {lv[1]}"}, 
        "greater" : {"H0": f"{lv[0]} <= {lv[1]}", "H1":f"{lv[0]} > {lv[1]}"}, 
    }                  

    rows = [] 
    # 양측/ 좌측단측/ 우측단측을 일괄 검정 
    for alt in ("two-sided", "less", "greater"): 
        # 적용 검정에 맞춰 대립가설 방향을 전달하여 검정수행 
        if test_name == "Mann-Whitney U test": 
            stat, p = mannwhitneyu(a, b, alternative=alt)
        elif test_name == "Student t-test":
            stat, p = ttest_ind(a, b, equal_var=True, alternative=alt)
        else: 
            stat, p = ttest_ind(a, b, equal_var=False, alternative=alt)

        # p < alpha 이면 통계적으로 유의(귀무가설 기각) 
        significant = p < alpha 

        rows.append({
            "test": test_name, 
            "alternative": alt, 
            "statistic": round(float(stat), 4), 
            "p-value": round(float(p), 4), 
            "significant": significant, 
            # 유의하면 대립가설(H1) 채택, 아니면 귀무가설(H0) 유지 
            "result": hypotheses[alt]["H1"] if significant else hypotheses[alt]["H0"]

        })

    # 세 방향 결과를 표로 정리하여 반환 
    result_df = DataFrame(rows).set_index(["test", "alternative"])

    # 시각화 옵션이 True인 경우, 시각화 수행 
    if plot : 
        # wide 형식을 long 형식으로 변환하여 그룹별 박스플롯 작성 
        melt_df = melt(data, value_vars=[group1, group2], 
                       var_name="group", value_name="value")
        
        fig, ax = my_plot.init(title=title, width=width, height=height, 
                               xlabel=xlabel, ylabel=ylabel, )
        my_plot.boxplot(data=melt_df, x="group", y="value", hue="group", palette=palette, ax=ax)

        # 독립표본 검정 결과를 시각화에 추가 
        annotator = Annotator(data=melt_df, x="group", y="value", # 데이터프레임, x축, y축 변수 지정
                              pairs=[(lv[0], lv[1])], # 비교할 그룹 쌍
                              ax = ax)  # 그래프 축 
        
        if test_name == "Mann-Whitney U test": # 가설검정 알고리즘 종류 (적용된 검정에 맞춰 지정)
            annot_test = "Mann-Whitney"
        elif test_name == "Student t-test":
            annot_test = "t-test_ind"
        else: 
            annot_test = "t-test_welch"
        
        annotator.configure(test=annot_test)
        annotator.apply_and_annotate()
        my_plot.show()

    return result_df

def anova_oneway(data, y, between, alpha=0.05): 
    """
    일원분산분석 ( One-way ANOVA ) 

    Args : 
        data (DataFrame) : 검정 대상 데이터 프레임 (long형식)
        y ( str ) : 종속변수(연속형) 컬럼명
        between (str) : 집단을 구분하는 독립변수(명목형) 컬럼명 
        alpha (float) : 유의수준 (기본값 : 0.05)

    Returns :
        DataFrame : pingouin의 분산분석 결과표(One-way ANOVA 또는 Welch-ANOVA)에 
                    설명용 컬럼을 덧붙인 결과표.
                    - test : 사용한 검정 이름 
                    - effect_size : np2 기준 효과크기 해석 라벨(큼/중간/작음/미미함)
    """

    # 분석에 사용할 두 컬럼만 추출하고 결측 행 제거 
    df = data[[y, between]].dropna()

    # 집단별 종속변수 값을 wide 형태(집단=컬럼)로 모아 가정 검정에 전달 
    wide = my_prep.long2wide(df, hue=between, values=y)
    assumption = test_assumptions(wide, columns=list(wide.columns), alpha=alpha)

    # 등분산성 충족 여부 추출( 정규성은 robust 가정에 따라 분기에 사용하지 않음)
    equal_var = bool(assumption[assumption["test"] == "equal_var"]["result"].iloc[0])   

    # 등분산성 여부에 따라 일반 ANOVA / Welch-ANOVA 선택 
    if equal_var: 
        anova_name = "anova"
        aov = anova(data=df, dv=y, between=between)
    else: 
        anova_name = "welch_anova"
        aov = welch_anova(data=df, dv=y, between=between)

    # 어떤 검정을 사용했는지 식별할 수 있도록 맨 앞에 test 컬럼 추가 
    aov.insert(0, "test", anova_name)

    # --- 효과크기 해석 컬럼 추가 --- 
    # pingouin이 제공하는 Cohen의 효과크기 기준표로 해석하여 라벨 부여
    #     >= 0.14 ->큼,   >=0.06 -> 중간,   >=0.01 -> 작음, 그 미만 -> 미미함
    conditions = [
        aov["np2"] >=0.14, 
        aov["np2"] >=0.06, 
        aov["np2"] >=0.01, 
    ]
    labels=["Large", "Medium", "Small"]
    aov["effect_size"] = np.select(conditions, labels, default="Negligible")
        
    return aov

# 사후검정 함수 정의 LAB07-7 사후검정
def posthoc_oneway(data, y, between, alpha=0.05, plot=True,summary=True, palette=None, 
                   title=None, xlabel=None, ylabel=None, width=1280, 
                   height=640, save_path=None): 
    """
    일원분산분석( One-way ANOVA )의 사후검정을 수행하는 함수 

    Args: 
        data ( DataFrame ) : 검정대상 데이터 프레임 (long 형식)
        y ( str ) : 종속변수 (연속형) 컬럼명
        between (str) : 집단을 구분하는 독립변수(명목형) 컬럼명 
        alpha (float) : 유의수준 (기본값: 0.05) 
        plot (bool) : 결과를 시각화할지 여부 ( 기본값: True) 
        palette (str or list) : 색상 팔레트 (기본값: None) 
        title (str) : 그래프 제목 (기본값: None) 
        xlabel (str) : x축 라벨 (기본값: None) 
        ylabel (str) : y축 라벨 (기본값: None) 
        width (int) : 그래프 너비 (기본값: 1280) 
        height (int) : 그래프 높이 (기본값: 640) 
        save_path (str) : 그래프 저장 경로 (기본값: None) 

    Returns : 
        DataFrame : 그룹 쌍별 사후검정 결과표( Tukey HSD 또는 Games-Howell)

    """
    # 등분산성 가정에 따른 검정방법 선택 
    # 분석에 사용할 두 컬럼만 추출하고 결측 행 제거 
    df = data[[y, between]].dropna()

    # 집단별 종속변수 값을 wide 형태(집단=컬럼)로 모아 등분산성 가정 검정에 전달
    wide = my_prep.long2wide(df, hue=between,values=y)
    assumption = test_assumptions(wide, columns=list(wide.columns), alpha=alpha)

    # 등분산성 충족 여부 추출 
    equal_var = bool(assumption[assumption["test"] == "equal_var"]["result"].iloc[0])

    # 등분산성 여부에 따라 사후검정 방법 선택 
    if equal_var : 
        posthoc_name = "Tukey HSD"
        result = pairwise_tukey(data=df, dv=y, between=between)
        # pingouin 버전/패치에 따라 p값 컬럼명이 다를 수 있어 유연하게 선택 
        pcol = "p-tukey" if "p-tukey" in result.columns else "p_tukey"

    else: 
        posthoc_name = "Games-Howell"
        result = pairwise_gameshowell(data=df, dv=y, between=between)
        pcol = "pval"
    
    # 시각화 준비 및 검정 결과표 보정 
    # 그래프의 x축 순서 (그룹순서) 
    order = sorted(df[between].unique())

    # 비교 대상 그룹 쌍과 그에 대응하는 p값 추출
    pairs = list(zip(result["A"], result["B"]))
    pvalues = list(result[pcol])

    # 어떤 사후검정을 사용했는지 식별할 수 있도록 맨 앞에 test 컬럼 추가
    result.insert(0, "test", posthoc_name)
    # p값이 유의수준 미만이면 통계적으로 유의(귀무가설 기각) 
    result["significant"] = result[pcol] < alpha 

    # 효과크기 해석 컬럼 추가 
    # --- 효과크기 해석 컬럼 추가 --- 
    # hedges(Hedges' g)는 두 집단 평균차에 대한 표준화 효과크기로, 
    # Cohen의 d 기준표를 따라 절댓값으로 해석한다. 
    #   >=0.8 -> 큼 ,     >=0.5 -> 중간,    >= 0.2 -> 작음, 그 미만 -> 미미함 
    # 부호는 비교 방향(A-B)을 의미하므로 크기 해석에는 절댓값을 사용한다.
    abs_hedges = result["hedges"].abs()
    conditions = [
        abs_hedges >= 0.8, 
        abs_hedges >= 0.5, 
        abs_hedges >= 0.2, 
    ]
    labels = ["Large", "Medium", "Small"]
    result["effect_size"] = np.select(conditions, labels, default="Negligible")

    # 시각화 옵션이 True인 경우, 시각화 수행 
    if plot: 
        fig, ax = my_plot.init(title=title, width=width, height=height, xlabel=xlabel, ylabel=ylabel)
        my_plot.boxplot(data=df, x=between, y=y, hue=between, palette=palette, 
                        order=order, ax=ax)
        
        # 사후검정 결과(그룹 쌍별 p값)를 시각화에 추가 
        annotator = Annotator(data=df, x=between, y=y, # 데이터프레임, x축, y축 변수 지정
                            pairs=pairs, # 비교할 그룹 쌍 
                            order=order, # 그룹(x축) 순서 
                            ax=ax) # 그래프 축 
        
        # 검정을 새로 수행하지 않고, 앞서 구한 p값을 그대로 주입하여 주석 표시 
        annotator.configure(text_format="star", loc="inside")
        annotator.set_pvalues(pvalues)
        annotator.annotate()
        my_plot.show()
    
    # --- 6) 결과 요약 출력 --- 
    if summary:
        print("비교한 조합 쌍: {0}개".format(len(result)))
        print("유의한 쌍: {0}개".format(int(result["significant"].sum())))

        big = result.loc[result["diff"].abs().idxmax()]
        print("평균 차이가 가장 큰 쌍: ({0}) vs ({1})"
              "-> 차이 {2:.3f}, 효과크기 {3}, p-value {4:.3f}".format(
                  big["A"], big["B"], abs(big["diff"]), big["effect_size"], big["pval"]))
        
        sm = result.loc[result["diff"].abs().idxmin()]  
        print("평균 차이가 가장 작은 쌍: ({0}) vs ({1})"
              "-> 차이 {2:.3f}, 효과크기 {3}, p-value {4:.3f}".format(
                  sm["A"], sm["B"], abs(sm["diff"]), sm["effect_size"], sm["pval"]))

    return result

def anova_twoway(data, y, between, alpha=0.05, order=None, plot=True, palette=None, 
                 title=None, ylabel=None, width=640, height=480, save_path=None): 
    """
    이원분산분석 (Two-way ANOVA) 
        - 등분산 충족 : 일반 이원분산분석 (pingouin.anova)
        - 등분산 미충족 : Type - II ANOVA

    Args : 
        data (DataFrame) : 검정 대상 데이터 프레임 (long 형식) 
        y (str) : 종속변수(연속형) 컬럼명 
        between (list) : 집단을 구분하는 두 개의 독립변수(명목형) 컬렴명 리스트 
        alpha (float) : 유의수준 (기본값 : 0.05) 
        order (list) : 두 독립변수의 수준 표시 순서를 담은 리스트의 리스트 (기본값 : None) 
            예 : [['low', 'med', 'high'], ['weekly', 'daily']]
        plot (bool) : 상호작용 플롯을 시각화할지 여부 (기본값 : None) 
        title (str) : 그래프 전체 제목 (기본값 : None) 
        ylabel (str) : y축 라벨 (기본값 : None이면 "평균 {y}")
        width (int) : 서브플롯 한 칸의 너비 (기본값 : 640) 
        height (int) : 서브플롯 한 칸의 높이 (기본값 : 480) 
        save_path (str) : 그래프 저장 경로 (기본값: None) 

    Returns: 
        DataFrame : 이원분산분석 결과표에 설명용 컬럼을 덧붙인 결과표 
    """

    # --- 1) 분석에 사용할 컬럼만 추출하고 결측 행 제거 ---
    df = data[[y, between[0], between[1]]].dropna()

    # --- 2) 등분산성 가정 검정 --- 
    # 두 명목형 변수의 모든 조합(셀)별 값을 wide 형태로 모아 가정 검정에 전달 
    cell = df.copy()
    cell["_cell"] = cell[between[0]].astype(str) + ", "+ cell[between[1]].astype(str)
    wide = my_prep.long2wide(cell, hue="_cell", values=y) 
    assumption = test_assumptions(wide, columns=list(wide.columns), alpha=alpha) 

    # 등분산성 충족 여부 추출 
    equal_var = bool(assumption[assumption["test"] == "equal_var"]["result"].iloc[0])

    # --- 3) 등분산 여부에 따른 이원분산분석 수행 --- 
    if equal_var: 
        # [등분산 충족] 일반 이원분산분석 
        test_name = "two-way ANOVA"
        aov = anova(data=df, dv=y, between=list(between))
        # p값이 유의수준 미만이면 통계적으로 유의(귀무가설 기각) 
        aov["significant"] = aov["p_unc"] < alpha 

    else : 
        # [등분산 미충족] 등분산을 가정하지 않는 선형모형 (HC3) 기반 Type-II ANOVA
        test_name = "Type-II ANOVA"
        # Q()로 컬럼명을 감싸 공백/특수문자가 있는 컬럼명도 안전하게 처리 
        formula = "Q('{0}') ~ C(Q('{1}')) * C(Q('{2}'))".format(y, between[0], between[1])
        model = ols(formula, data=df).fit(cov_type="HC3")
        aov = sm.stats.anova_lm(model, typ=2, robust="hc3")

        # statsmodels 결과표에는 np2가 없으므로 편에타제곱을 직접 계산한다. 
        #   np2 = SS_effect / (SS_effect + SS_residual)
        ss_resid = aov.loc["Residual", "sum_sq"]
        aov["np2"] = aov["sum_sq"] / (aov["sum_sq"] + ss_resid)
        aov.loc["Residual", "np2"] = np.nan 

        # 인덱스에 담긴 효과명을 Source 컬럼으로 변환 
        aov = aov.reset_index().rename(columns= {"index": "Source"})
        # statsmodels가 만든 효과명 (C(Q('Water')) : C(Q('sun')) 등 )을 
        # pingouin 결과와 동일한 형태 (water * sun)로 정리한다. 
        aov["Source"] = (aov["Source"].str.replace("C(Q('", "", regex=False)
                                      .str.replace("'))", "", regex=False)
                                      .str.replace(":", "*", regex=False)) 
        # p값이 유의수준 미만이면 통계적으로 유의(귀무가설 기각) 
        aov["significant"] = aov["PR(>F)"] < alpha 

    # --- 4) 결과표 가공 ( 검정명, 효과크기 컬럼 추가 ) 
    # 어떤 검정을 사용했는지 식별할 수 있도록 맨 앞에 test 컬럼 추가 
    aov.insert(0, "test", test_name)

    # 편에타제곱(np2)을 Cohen의 기준표로 해석한다. 
    # >= 0.14 -> 큼 /    >=0.06 -> 중간 / >=0.01 -> 작음 / 그 미만 -> 미미함 
    conditions = [
        aov["np2"] >= 0.14, 
        aov["np2"] >= 0.06, 
        aov["np2"] >= 0.01, 
    ]
    labels = ["Large", "Medium", "Small"]
    aov["effect_size"] = np.select(conditions, labels, default="Negligible")
    # np2가 없는 행(잔차 등)은 효과크기 해석 대상이 아니므로 표시를 비운다. 
    aov.loc[aov["np2"].isna(), "effect_size"] = "-"
    
    # --- 5) 시각화 및 결과 반환 --- 
    if plot : 
        # 5-1) 각 요인의 수준 표시 순서 결정 
        # order가 없으면 Categorical 범주 순서를, 그것도 아니면 데이터 등장 순서를 따른다. 
        if order is None: 
            orders = [] # 두 요인 각각의 수준 순서를 담은 리스트 

            for c in between: 
                if hasattr(df[c], "cat"): 
                    # Categorical 타입이면 미리 지정된 범주 순서를 그대로 사용 
                    levels = list(df[c].cat.categories)
                else: 
                    # 그 외에는 데이터에 등장한 순서를 사용
                    levels = list(df[c].unique())

                orders.append(levels)
        else: 
            # order가 주어지면 그대로 사용 (between 과 같은 순서로 대응) 
            orders = list(order) 

        if ylabel is None : 
            ylabel = "평균 {0}".format(y) 

        # 5-2) 두 요인의 역할(x축/선)을 서로 바꾼 두개의 상호작용 플롯을 나란히 그린다. 
        # (title은 전체 제목 (suptitle)이며, 지정하지 않으면 서브플롯별 제목만 표시된다. )
        fig, ax = my_plot.init(title=title, width=width, height=height, rows=1, cols=2)

        for i in range(2) : 
            # 한 요인은 x축, 나머지 요인은 선(hue)으로 역할을 바꿔가며 그린다. 
            x_field, hue_field = between[i], between[1-i]
            x_order, hue_order = orders[i], orders[1-i]

            # 각 조합의 평균(점)과 표준오차(오차막대)를 선으로 이어 평균 프로파일을 그린다. 
            my_plot.pointplot(data=df, x=x_field, y=y, hue=hue_field, 
                              order=x_order, hue_order=hue_order, 
                              errorbar="se", capsize=0.1, palette=palette, 
                              legend_title=hue_field, ax=ax[i])
            
            # ax를 직접 전달한 경우 my_plot이 제목과 축 라벨을 설정하지 않으므로 직접 지정한다.
            ax[i].set_title("{0}에 따른 {1}별 평균 {2}".format(x_field, hue_field, y), 
                            fontsize=15, pad=10)
            ax[i].set_xlabel(x_field, fontsize=12)
            ax[i].set_ylabel(ylabel, fontsize=12)
        my_plot.show(save_path=save_path)

    return aov 

# 사후검정 함수 정의 
def posthoc_twoway(data, y, between, alpha=0.05, plot=True, summary=True, 
                   palette=None, title=None, xlabel=None, ylabel=None, 
                   width=1280, height=640, save_path=None): 
    """
    이원분산분석(Two-way ANOVA)의 사후검정을 수행하는 함수 
        - 등분산 충족 : Tukey HSD 
        - 등분산 미충족 : Games-Howell 

    Args : 
        data (DataFrame) : 검정 대상 데이터 프레임 (long 형식) 
        y (str) : 종속변수(연속형) 컬럼명 
        between (list) : 집단을 구분하는 두 개의 독립변수(명목형) 컬렴명 리스트 
        alpha (float) : 유의수준 (기본값 : 0.05) 
        plot (bool) : 상호작용 플롯을 시각화할지 여부 (기본값 : True)
        summary (bool) : 결과 요약 (비교쌍 수, 유의한 쌍 수, 평균차가 가장 큰/작은 쌍, 
                                    첫번째 요인의 수준별 유의한 쌍)을 출력할지 여부 (기본값: True)
        palette (str or list) : 색상 팔레트 (기본값 : None) 
        title (str) : 그래프 제목 (기본값 : None 이면 "조합(셀)별 {y}분포")
        xlabel (str) : x축 라벨 (기본값:None이면 "조합 ({between[0]}, {between[1]})) 
        ylabel (str) : y축 라벨 (기본값 : None이면 y)
        width (int) : 그래프 너비 (기본값 : 1280) 
        height (int) : 그래프 높이 (기본값 : 640) 
        save_path (str) : 그래프 저장 경로 (기본값: None) 

    Returns: 
        DataFrame : 조합(셀) 집단 쌍별 사후검정 결과표( Tukey HSD 또는 Games-Howell)
    """        


    # --- 1) 분석에 사용할 컬럼만 추출하고 결측 행 제거 ---
    df = data[[y, between[0], between[1]]].dropna().copy()
    
    # --- 2) 두 명목형 변수를 결합하여 조합(셀) 단위의 집단 컬럼 생성 ---
    group = "{0} * {1}".format(between[0], between[1])
    df[group] = df[between[0]].astype(str) + ", " + df[between[1]].astype(str)

    # --- 3) 등분산성 가정 검정 ---
    # 조합별 종속변수 값을 wide 형태로 모아 등분산성 가정 검정에 전달 
    wide = my_prep.long2wide(df, hue=group, values=y)
    assump = test_assumptions(wide, columns=list(wide.columns), alpha=alpha)

    # 등분산성 충족 여부 추출
    equal_var = bool(assump[assump["test"] == "equal_var"]["result"].iloc[0])

    # --- 4) 등분산성 여부에 따른 사후검정 수행 ---
    if equal_var : 
        posthoc_name = "Tukey HSD"
        result = pairwise_tukey(data=df, dv=y, between=group) 
        # p값 컬럼명을 검정 종류와 무관하게 'pval'로 통일 
        # (pingouin 버전/패치에 따라 'p-tukey' 또는 'p_tukey'로 나올 수 있다.)
        pcol = "p-tukey" if "p-tukey" in result.columns else "p_tukey"
        result.rename(columns={pcol: "pval"}, inplace=True)
    else : 
        posthoc_name = "Games-Howell"
        result = pairwise_gameshowell(data=df, dv=y, between=group)

    # --- 5) 결과표 가공 (검정명, 유의성, 효과크기, 정렬) ---
    # 어떤 사후 검정을 사용햇는지 식별할 수 있도록 맨 앞에 test 컬럼 추가 
    result.insert(0, "test", posthoc_name)
    # p값이 유의수준 미만이면 통계적으로 유의(귀무가설 기각) 
    result["significant"] = result["pval"] < alpha

    # hedges는 두 집단 평균차에 대한 표준화 효과크기로, 
    # Cohen의 d 기준표를 따라 절댓값으로 해석한다. 
    # >=0.8 -> 큼 / >=0.5 -> 중간 / >=0.2 -> 작음 / 그 미만 -> 미미함 
    abs_hedges = result["hedges"].abs()
    conditions = [
        abs_hedges >= 0.8, 
        abs_hedges >= 0.5, 
        abs_hedges >= 0.2, 
    ]
    labels = ["Large", "Medium", "Small"]
    result["effect_size"] = np.select(conditions, labels, default="Negligible")
    
    # --- 6) 비교쌍( A, B ) 기준으로 정렬 ---
    result.sort_values(["A", "B"], inplace=True)

    # --- 7) 시각화 ( 조합별 상자그림 ) 및 결과 반환 ---
    if plot:
        # 평균이 큰 조합부터 왼쪽에 오도록 x축 순서를 정한다. 
        order = (df[[group, y]].groupby(group).mean().
                 sort_values(y, ascending=False).index.tolist())
        
        if title is None: 
            title = "조합(셀)별 {0} 분포".format(y) 
        if xlabel is None:
            xlabel = "조합 ({0}, {1})".format(between[0], between[1])
        if ylabel is None: 
            ylabel = y 
        
        my_plot.boxplot(data=df, x=group, y=y, order=order, palette=palette, 
                        title=title, xlabel=xlabel, ylabel=ylabel, 
                        width=width, height=height, save_path=save_path)
    # --- 8) 결과 요약 출력 ---
    if summary: 
        # 조합 이름은 "{between[0]} 수준, {between[1]}수준" 형태이므로 
        # 앞부분만 떼어내면 각 비교쌍이 어느 첫번째 요인 수준에 속하는지 알 수 있다. 
        a_level = result["A"].str.split(",").str[0]
        b_level = result["B"].str.split(",").str[0]
        print("비교한 조합 쌍: {0}개".format(len(result)))
        print("유의한 쌍 : {0}개".format(int(result["significant"].sum()))) 

        big = result.loc[result["diff"].abs().idxmax()]
        print("평균 차이가 가장 큰 쌍 :  ({0}) vs ({1})"
              "-> 차이 {2:.3f}, 효과크기 {3}, p-value {4:.3f}".format(
                  big["A"], big["B"], abs(big["diff"]), big["effect_size"], big["pval"]))
        
        sm = result.loc[result["diff"].abs().idxmin()]
        print("평균 차이가 가장 작은 쌍: ({0}) vs ({1})"
              "-> 차이 {2:.3f}, 효과크기 {3}, p-value {4:.3f}".format(
                  sm['A'], sm["B"], abs(sm["diff"]), sm["effect_size"], sm["pval"]))
        
        # 첫번째 요인의 수준을 고정한 채 두번째 요인끼리만 비교한 상을 따로 살핀다.
        # (상호작용이 있는 경우, 수준마다 유의한 쌍의 수가 다르게 나타난다)
        for lv in df[between[0]].unique(): 
            sub = result[(a_level == str(lv)) & (b_level == str(lv))]
            sig = sub[sub["significant"]]

            print("\n[{0}] {1}쌍 중 유의한 쌍 : {2}개".format(lv, len(sub), len(sig)))  

            if sig.empty : 
                # 이 수준에서는 두번째 요인을 무엇으로 바꿔도 차이를 확인할 수 없다. 
                print("(유의한 쌍 없음)")
            else : 
                print(sig[["A", "B", "diff", "pval","significant"]].to_string(index=False))
    return result

# 상관분석 함수 정의 
def correlation (data, x, y, alpha=0.05, plot=True, palette=None, 
                 title=None, xlabel=None, ylabel=None, width=1280,
                 height=640, save_path=None): 
    """"
    두 연속형 변수의 상관분석을 일괄 수행하는 함수 

    Args : 
        data (DataFrame) : 분석 대상 데이터 프레임
        x (str) : 첫번째 연속형 변수 컬럼명 
        y (str) : 두번째 연속형 변수 컬럼명 
        alpha (float) : 유의수준 (기본값: 0.05)
        plot (bool) : 산점도(회귀선 포함)를 시각화할지 여부 (기본값: True)
        palette (str or list) : 색상 팔레트 (기본값: None) 
        title (str) : 그래프 제목 (기본값: None)
        xlabel (str) : x축 라벨 (기본값: None) 
        ylabel (str) : y축 라벨 (기본값: None) 
        width (int) : 그래프 너비 (기본값: 1280) 
        height (int) : 그래프 높이 (기본값: 640)
        save_path (str) : 그래프 저장 경로 (기본값: None)

    Returns: 
        DataFrame: (x, y)를 인덱스로 하는 단일 행 결과표 
    """
    ### 1) 같은 행끼리 비교해야 하므로 두 컬럼을 함께 결측 행 제거  ---
    pair = data[[x, y]].dropna()
    vx, vy = pair[x], pair[y]
    
    ### 2) 정규성 검정 (test_assumptions 재사용) ---
    report = test_assumptions(pair, columns=[x, y], alpha=alpha)
    norm_x = bool(report.loc[x, "result"])
    norm_y = bool(report.loc[y, "result"])

    ### 3) 선형성 검정 (Ramsey RESET Test) ---
    # H0: 모형이 올바르게 설정됨(선형). p >= alpha이면 선형성 충족 
    X = sm.add_constant(vx)
    model = sm.OLS(vy, X).fit()
    linearity = bool(linear_reset(model, power=2, use_f=True).pvalue >= alpha)

    ### 4) 이상치(영향점) 및 왜도 점검 ---
    # IQR(사분위수) 울타리를 벗어난 행을 제외한 데이터를 별도로 만들어, 
    # 피어슨 r이 크게 바뀌면 ( >=0.1 ) '영향점'으로 판단한다.
    # (단순히 이상치가 존재하는 것과 상관계수를 왜곡하는 것은 다르다. )
    trimmed = pair.copy()
    for col in (x, y): 
        # 울타리는 항상 원본 (pair) 기준으로 계산 
        q1 = pair[col].quantile(0.25)
        q3 = pair[col].quantile(0.75)
        iqr = q3-q1 
        trimmed = trimmed[(trimmed[col] >= q1-1.5*iqr) &
                          (trimmed[col] <= q3+1.5*iqr)]
    r_full = pearsonr(vx, vy)[0]
    r_trim = pearsonr(trimmed[x], trimmed[y])[0]    
    influential = bool(abs(r_full - r_trim) >= 0.1)
    high_skew = bool(abs(vx.skew()) > 1 or abs(vy.skew()) > 1)

    
    ### 5) 가정에 따른 상관계수 선택 ---
    # 모든 가정을 충족하면 피어슨, 하나라도 위반하면 스피어만을 사용한다. 
    use_pearson = linearity and norm_x and norm_y and \
                (not influential) and (not high_skew)
    if use_pearson: 
        method = "Pearson"
        coef, p = pearsonr(vx, vy)
    else: 
        method = "Spearman"
        coef, p = spearmanr(vx, vy)

    ### 6) 상관 강도 해석 라벨---
    # |r| > 0.7 -> 강함 
    # 0.3 < |r| <=0.7 -> 중간, 
    # 0 < |r| <= 0.3 -> 약함 
    # 그외 -> 없음 
    a = abs(coef)
    if a > 0.7: strength = "Strong"
    elif a > 0.3: strength = "Moderate"
    elif a > 0 : strength = "Weak"
    else: strength = "None"

    ### 7) 가정 점검 결과와 선택된 상관계수를 단일 행 결과표로 정리 ---
    row = {
        "x" : x, 
        "y" : y, 
        "method" : method, 
        "coef" : round(float(coef), 4), 
        "p-value" : round(float(p), 4), 
        "strength" : strength, 
        "significant":bool(p<alpha), 
        "normality_x" : norm_x, 
        "normality_y" : norm_y, 
        "linearity" : linearity,
        "influential_outlier": influential, 
        "high_skew" : high_skew
    }
    result_df = DataFrame([row]).set_index(["x", "y"])

    ### 8) 시각화 ---
    # 시각화 옵션이 True인 경우, 산점도를 시각화 
    if plot: 
        my_plot.scatterplot(data=pair, x=x, y=y, palette=palette,
                            title=title, xlabel=xlabel, ylabel=ylabel, 
                            width=width, height=height, save_path=save_path)    
        
    ### 9) 결과 반환 ---
    return result_df 

# 다중 상관분석 함수 정의 
def multi_correlation(data, columns=None, alpha=0.05, plot=True, palette=None, 
                      diag_kind="kde", reg=False, title=None, 
                      width=1280, height=1024, save_path=None): 
    """
    여러 변수 쌍에 대한 상관분석을 일괄 수행하고 결과를 출력하는 함수 

    Args: 
        data (DataFrame) : 분석 대상 데이터 프레임 
        columns (list) : 분석에 사용할 컬럼명 목록 
                        ( 기본값 : None -> 수치형 컬럼 전체 )
        alpha (float) : 유의수준 (기본값: 0.05)
        plot (bool) : 산점도 행렬을 시각화할지 여부 (기본값: True)
        palette (str or list) : 색상 팔레트 (기본값 : None) 
        diag_kind (str) : 산점도 행렬 대각선 그래프 종류 'hist' 또는 'kde' (기본값: "kde")
        reg (bool) : 산점도 행렬에 회귀선 표시 여부 (기본값 : False)
        title (str) : 산점도 행렬 제목 (기본값 : None) 
        width (int) : 그래프 너비 (기본값 : 1280) 
        height (int) : 그래프 높이 (기본값: 1024)
        save_path (str) : 그래프 저장 경로 (기본값: None) 

    Returns:
        DataFrame : 변수 쌍별 상관분석 결과표 
    """

    # --- 1) 준비작업 ---
    # 분석에 사용할 컬럼 결정 ( 지정하지 않으면 수치형 컬럼 전체 사용) 
    if columns is None: 
        columns = data.select_dtypes(include="number").columns.tolist()

    # 하나의 컬럼명이 문자열로 전달된 경우 리스트로 감싸준다. 
    if type(columns) == str:
        columns = [columns]
    
    # 상관분석은 두 개 이상의 변수가 있어야 수행할 수 있다.
    if len(columns) < 2:
        raise ValueError("상관분석을 위해서는 두 개 이상의 컬럼이 필요합니다.")

    # --- 2) 변수 조합 쌍별 상관분석 ---
    # 각 컬럼 조합에 대해 correlation()을 호출하여 단일 행 결과를 세로로 누적 
    columns_pairs = list(combinations(columns, 2))
    corr_df = DataFrame() # < -- 리턴할 결과표 
    for col1, col2 in columns_pairs:
        corr = correlation(data, col1, col2, alpha=alpha, plot=False)
        corr_df = concat([corr_df, corr])

    # --- 3) 상관행렬 결과표 재배치 ---
    # 대각선(자기 자신과의 상관)은 1.0으로 초기화 
    corr_matrix = DataFrame(1.0, index=columns, columns=columns)

    # 각 변수 조합의 상관계수(coef)를 대칭이 되도록 양쪽에 채운다. 
    for (col1, col2), coef in corr_df["coef"].items(): 
        corr_matrix.loc[col1, col2] = coef 
        corr_matrix.loc[col2, col1] = coef
    
    # 배경 색상(그라데이션)을 적용한 상관행렬 출력
    display(corr_matrix.style
            .background_gradient(cmap="coolwarm", vmin=-1, vmax=1)
            .format("{:.3f}"))

    # --- 4) 산점도 행렬 시각화 ---
    if plot: 
        my_plot.pairplot(data=data[columns], palette=palette, 
                         diag_kind=diag_kind, reg=reg, title=title, 
                         width=width, height=height, save_path=save_path)

    # --- 5) 결과 반환 ---
    return corr_df 
    
# 1. VIF 계산 함수 정의 
def compute_vif(df, columns=None):
    """
    각 변수의 VIF를 statsmodels 패키지로 계산해서 반환 
    """

    # --- 1) 처리 대상 컬럼 결정 ---
    if columns is None : 
        target = df.select_dtypes(include='number')
    else: 
        # df에 존재하지 않는 컬럼이 전달되었는지 체크 
        missing = []
        for col in columns: 
            if col not in df.columns: 
                missing.append(col)
        if missing: 
            raise KeyError(f'df에 존재하지 않는 컬럼입니다: {missing}')
        
        # 원본에 데이터프레임에서 columns에 해당하는 컬럼만 추출 
        target = df[columns]

        # VIF 는 수치 행렬 연산이므로 비수치형이 섞이면 안된다. 
        non_numeric = list(target.select_dtypes(exclude='number').columns)
        if non_numeric: 
            raise TypeError(f'수치형이 아닌 컬럼은 VIF를 계산할 수 없습니다: {non_numeric}')

    # --- 2) VIF 계산 
    # 회귀모형에 절편(상수항)이 있어야 올바른 VIF가 나오므로 절편(상수항)을 추가 
    X = add_constant(target)

    # 각 변수(열)별로 VIF를 하나씩 계산해서 리스트에 담는다. 
    vif_values = []

    # 각 변수에 대해 VIF를 계산 
    for i in range(X.shape[1]): 
        # variance_inflation_factor 는 i번째 변수에 대한 VIF를 계산 
        vif_i = variance_inflation_factor(X.values, i)
        vif_values.append(vif_i)

    # 계산한 VIF 값들을 변수명과 함께 DataFrame으로 정리 
    vif = DataFrame({'VIF':vif_values}, index=X.columns)    

    # 상수항(const)은 분석 대상이 아니므로 제외하고
    # 인덱스 오름차순으로 먼저 정렬
    # 그 후 VIF 기준 내림차순으로 정렬해서 반환 
    # 단, 동점일 경우 기존 순서를 유지하도록 kind = "stable" 옵션 사용 
    vif = (vif.drop('const').sort_index()
           .sort_values(by='VIF', ascending=False, kind="stable"))
    
    return vif

def correlation_summary(corr_df, strength="Strong"): 
    """
    multi_correlation()의 결과표를 변수별 중복(다중공선성) 신호로 집계하는 함수 

    Args:
        corr_df (DataFrame): multi_correlation()이 리턴한 변수 쌍별 상관분석 결과표
        strength (str or list) : 중복으로 간주할 상관 강도 레베레
                                (기본값 : "Strong" -> |coef|>=0.7 인 쌍만 중복으로 집계)

    Returns: 
        DataFrame : 변수별 집계표 (중복이 심한 변수부터 정렬)
            - index : 변수명 
            - max-y : 상관계수 절대값이 가장 큰 상대 변수명 
            - max-coef : 그때의 상관계수 
            - count : 중복으로 집계된 쌍의 개수 (없으면 0)
            - columns : 중복으로 집계된 상대 변수명을 쉼표로 연결한 문자열 ( 없으면 "-")
    """

    # -- 1) 결과표를 양방향으로 만들기 -- 
    # corr_df는 각 쌍이 한 번만 등장하므로 (CRIM-NOX만 있고 NOX-CRIM은 없음)
    # x, y를 뒤집은 결과표를 덧붙여야 변수별 집계가 가능하다. 
    pairs = corr_df.reset_index()
    pairs = concat([pairs, pairs.rename(columns={"x":"y", "y":"x"})])

    # 상관계수의 절대값이 큰 순으로 정렬
    pairs.sort_values(by="coef", key=abs, ascending=False, inplace=True)


    # -- 2) 변수별 최강 상대 ---
    # 절대값이 큰 순으로 정렬했으므로 그룹별 첫 번째 항목이 곧 최강 상대가 된다.
    # 강한 쌍이 없는 변수도 "중복 없음"이라는 근거로 남아야 하므로 여기서는 강도로 거르지 않는다.
    summary = pairs.groupby("x").first()
    summary.rename(columns={"y":"max-y", "coef":"max-coef"}, inplace=True)

    # -- 3) 변수별 중복 쌍의 개수와 목록 ---
    # 하나의 강도가 문자열로 전달된 경우 리스트로 감싸준다.
    # -> 함수 호출 시 ['String', 'Moderate'] 같이 여러 강도를 지정할 수 있도록 하기 위함
    if type(strength) == str:
        strength = [strength]

    # 강도로 길러야 변수마다 개수가 달라져 중복의 정도를 구분 할 수 있다.
    group_pairs = (pairs[pairs["strength"].isin(strength)]
                   .groupby("x")["y"].agg(["count", ", ".join]))

    # -- 4) 두 결과를 병합 ---
    # 중복 쌍이 없는 변수는 병합 결과가 결측이 되므로 0과 "-"로 채운다.
    corr_table = summary[["max-y", "max-coef"]].merge(
        group_pairs, left_index=True, right_index =True, how="left")
    corr_table.fillna({"count":0, "join":"-"}, inplace=True)
    corr_table = corr_table.astype({"count":int})

    # -- 5) 중복이 심한 변수부터 정렬 ---
    # 중복 쌍의 개수가 같으면 최강 상관계수가 큰 변수를 앞에 둔다.
    corr_table.sort_values(by=["count", "max-coef"], key=abs,
                          ascending=False, inplace=True)
    corr_table.rename(columns={"join":"columns"}, inplace=True)

    # -- 6) 결과표 반환 ---
    return corr_table

def chi2_goodness_of_fit(data, column, expected=None, order=None, alpha=0.05,
                        plot=True, palette=None, title=None, xlabel=None,
                        ylabel=None, width=1280, height=640, save_path=None):
    """
    적합도 검정을 가정확인 부터 강도까지 일괄 수행하는 함수 

    Args: 
        data (DataFrame) : 원본 데이터 프레임
        column (str) : 검정 대상 범주형 변수명
        expected (list | None) : 각 범주의 기대빈도 또는 기대비율. None이면 균등분포 (기본값:None)
        order : 명목형 범주의 표시, 계산 순서를 지정하는 리스트
        alpha (float) : 유의수준 (기본값 : 0.05)
        plot (bool) : 결과를 시각호할지 여부 (기본값: True)
        palette (str or list) : 색상 팔레트 (기본값: None)
        title (str) : 그래프 제목 (기본값: None)
        xlabel (str) : x축 라벨 (기본값: None -> 변수명)
        ylabel (str) : y축 라벨 (기본값: None -> "빈도")
        width (int) : 그래프 너비 (기본값: 1280)
        height (int) : 그래프 높이 (기본값: 640)
        save_path (str) : 그래프 저장 경로 (기본값: None)

    Returns:
        DataFrame : 단일 행 결과표 
    """

    # --- 1) 관측빈도 집계 ---
    # 범주별 관측빈도 집계 (order가 있으면 그 순서로, 없으면 라벨 순으로 정렬)
    if order is not None:
        observed = data[column].value_counts().reindex(order)
    else:
        observed = data[column].value_counts().sort_index()
    n = int(observed.sum())
    k = len(observed)

    # --- 2) 기대빈도 결정 ---
    # None이면 균등분포, 합이 1 이하인 비율이면 빈도로 환산, 그 외는 빈도로 사용 
    if expected is None:
        exp = np.full(k, n/k)
    elif np.sum(expected) <= 1.0001:
        exp = np.array(expected, dtype=float) * n
    else: 
        exp = np.array(expected, dtype=float)

    # --- 3) 가정 확인 ---
    # 기대빈도 점검 (5이상 셀이 80% 이상 + 1미만 셀 없음) 
    pct_ok = float((exp>=5).mean())
    min_exp = float(exp.min())
    assumption = bool(pct_ok >=0.8 and min_exp >=1)
    recommend = "Chi-square goodness-of-fit" if assumption else "category merge"

    # --- 4) 적합도 검정 수행 ---
    # 카이제곱 적합도 검정 ( 관측빈도 vs 기대빈도 )
    chi2, p = chisquare(f_obs=observed.values, f_exp=exp)

    # --- 5) 강도 확인 ---
    # 효과크기 : Cohen's w = sqrt(chi2/n)
    w = float(np.sqrt(chi2/n))

    # 효과크기 강도 레벨 
    # --> (Cohen 관례 : 0.1 이하 미미 / 0.3 이하 약함 / 0.5 이하 보통 / 그 이상 강함)
    if w < 0.1:
        strength = "Negligible"
    elif w < 0.3:
        strength = "Weak"
    elif w < 0.5:
        strength = "Moderate"
    else: 
        strength = "Strong"

    # --- 6) 결과표 생성 ---
    result_df = DataFrame([{
        "chi2" : round(float(chi2), 4), 
        "dof" : k-1,
        "p-value" : round(float(p), 6),
        "significant" : bool(p < alpha),
        "effect(w)" : round(w, 4), 
        "strength" : strength,
        "min_expected" : round(min_exp, 2), 
        "assumption" : assumption
    }], index=["Chi-square goodness-of-fit"])

    # --- 7) 결과 시각화 ---
    # 관측 빈도 vs 기대빈도 막대그래프 (long 형식으로 변환해 hue로 비교)
    if plot: 
        cats = list(observed.index)
        plot_df = DataFrame({
            column: cats * 2,
            "구분" : ["관측"]*len(cats) + ["기대"]*len(cats), 
            "빈도": list(observed.values) + list(exp), 
        })
        my_plot.barplot(data=plot_df, x=column, y="빈도", hue="구분", order=cats,
                        palette=palette, title=title, 
                        xlabel=xlabel if xlabel is not None else column,
                        ylabel=ylabel if ylabel is not None else "빈도", 
                        width=width, height=height, save_path=save_path)

    return result_df

# 53p
def _chi2_crosstab(data, row, col, kind, alpha=0.05, plot=True, palette=None, orient='v',
                   title=None, xlabel=None, ylabel=None, width=1280, height=640, save_path=None):
    """
    독립성 검정의 공통 처리부 (가정확인 -> 카이제곱/피셔 분기 -> 크라메르 v)

    Args : 
        data (DataFrame) : 원본 데이터프레임 (개별 관측치)
        row (str) : 행 범주형 변수명 
        col (str) : 열 범주형 변수명
        kind (str) : 검정 종류 (독립성 검정 : "independence"/ 동질성 검정: "homogeneity")
        alpha (float) : 유의수준 ( 기본값: 0.05)
        plot (bool) : 결과를 시각화할지 여부 (기본값 : True)
        palette (str or list) : 색상 팔레트 (기본값 : None)
        orient (str) : 그래프 방향 ('v' 또는 'h', 기본값: 'v')
        title (str) : 그래프 제목 (기본값 : None)
        xlabel (str) : x축 라벨 (기본값: None -> x 변수명 )
        ylabel (str) : y축 라벨 (기본값: None -> "비율(%)")
        width (int) : 그래프 너비 (기본값: 1280)
        height (int) : 그래프 높이 (기본값 : 640)
        save_path (str) : 그래프 저장 경로 (기본값: None)
    
    Returns: 
        DataFrame : (row, col)를 인덱스로 하는 단일 행 결과표 
    """
    # --- 1) 대상 데이터 전처리 ---
    # 두 범주형 변수로 교차표(관측빈도) 생성 
    ct = crosstab(data[row], data[col])

    # --- 2) 가정 확인 ---
    # 카이제곱으로 기대빈도 확보 (2x2는 예이츠 보정 기본 적용) 후 가정 점검
    chi2, p_chi, dof, expected = chi2_contingency(ct) 
    pct_ok = float((expected >=5).mean())
    min_exp = float(expected.min())
    assumption = bool(pct_ok >=0.8 and min_exp>=1)

    # --- 3) 검정 수행 (가정에 따른 분기) ---
    # 가정 위반 + 2x2 이면 피셔의 정확검정으로, 그 외는 카이제곱으로 분기 
    if (not assumption) and tuple(ct.shape) == (2,2):
        test_name = "Fisher's exact test"
        _, p = fisher_exact(ct)
        chi2_out, dof_out = np.nan, np.nan
    else:
        test_name = "Chi-square test of %s"% kind
        p, chi2_out, dof_out = p_chi, chi2, dof

    # --- 4) 강도 확인 ---
    # 효과크기 : 크라메르 V (피셔로 분기해도 chi2 기반 참고치를 함께 제공)
    n = int(ct.values.sum())
    min_dim = min(ct.shape) -1
    cramers_v = float(np.sqrt(chi2/ (n*min_dim))) if min_dim >0 else np.nan 

    # 효과크기 강도 라벨 (Cohen 관례 : 0.1 이하 미미 / 0.3 이하 약함 / 0.5 이하 보통/ 그 이상 강함)
    if cramers_v < 0.1 :
        strength = "Negligible"
    elif cramers_v < 0.3:
        strength = "Weak"
    elif cramers_v < 0.5:
        strength = "Moderate"
    else:
        strength = "Strong"

    # --- 5) 결과표 생성 ---
    result_df = DataFrame([{
        "row": row, 
        "col": col, 
        "test": test_name, 
        "chi2": np.nan if np.isnan(chi2_out) else round(float(chi2_out), 4),
        "dof": dof_out, 
        "p-value": round(float(p), 6), 
        "significant": bool(p < alpha), 
        "effect(V)": round(cramers_v, 4), 
        "strength": strength, 
        "min_expected": round(min_exp, 2), 
        "assumption": assumption, 
    }]).set_index(["row", "col"])

    # --- 6) 결과 시각화 --- 
    # 행 범주별 열 범주 구성비를 100% 누적 막대그래프로 표시 
    if plot: 
        tmp = data[[row, col]].copy()
        tmp["_n"] = 1 # 빈도 집계용 보조 컬럼 
        my_plot.stackplot(data=tmp, x=row, y="_n", hue=col, orient=orient, 
                          aggfunc="sum", ratio=True, palette=palette, title=title,
                          xlabel=xlabel if xlabel is not None else row, 
                          ylabel=ylabel if ylabel is not None else "비율(%)", 
                          width=width, height=height, save_path=save_path )
    return result_df 

def chi2_independence(data, x, y, alpha=0.05, 
                      plot=True, palette=None, orient='v', 
                      title=None, xlabel=None, ylabel=None, 
                      width=1280, height=640, save_path=None):
    """
    독립성 검정을 가정확인부터 강도까지 일괄 수행하는 함수 

        _chi2_crosstab()를 호출하여, 두 범주형 변수의 독립성 검정을 수행한다. 
    """
    return _chi2_crosstab(data, x, y, "independence", alpha, 
                          plot=plot, palette=palette, orient=orient, 
                          title=title, xlabel=xlabel, ylabel=ylabel, 
                          width=width, height=height, save_path=save_path)

def chi2_homogeneity(data, group, category, alpha=0.05, 
                     plot=True, palette=None, orient='v', 
                     title=None, xlabel=None, ylabel=None, 
                     width=1280, height=640, save_path=None):
    """
    동질성 검정을 가정확인부터 강도까지 일괄수행하는 함수 

        _chi2_crosstab()를 호출하여, 두 범주형 변수의 동질성 검정을 수행한다.

    """
    return _chi2_crosstab(data, group, category, "homogeneity", alpha, 
                          plot=plot, palette=palette, orient=orient, 
                          title=title, xlabel=xlabel, ylabel=ylabel, 
                          width=width, height=height, save_path=save_path)
