
# -*- coding: utf-8 -*-



import os

from datetime import datetime, timedelta

from pathlib import Path

from typing import Optional, Dict, Any, List, Tuple



import pandas as pd



from .config import DIR_REPORT

from .db import get_db_conn

from .utils import log



# --------------------------------------------------

# matplotlib 로딩 (옵션)

# --------------------------------------------------

plt = None

try:

    import matplotlib



    matplotlib.use("Agg")

    import matplotlib.pyplot as plt

    from matplotlib import font_manager, rcParams



    try:

        nanum_path_candidates = [

            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",

            "/usr/share/fonts/truetype/nanum/NanumGothicCoding.ttf",

        ]

        font_path = None

        for cand in nanum_path_candidates:

            if os.path.exists(cand):

                font_path = cand

                break



        if font_path:

            font_prop = font_manager.FontProperties(fname=font_path)

            rcParams["font.family"] = font_prop.get_name()

            log("[REPORT] matplotlib 한글 폰트 사용: %s" % font_prop.get_name())

        else:

            log("[REPORT][WARN] NanumGothic.ttf 폰트를 찾지 못했습니다. 기본 폰트 사용.")

        rcParams["axes.unicode_minus"] = False

    except Exception as e:

        log("[REPORT][WARN] 폰트 설정 중 오류: %s" % e)

except Exception as e:

    plt = None

    log("[REPORT][WARN] matplotlib 로드 실패, 차트 생략: %s" % e)





# --------------------------------------------------

# 내부 유틸 함수들

# --------------------------------------------------

def _first_tag(v: Any) -> str:

    """지역태그 문자열에서 첫 번째 태그만 추출."""

    if not isinstance(v, str) or not v.strip():

        return ""

    return v.split(",")[0].strip()





def _dict_to_html_table(data: Dict[str, Any]) -> str:

    """딕셔너리를 간단한 HTML 테이블로 변환."""

    if not data:

        return "<p>데이터 없음</p>"

    rows = "".join(

        "<tr><th>{}</th><td>{}</td></tr>".format(k, v) for k, v in data.items()

    )

    return "<table class='simple'><tbody>{}</tbody></table>".format(rows)





def _load_trend_data() -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:

    """

    최근 30일 ntcedata 기반 공고수 통계 조회.

    - trend_daily: 일자별 전체 공고수

    - trend_ind: 일자 x 업종 코드별 공고수 pivot

    """

    trend_daily = None

    trend_ind = None

    try:

        cn = get_db_conn()

    except Exception as e:

        log("[REPORT][WARN] 추세 데이터용 DB 연결 실패: %s" % e)

        return trend_daily, trend_ind



    try:

        q = """

        SELECT DATE(created_at) AS d, ind, COUNT(*) AS cnt

        FROM ntcedata

        WHERE created_at >= (CURDATE() - INTERVAL 29 DAY)

        GROUP BY d, ind

        ORDER BY d, ind

        """

        trend_df = pd.read_sql(q, cn)

        if not trend_df.empty:

            trend_daily = (

                trend_df.groupby("d")["cnt"]

                .sum()

                .reset_index()

                .rename(columns={"cnt": "total_cnt"})

            )

            trend_ind = (

                trend_df.pivot_table(

                    index="d", columns="ind", values="cnt", aggfunc="sum"

                )

                .fillna(0)

                .reset_index()

            )

    except Exception as e:

        log("[REPORT][WARN] 추세 데이터 조회 실패: %s" % e)

    finally:

        try:

            cn.close()

        except Exception:

            pass



    return trend_daily, trend_ind





def _load_today_sms_log() -> Optional[pd.DataFrame]:

    """오늘 발송된 알림톡 sendlog + ntcedata join."""

    try:

        cn = get_db_conn()

    except Exception as e:

        log("[REPORT][WARN] 발송 내역용 DB 연결 실패: %s" % e)

        return None



    sms_df = None

    try:

        q_sms = """

        SELECT s.sent_at,

               s.bid_no,

               s.bid_ord,

               s.receiver,

               s.tpl,

               n.ind,

               n.title,

               n.region_text

        FROM sendlog s

        LEFT JOIN ntcedata n

          ON s.bid_no = n.bid_no AND s.bid_ord = n.bid_ord

        WHERE DATE(s.sent_at) = CURDATE()

        ORDER BY s.sent_at DESC

        """

        sms_df = pd.read_sql(q_sms, cn)

    except Exception as e:

        log("[REPORT][WARN] 발송 내역 조회 실패: %s" % e)

    finally:

        try:

            cn.close()

        except Exception:

            pass



    return sms_df





def _make_charts(

    df: pd.DataFrame,

    by_region: Dict[str, int],

    by_ind: Dict[str, int],

    trend_daily: Optional[pd.DataFrame],

    ts_id: str,

    report_dir: Path,

) -> Dict[str, str]:

    """

    차트를 생성하고 파일명을 dict 로 반환.

    keys: "region", "ind", "trend_total" 등

    """

    chart_files: Dict[str, str] = {}

    global plt



    if plt is None:

        return chart_files



    try:

        # 지역별 공고 수

        if by_region:

            fig = plt.figure(figsize=(6, 3))

            labels = list(by_region.keys())

            values = list(by_region.values())

            plt.bar(labels, values)

            plt.xticks(rotation=30, ha="right")

            plt.title("지역별 공고 수")

            fig.tight_layout()

            img_path = report_dir / ("입찰리포트_{}_region.png".format(ts_id))

            fig.savefig(img_path)

            plt.close(fig)

            chart_files["region"] = img_path.name



        # 업종별 공고 수

        if by_ind:

            fig = plt.figure(figsize=(6, 3))

            labels = list(by_ind.keys())

            values = list(by_ind.values())

            plt.bar(labels, values)

            plt.title("업종별 공고 수")

            fig.tight_layout()

            img_path = report_dir / ("입찰리포트_{}_ind.png".format(ts_id))

            fig.savefig(img_path)

            plt.close(fig)

            chart_files["ind"] = img_path.name



        # 최근 30일 공고 수 추이

        if trend_daily is not None and not trend_daily.empty:

            fig = plt.figure(figsize=(6, 3))

            plt.plot(trend_daily["d"], trend_daily["total_cnt"], marker="o")

            plt.xticks(rotation=30, ha="right")

            plt.title("최근 30일 공고 수 추이")

            fig.tight_layout()

            img_path = report_dir / ("입찰리포트_{}_trend_total.png".format(ts_id))

            fig.savefig(img_path)

            plt.close(fig)

            chart_files["trend_total"] = img_path.name

    except Exception as e:

        log("[REPORT][WARN] 차트 생성 실패: %s" % e)



    return chart_files





def _write_index_html(report_dir: Path) -> None:

    """리포트 목록 index HTML 생성."""

    try:

        index_path = report_dir / "입찰리포트_index.html"

        files = sorted(

            [p for p in report_dir.glob("입찰리포트_*.html")],

            key=lambda x: x.name,

            reverse=True,

        )



        rows_html = ""

        for p in files:

            rows_html += (

                "<tr><td>{}</td>"

                "<td><a href=\"{}\">열기</a></td></tr>".format(p.name, p.name)

            )



        index_html = """<!DOCTYPE html>

<html lang="ko">

<head>

  <meta charset="utf-8" />

  <title>입찰 리포트 목록</title>

  <style>

    body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; font-size:14px; }}

    table {{ border-collapse:collapse; }}

    th,td {{ border:1px solid #ccc; padding:4px 6px; }}

    th {{ background:#f5f5f5; }}

    .wrap {{ max-width:800px; margin:0 auto; padding:12px; }}

    .small {{ color:#666; font-size:12px; }}

  </style>

</head>

<body>

<div class="wrap">

  <h1>입찰 리포트 목록</h1>

  <p class="small">총 {count}개 파일</p>

  <table>

    <thead><tr><th>파일명</th><th>열기</th></tr></thead>

    <tbody>

      {rows}

    </tbody>

  </table>

</div>

</body>

</html>

""".format(

            count=len(files), rows=rows_html

        )



        with open(index_path, "w", encoding="utf-8") as f:

            f.write(index_html)

        log("[REPORT] index HTML 갱신: %s" % index_path)

    except Exception as e:

        log("[REPORT][WARN] index 생성 실패: %s" % e)





# --------------------------------------------------

# 외부에서 사용하는 핵심 함수: make_report

# --------------------------------------------------

def make_report(

    excel_path: str,

    bgn_dt_str: str,

    end_dt_str: str,

    report_dir: Path = DIR_REPORT,

) -> Tuple[Optional[str], Optional[str]]:

    """

    실행 결과 리포트(HTML + EXCEL) 생성.



    :param excel_path: save_excel() 이 생성한 통합 엑셀 경로

    :param bgn_dt_str: 조회 시작 시각 (YYYYMMDDHHMM)

    :param end_dt_str: 조회 종료 시각 (YYYYMMDDHHMM)

    :param report_dir: 리포트 저장 폴더 (기본: DIR_REPORT)

    :return: (report_html_path, report_excel_path)

    """

    report_dir = Path(report_dir)

    report_dir.mkdir(parents=True, exist_ok=True)



    try:

        df = pd.read_excel(excel_path)

    except Exception as e:

        log("[REPORT][ERR] 엑셀 로드 실패: %s" % e)

        return None, None



    if df.empty:

        log("[REPORT] 데이터가 없어 리포트 생성을 건너뜁니다.")

        return None, None



    # 대표지역 컬럼 추가 (지역태그의 첫 번째 값)

    df["대표지역"] = df.get("지역태그", "").apply(_first_tag)



    now = datetime.now()

    ts_id = now.strftime("%Y%m%d_%H%M")

    date_str = now.strftime("%Y-%m-%d %H:%M")



    report_html = report_dir / ("입찰리포트_{}.html".format(ts_id))

    report_xlsx = report_dir / ("입찰리포트_{}.xlsx".format(ts_id))



    total_cnt = len(df)

    target_cnt = int((df.get("알림대상") == "Y").sum())



    by_region = df["대표지역"].value_counts().to_dict()

    by_ind = df["공고업종코드"].value_counts().to_dict()



    # DB에서 추세 데이터 / 발송내역 조회

    trend_daily, trend_ind = _load_trend_data()

    sms_df = _load_today_sms_log()



    # 차트 생성

    chart_files = _make_charts(

        df=df,

        by_region=by_region,

        by_ind=by_ind,

        trend_daily=trend_daily,

        ts_id=ts_id,

        report_dir=report_dir,

    )



    # 요약 테이블

    summary_dict = {

        "전체 공고 수": total_cnt,

        "알림대상 공고 수": target_cnt,

    }



    # 상위 50건 미리보기

    preview_html = df.head(50).to_html(

        index=False,

        border=0,

        justify="left",

        escape=False,

    )



    # 오늘 알림톡 발송 내역

    if sms_df is not None and not sms_df.empty:

        sms_html = sms_df.to_html(index=False, border=0, justify="left")

    else:

        sms_html = "<p>오늘 발송된 알림톡이 없습니다.</p>"



    # HTML 본문 구성

    html_parts: List[str] = []



    html_head = """<!DOCTYPE html>

<html lang="ko">

<head>

  <meta charset="utf-8" />

  <title>입찰 리포트 {ts}</title>

  <style>

    body {{ font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; font-size:14px; }}

    h1,h2,h3 {{ margin: 0.4em 0; }}

    table {{ border-collapse: collapse; }}

    th, td {{ border: 1px solid #ccc; padding: 4px 6px; }}

    th {{ background: #f5f5f5; white-space: nowrap; }}

    .wrap {{ max-width: 1200px; margin: 0 auto; padding: 12px; }}

    .charts img {{ max-width: 100%; height: auto; margin-bottom: 8px; }}

    .small {{ color:#666; font-size:12px; }}

  </style>

</head>

<body>

<div class="wrap">

  <h1>입찰 리포트</h1>

  <p class="small">생성시각: {date_str} / 조회기간: {bgn} ~ {end}</p>

""".format(

        ts=ts_id, date_str=date_str, bgn=bgn_dt_str, end=end_dt_str

    )

    html_parts.append(html_head)



    # 1. 요약

    html_parts.append("<h2>1. 요약</h2>")

    html_parts.append(_dict_to_html_table(summary_dict))



    # 1-1. 지역별 / 1-2. 업종별

    html_parts.append("<h3>1-1. 지역별 공고 수</h3>")

    html_parts.append(_dict_to_html_table(by_region))



    html_parts.append("<h3>1-2. 업종별 공고 수</h3>")

    html_parts.append(_dict_to_html_table(by_ind))



    # 2. 차트

    html_parts.append('<div class="charts">')

    html_parts.append("<h2>2. 차트</h2>")



    if "region" in chart_files:

        html_parts.append(

            '<h3>2-1. 지역별 공고 수</h3>'

            '<img src="{src}" alt="지역별 공고 수" />'.format(

                src=chart_files["region"]

            )

        )

    if "ind" in chart_files:

        html_parts.append(

            '<h3>2-2. 업종별 공고 수</h3>'

            '<img src="{src}" alt="업종별 공고 수" />'.format(

                src=chart_files["ind"]

            )

        )

    if "trend_total" in chart_files:

        html_parts.append(

            '<h3>2-3. 최근 30일 공고 수 추이</h3>'

            '<img src="{src}" alt="일별 공고 수 추이" />'.format(

                src=chart_files["trend_total"]

            )

        )



    html_parts.append("</div>")  # .charts



    # 3. 오늘 수집 공고 (상위 50건)

    html_parts.append("<h2>3. 오늘 수집 공고 (상위 50건 미리보기)</h2>")

    html_parts.append(preview_html)

    html_parts.append(

        '<p class="small">전체 목록은 메인 엑셀 또는 엑셀 리포트에서 확인 가능합니다.</p>'

    )



    # 4. 오늘 알림톡 발송 내역

    html_parts.append("<h2>4. 오늘 알림톡 발송 내역</h2>")

    html_parts.append(sms_html)



    # 마무리

    html_parts.append("</div></body></html>")



    html_full = "\n".join(html_parts)



    try:

        with open(report_html, "w", encoding="utf-8") as f:

            f.write(html_full)

        log("[REPORT] HTML 생성: %s" % report_html)

    except Exception as e:

        log("[REPORT][ERR] HTML 저장 실패: %s" % e)



    # 엑셀 리포트 (요약 + 전체 + 발송내역)

    try:

        with pd.ExcelWriter(report_xlsx, engine="openpyxl") as writer:

            # 전체 데이터

            df.to_excel(writer, sheet_name="오늘공고", index=False)



            # 요약

            sum_rows: List[List[Any]] = [

                ["전체 공고 수", total_cnt],

                ["알림대상 공고 수", target_cnt],

            ]

            if by_region:

                sum_rows.append(["---", "---"])

                sum_rows.append(["[지역별 공고 수]", ""])

                for k, v in by_region.items():

                    sum_rows.append([k, v])

            if by_ind:

                sum_rows.append(["---", "---"])

                sum_rows.append(["[업종별 공고 수]", ""])

                for k, v in by_ind.items():

                    sum_rows.append([k, v])



            sum_df = pd.DataFrame(sum_rows, columns=["구분", "값"])

            sum_df.to_excel(writer, sheet_name="요약", index=False)



            # 발송내역

            if sms_df is not None and not sms_df.empty:

                sms_df.to_excel(writer, sheet_name="발송내역", index=False)



        log("[REPORT] EXCEL 생성: %s" % report_xlsx)

    except Exception as e:

        log("[REPORT][WARN] 엑셀 리포트 생성 실패: %s" % e)



    # index HTML 갱신

    _write_index_html(report_dir)



    return str(report_html), str(report_xlsx)





# --------------------------------------------------

# 추가 헬퍼: generate_all_reports

#  - 필요시 main에서 확장용으로 사용 가능

# --------------------------------------------------

def generate_all_reports(

    excel_path: Optional[str], bgn_dt_str: str = "", end_dt_str: str = ""

) -> None:

    """

    향후 확장용 Wrapper.

    현재는 단일 make_report 만 호출하지만,

    필요하면 여기서 여러 형태의 리포트를 추가로 생성할 수 있다.

    """

    if not excel_path:

        log("[REPORT] generate_all_reports: excel_path가 비어 있어 스킵")

        return



    if not os.path.exists(excel_path):

        log("[REPORT] generate_all_reports: 파일이 존재하지 않아 스킵: %s" % excel_path)

        return



    make_report(

        excel_path=excel_path,

        bgn_dt_str=bgn_dt_str,

        end_dt_str=end_dt_str,

        report_dir=DIR_REPORT,

    )


