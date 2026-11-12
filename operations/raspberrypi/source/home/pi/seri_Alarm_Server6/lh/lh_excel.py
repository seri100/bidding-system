
# -*- coding: utf-8 -*-

import os

from pathlib import Path

from datetime import datetime



import pandas as pd





class LHExcelSaver:

    """

    LH 크롤링 결과를 엑셀로 저장하는 모듈



    - 저장 경로 (라즈베리파이): /mnt/vol1/bid/LH

    - 윈도우 경로: Z:\\VOL1\\bid\\LH

    """



    def __init__(self, out_dir="/mnt/vol1/bid/LH"):

        self.out_dir = Path(out_dir)

        self.out_dir.mkdir(parents=True, exist_ok=True)



    def save(self, rows):

        """

        rows: dict 리스트 (LHParser.normalize() 결과 리스트)



        반환값: 저장된 엑셀 파일의 전체 경로(Path 객체)

        """

        if not rows:

            return None



        now = datetime.now().strftime("%Y%m%d_%H%M%S")

        filename = f"LH_{now}.xlsx"

        xlsx_path = self.out_dir / filename



        df = pd.DataFrame(rows)

        df.to_excel(xlsx_path, index=False)



        return xlsx_path

