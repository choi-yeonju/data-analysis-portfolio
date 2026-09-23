import numpy as np
from pandas import to_datetime, DataFrame, ExcelWriter

def set_type(data, as_int=[], as_float=[], as_string=[], as_category=[], as_datetime=[]):
    
    """ 
    데이터 프레임의 컬럼 타입을 변경하고
    변경된 데이터프레임의 정보를 출력하는 함수 

    Args : 
        data (DataFrame) : 타입을 변경할 데이터 프레임 
        as_int (list) : int 타입으로 변경할 컬럼 리스트 
        as_float (list) : float 타입으로 변경할 컬럼 리스트 
        as_string (list) : string 타입으로 변경할 컬럼 리스트 
        as_category (list) : categoty 타입으로 변경할 컬럼 리스트 
        as_datatime (list) : datetime 타입으로 변경할 컬럼 리스트 

    Returns : 
        DataFrame : 타입이 변경된 데이터 프레임 
    """
    df = data.copy()

    for col in as_int: 
        df[col] = df[col].astype(int)
    for col in as_float: 
        df[col] = df[col].astype(float)
    for col in as_string: 
        df[col] = df[col].astype(str)
    for col in as_category: 
        df[col] = df[col].astype('category')
    for col in as_datetime: 
        df[col] = to_datetime(df[col])

    df.info()

    return df         

def get_number_column_names(data):
    """
    데이터 프레임에서 숫자형 컬럼의 이름을 리스트로 반환하는 함수 

    Args: 
        data (DataFrame) : 숫자형 컬럼의 이름을 추출할 데이터 프레임 

    Returns: 
        list: 숫자형 컬럼의 이름 리스트 
    """
    return data.select_dtypes(include="number").columns.to_list()


def get_categorical_column_names(data): 
    """
    데이터 프레임에서 범주형 컬럼의 이름을 리스트로 반환하는 함수 

    Args: 
        data (DataFrame) : 범주형 컬럼의 이름을 추출할 데이터 프레임 

    Returns:
        list: 범주형 컬럼의 이름 리스트 
    """
    return data.select_dtypes(include = "category").columns.to_list()

def check_duplicates(data, drop=True): 
    """
    데이터 프레임에서 행 단위 중복을 검사하고, 중복된 행을 제거하는 함수 

    Args: 
        data (pd.DataFrame) : 중복을 검사할 데이터 프레임 
        drop (bool) : 중복된 행을 제거할지 여부 (기본값 : True) 

    Returns: 
        DataFrame: 중복이 제거된 데이터 프레임 
    """
    df = data.copy()
    duplicate_rows = df.duplicated()
    num_duplicates = duplicate_rows.sum()
    print(f"중복된 행의 수 : {num_duplicates}")

    if drop and num_duplicates > 0:
        df = df.drop_duplicates()
        print("중복된 행이 제거되었습니다.")

    return df

def check_missing_values(data): 
    """
    데이터 프레임에서 컬럼별 결측치 개수와 비율을 계산하여 데이터 프레임으로 반환하는 함수
    
    Args:
        data (pd.DataFrame) : 결측치를 점검할 데이터 프레임 

    Returns: 
        DataFrame: 컬럼별 결측치 개수와 비율이 포함된 데이터 프레임 
    """
    na_count = data.isna().sum()
    na_ratio = (na_count / len(data)) * 100 

    return DataFrame({
        'Missing Count': na_count,
        'Missing Ratio (%)' : na_ratio 
    })

def categorical_summary(data, columns=None, value_counts=True, save_path=None):
    """
    데이터 프레임의 범주형 컬럼에 대한 요약 통계를 반환하는 함수 

    Args: 
        data (pd.DataFrame): 범주형 컬럼이 요약 통계를 출력할 데이터 프레임 
        columns (list) : 요약 통계를 출력할 범주형 컬럼 리스트 
        value_counts (bool) : 각 범주형 컬럼의 value_counts()를 출력할지 여부(기본값 : True)
        save_path (str) : 요약 통계 결과를 CSV 파일로 저장할 경로 (기본값: None, 저장하지 않음)

    Returns: 
        DataFrame: 범주형 컬럼에 대한 요약 통계가 포함된 데이터 프레임 
    """
    
    # colums가 비어있으면 데이터 프레임에서 범주형 컬럼의 이름을 가져옴
    if not columns: 
        columns = get_categorical_column_names(data)

    # 대상 컬럼으로 데이터 프레임 생성 
    df = data[columns].copy()

    # 명목형 변수의 기술 통계량 계산 
    desc_df = df.describe(include="category")

    # 저장된 파일 경로가 전달된 경우 기술 통계량을 Excel 파일로 저장 
    if save_path: 
        desc_df.to_excel(save_path, sheet_name='Summary', index=True)

    # 각 범주형 컬럼의 value_counts()를 출력해야 한다면? 
    if value_counts: 
        for col in columns: 
            cdf = DataFrame(data[col].value_counts())
            cdf.index.name = col 
            cdf.sort_index(inplace=True)
            print(f"컬럼 '{col}'의 value_counts():")
            display(cdf)

            # 저장될 파일 경로가 전달된 경우 value_counts 결과를 Excel 파일로 저장 
            if save_path: 
                # 기존 파일에 이어 쓰기를 수행하기 위해 ExcelWriter를 사용하여 시트별로 저장 
                with ExcelWriter(save_path, mode='a', engine='openpyxl') as excel_writer: 
                    cdf.to_excel(excel_writer, sheet_name=col, index=True)

    return desc_df

def numerical_summary(data, columns=None, save_path=None):
    """데이터프레임의 숫자형 컬럼에 대한 요약 통계를 반환하는 함수

    Args:
        data (DataFrame): 숫자형 컬럼의 요약 통계를 출력할 데이터프레임
        columns (list): 요약 통계를 출력할 숫자형 컬럼 리스트
        save_path (str): 요약 통계 결과를 CSV 파일로 저장할 경로 (기본값: None, 저장하지 않음)

    Returns:
        DataFrame: 숫자형 컬럼에 대한 요약 통계가 포함된 데이터프레임
    """
    #-----------------------------------------------------
    # 1) columns가 비어있으면 데이터프레임에서 숫자형 컬럼의 이름을 가져옴
    #-----------------------------------------------------
    if not columns:
        columns = get_number_column_names(data)

    desc_df = data[columns].describe().T
    #-----------------------------------------------------
    # 2) 평균-중앙값의 상대 차이율을 계산하여 중심 수준 파악
    #-----------------------------------------------------
    # "평균-중앙값 상대 차이율 = |평균 - 중앙값| / 중앙값" 컬럼 추가
    desc_df['rel_diff'] = abs(desc_df['mean'] - desc_df['50%']) / desc_df['50%']

    # 상대 차이율 의미 컬럼 추가
    conditions = [desc_df['rel_diff'] < 0.1, desc_df['rel_diff'] < 0.5]
    choices = ['similar', 'diff']
    desc_df['rdiff_flag'] = np.select(conditions, choices, default='large_diff')

    #-----------------------------------------------------
    # 3) IQR, 이상치 경계값 계산
    #-----------------------------------------------------
    # iqr
    desc_df['iqr'] = desc_df['75%'] - desc_df['25%']

    # 상한 이상치 경계
    desc_df['upper_bound'] = desc_df['75%'] + 1.5 * desc_df['iqr']

    # 하한 이상치 경계
    desc_df['lower_bound'] = desc_df['25%'] - 1.5 * desc_df['iqr']

    #-----------------------------------------------------
    # 4) 명목형 변수를 제외한 데이터 프레임 생성
    #-----------------------------------------------------
    df = data[columns].copy()

    #-----------------------------------------------------
    # 5) 상한 이상치 탐지
    #-----------------------------------------------------
    # 상한 이상치 수
    desc_df['upper_outliers'] = ((df > desc_df['upper_bound'])).sum()

    # 상한 이상치 수 비율
    desc_df['upper_outliers_ratio'] = desc_df['upper_outliers'] / df.shape[0]

    #-----------------------------------------------------
    # 6) 하한 이상치 탐지
    #-----------------------------------------------------
    # 하한 이상치 수
    desc_df['lower_outliers'] = ((df < desc_df['lower_bound'])).sum()

    # 하한 이상치 수 비율
    desc_df['lower_outliers_ratio'] = desc_df['lower_outliers'] / df.shape[0]

    #-----------------------------------------------------
    # 7) 전체 이상치 집계
    #-----------------------------------------------------
    # 통합 이상치 수
    desc_df['outliers'] = desc_df['upper_outliers'] + desc_df['lower_outliers']

    # 통합 이상치 수 비율
    desc_df['outliers_ratio'] = desc_df['outliers'] / df.shape[0]

    #-----------------------------------------------------
    # 8) 왜도 점검
    #-----------------------------------------------------
    # 왜도 계산
    desc_df['skew'] = df.skew()

    # 왜도를 통한 분포 형태 해석
    conditions_skew = [(desc_df['skew'] < -0.5), (desc_df['skew'] > 0.5)]
    choices_skew = ['left tail', 'right tail']
    desc_df['skew_interpret'] = np.select(conditions_skew, choices_skew, default='symmetric')

    #-----------------------------------------------------
    # 9) 첨도 점검
    #-----------------------------------------------------
    # 첨도 계산
    desc_df['kurt'] = df.kurt()

    # 첨도를 통한 분포 형태 해석
    conditions_kurt = [(desc_df['kurt'] < 0), (desc_df['kurt'] > 0)]
    choices_kurt = ['platykurtic', 'leptokurtic']
    desc_df['kurt_interpret'] = np.select(conditions_kurt, choices_kurt, default='mesokurtic')

    #-----------------------------------------------------
    # 10) 로그 변환 필요성 판단 함수 정의 (inner function)
    #-----------------------------------------------------
    def judge_log_transform(skew, kurt, min_value):
        right = skew >= 1 or (skew > 0.5 and kurt > 0)    # 우측 꼬리
        left = skew <= -1 or (skew < -0.5 and kurt > 0)   # 좌측 꼬리

        if right:
            if min_value > 0:   return "log"        # 0이 없으면 순수 log 가 정의된다
            if min_value == 0:  return "log1p"      # 0을 피하려고 +1 한다
            return "none"                           # 음수가 섞이면 로그 계열을 쓸 수 없다
        if left:
            return "reverse_log1p"                  # max-x >= 0 이라 항상 안전하다
        return "none"

    #-----------------------------------------------------
    # 11) 로그 변환 필요성 판정
    #-----------------------------------------------------
    desc_df['log_need'] = desc_df.apply(
        lambda row: judge_log_transform(row['skew'], row['kurt'], row['min']), axis=1)

    #-----------------------------------------------------
    # 12) 기술 통계량 표 저장
    #-----------------------------------------------------
    # 저장 경로 파라미터가 전달되었다면 기술 통계량 표를 Excel 파일로 저장
    if save_path:
        desc_df.to_excel(save_path, index=True)

    #-----------------------------------------------------
    # 13) 결과 리턴
    #-----------------------------------------------------
    return desc_df