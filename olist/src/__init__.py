import os 
import glob as gl
from matplotlib import font_manager as fm
from matplotlib import pyplot as plt
from pathlib import Path 

# ------------------------------------------------
# 전역 상수 
# ------------------------------------------------
# 무작위성이 개입하는 모든 기능(PCA, 군집, 데이터 분할 등)의 재현성을 위한 랜덤시드 
# 하위 모듈에서 'from . import RANDOM_STATE'로 참조하므로 모듈 임포트보다 먼저 정의한다. 
RANDOM_STATE = 3217

# -----------
# 내보낼 모듈 임포트 
# ----------- 
RANDOM_STATE = 42

from . import my_prep
from . import my_stats
from . import my_plot
from . import my_qtcheck

# ------------------------
# 한글 폰트 설정
# ------------------------
fpath = Path(__file__).resolve().parent / "fonts"   # src/fonts — cwd와 무관하게 항상 이 경로
font_files = list(fpath.glob("*.ttf"))

for f in font_files:
    fm.fontManager.addfont(str(f))
    fprop = fm.FontProperties(fname=str(f))
    fname = fprop.get_name()
    plt.rcParams['font.family'] = fname
#----------------------
# 그래프 기본 설정 
# ----------------------------
my_dpi = 200                                # 이미지 선명도(100~300)
plt.rcParams['font.size'] = 12              # 기본 폰트 이미지 
plt.rcParams['axes.unicode_minus'] = False  # 그래프에 마이너스 깨짐 방지 
plt.rcParams['figure.dpi'] = my_dpi         # 그래프의 dpi  설정
plt.rcParams['savefig.dpi'] = my_dpi        # 저장되는 그래프의 dpi 설정
plt.rcParams['lines.linewidth'] = 2         # 그래프 선 굵기 설정 
plt.rcParams['axes.axisbelow'] =True        # 그래프의 축과 격자선을 뒤에 배치 
