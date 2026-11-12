
# -*- coding: utf-8 -*-



import os

from pathlib import Path



import matplotlib

matplotlib.use("Agg")  # 화면 없이 이미지 파일만 생성

import matplotlib.pyplot as plt

from matplotlib import font_manager, rcParams



print("[TEST] matplotlib version:", matplotlib.__version__)



# -----------------------

# 1. 한글 폰트 설정 시도

# -----------------------

nanum_candidates = [

    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",

    "/usr/share/fonts/truetype/nanum/NanumGothicCoding.ttf",

]



font_path = None

for cand in nanum_candidates:

    if os.path.exists(cand):

        font_path = cand

        break



if font_path:

    font_prop = font_manager.FontProperties(fname=font_path)

    rcParams["font.family"] = font_prop.get_name()

    rcParams["axes.unicode_minus"] = False

    print("[TEST] Using font:", font_prop.get_name(), "from", font_path)

else:

    print("[TEST][WARN] Nanum 폰트를 찾지 못했습니다. 기본 폰트 사용.")

    rcParams["axes.unicode_minus"] = False



# -----------------------

# 2. 간단한 차트 생성

# -----------------------

out_dir = Path("/mnt/vol1/n_data/report")

out_dir.mkdir(parents=True, exist_ok=True)



# (1) 막대그래프

fig1 = plt.figure(figsize=(5,3))

x = ["충북", "세종", "대구", "경북"]

y = [10, 3, 7, 5]

plt.bar(x, y)

plt.title("테스트 차트 - 지역별 건수")

plt.tight_layout()

png1 = out_dir / "test_matplotlib_bar.png"

fig1.savefig(png1)

plt.close(fig1)

print("[TEST] Saved:", png1)



# (2) 선그래프

fig2 = plt.figure(figsize=(5,3))

days = list(range(1, 8))

vals = [3, 5, 2, 8, 6, 9, 4]

plt.plot(days, vals, marker="o")

plt.title("테스트 차트 - 7일 추이")

plt.xlabel("일")

plt.ylabel("건수")

plt.tight_layout()

png2 = out_dir / "test_matplotlib_line.png"

fig2.savefig(png2)

plt.close(fig2)

print("[TEST] Saved:", png2)



print("[TEST] Done.")

