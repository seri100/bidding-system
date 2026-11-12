#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
========================================================
  /home/pi/result/bid_collector.py
  나라장터 입찰공고 자동 수집기 (공사 / 물품)
  - 정식 엔드포인트: apis.data.go.kr/1230000/ad/BidPublicInfoService
  - Decoding 키 사용 (requests가 자동 인코딩)
  - 매일 08:00, 14:00 crontab 자동 실행
========================================================
"""

import os
import sys
import logging
import requests
import pandas as pd
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config


# ──────────────────────────────────────────────────────
#  로거
# ──────────────────────────────────────────────────────
def setup_logger() -> logging.Logger:
    log_dir = os.path.dirname(config.LOG_FILE)
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger("bid_collector")
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    fh = logging.FileHandler(config.LOG_FILE, encoding="utf-8")
    fh.setFormatter(fmt)
    if not logger.handlers:
        logger.addHandler(ch)
        logger.addHandler(fh)
    return logger


# ──────────────────────────────────────────────────────
#  컬럼 한글 매핑
# ──────────────────────────────────────────────────────
COLUMN_MAP = {
    "bidNtceNo"          : "입찰공고번호",
    "bidNtceOrd"         : "차수",
    "ntceInsttCd"        : "공고기관코드",
    "ntceInsttNm"        : "공고기관명",
    "dminsttCd"          : "수요기관코드",
    "dminsttNm"          : "수요기관명",
    "bidNtceNm"          : "입찰공고명",
    "bidNtceDt"          : "공고일시",
    "bidClseDt"          : "입찰마감일시",
    "opengDt"            : "개찰일시",
    "opengPlce"          : "개찰장소",
    "bidMethdNm"         : "입찰방법",
    "cntrctCnclsMthdNm"  : "계약방법",
    "ntceKindNm"         : "공고종류",
    "asignBdgtAmt"       : "배정예산금액",
    "presmptPrce"        : "추정가격",
    "bssamt"             : "기초금액",
    "drwtPrceCalcMthdNm" : "낙찰하한율방식",
    "lctrBidYn"          : "지역제한입찰여부",
    "intrntnlDlngYn"     : "국제입찰여부",
    "rbidPermsnYn"       : "재입찰허용여부",
    "prtcptPsblRgnNm"    : "참가가능지역",
    "bidNtceUrl"         : "공고URL",
    "rgstDt"             : "등록일시",
    "dtilPrdRgstDt"      : "세부공고등록일시",
    "cnstrtnWorkNm"      : "공사명",
    "rgnNm"              : "지역명",
    "ntceLicnsLmtYn"     : "면허제한여부",
    "indstrytyLmtYn"     : "업종제한여부",
    "cmmnSpcsNm"         : "공통규격명",
}


# ──────────────────────────────────────────────────────
#  API 호출 → DataFrame 반환
# ──────────────────────────────────────────────────────
def fetch_bid_data(category: str, endpoint: str,
                   logger: logging.Logger) -> pd.DataFrame:
    """
    ✅ Decoding 키를 params=에 직접 전달
       → requests가 자동으로 URL 인코딩 처리 (이중 인코딩 없음)
    """
    today        = datetime.today().strftime("%Y%m%d")
    inqry_bgn_dt = today + "0000"
    inqry_end_dt = today + "2359"
    url          = f"{config.BASE_URL}/{endpoint}"

    all_data    = []
    page        = 1
    total_count = None

    logger.info(
        f"[{category}] 수집 시작\n"
        f"  URL    : {url}\n"
        f"  기간   : {inqry_bgn_dt} ~ {inqry_end_dt}"
    )

    while True:
        # ✅ Decoding 키를 params에 그대로 전달 (requests가 자동 인코딩)
        params = {
            "serviceKey" : config.API_SERVICE_KEY,
            "pageNo"     : page,
            "numOfRows"  : config.NUM_OF_ROWS,
            "type"       : config.DATA_TYPE,
            "inqryDiv"   : 1,
            "inqryBgnDt" : inqry_bgn_dt,
            "inqryEndDt" : inqry_end_dt,
        }

        try:
            resp = requests.get(url, params=params, timeout=30)

            # ── 첫 페이지: 실제 호출 URL 로그 출력 (디버깅) ──
            if page == 1:
                logger.info(f"[{category}] 실제 요청 URL: {resp.url}")

            # ── Unexpected errors 명시 처리 ──
            if "Unexpected errors" in resp.text:
                logger.error(
                    f"[{category}] ❌ 'Unexpected errors' 응답\n"
                    f"  원인1: URL 경로 오류 → BASE_URL 확인\n"
                    f"  원인2: 파라미터명 오류 → inqryBgnDt/inqryEndDt 확인\n"
                    f"  원인3: API 미신청 → data.go.kr 활용신청 확인\n"
                    f"  응답 : {resp.text[:300]}"
                )
                break

            if resp.status_code != 200:
                logger.error(
                    f"[{category}] HTTP {resp.status_code}\n"
                    f"  응답: {resp.text[:500]}"
                )
                break

            result = resp.json()

        except requests.exceptions.Timeout:
            logger.error(f"[{category}] 타임아웃 (page={page})")
            break
        except ValueError:
            logger.error(
                f"[{category}] JSON 파싱 실패\n"
                f"  응답: {resp.text[:500]}"
            )
            break
        except Exception as e:
            logger.error(f"[{category}] 오류: {e}")
            break

        # ── 응답 파싱 ──
        try:
            # 공공API 에러 구조 체크
            if "OpenAPI_ServiceResponse" in result:
                hdr      = result["OpenAPI_ServiceResponse"]["cmmMsgHeader"]
                err_code = hdr.get("returnReasonCode", "")
                err_msg  = hdr.get("returnAuthMsg", "")
                logger.error(
                    f"[{category}] API 에러\n"
                    f"  코드: {err_code} / 메시지: {err_msg}\n"
                    f"  30: 서비스 미신청 → data.go.kr 활용신청\n"
                    f"  22: 트래픽 초과 → 내일 재시도\n"
                    f"  12: URL 오류 → BASE_URL 재확인"
                )
                break

            body  = result.get("response", {}).get("body", {})
            items = body.get("items", None)

            if total_count is None:
                total_count = int(body.get("totalCount", 0))
                logger.info(f"[{category}] 전체 공고 수: {total_count}건")

            if not items:
                msg = "오늘 공고 없음" if total_count == 0 else "마지막 페이지"
                logger.info(f"[{category}] page {page}: {msg} → 종료")
                break

            if isinstance(items, dict):
                items = [items]

            all_data.extend(items)
            logger.info(
                f"[{category}] page {page} | {len(items)}건 "
                f"(누계 {len(all_data)}/{total_count})"
            )

            if len(all_data) >= total_count:
                logger.info(f"[{category}] ✅ 전체 수집 완료")
                break

            page += 1

        except Exception as e:
            logger.error(f"[{category}] 파싱 오류: {e}\n  응답: {str(result)[:300]}")
            break

    if not all_data:
        logger.warning(f"[{category}] 수집된 데이터 없음")
        return pd.DataFrame()

    df = pd.DataFrame(all_data)
    logger.info(f"[{category}] DataFrame: {len(df)}행 × {len(df.columns)}열")
    return df


# ──────────────────────────────────────────────────────
#  CSV 저장
# ──────────────────────────────────────────────────────
def save_to_csv(df: pd.DataFrame, category: str,
                logger: logging.Logger):
    today    = datetime.today().strftime("%Y%m%d")
    filename = config.CSV_FILENAME_FORMAT.format(
        category=category, date=today
    )

    for save_dir in [config.LOCAL_RESULT_DIR, config.NETWORK_RESULT_DIR]:
        dir_path = Path(save_dir)
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"폴더 생성 실패 [{save_dir}]: {e} → 건너뜀")
            continue

        filepath = dir_path / filename
        try:
            if filepath.exists():
                existing = pd.read_csv(filepath, encoding="REDACTED_PRIVATE_VALUE")
                combined = pd.concat([existing, df], ignore_index=True)
                dedup = [c for c in ["입찰공고번호", "차수"]
                         if c in combined.columns]
                if dedup:
                    combined.drop_duplicates(
                        subset=dedup, keep="last", inplace=True
                    )
                combined.to_csv(filepath, index=False, encoding="REDACTED_PRIVATE_VALUE")
                logger.info(
                    f"[{category}] 병합 저장: {filepath} ({len(combined)}건)"
                )
            else:
                df.to_csv(filepath, index=False, encoding="REDACTED_PRIVATE_VALUE")
                logger.info(
                    f"[{category}] 신규 저장: {filepath} ({len(df)}건)"
                )
        except PermissionError:
            logger.error(f"[{category}] 저장 권한 없음: {filepath}")
        except Exception as e:
            logger.error(f"[{category}] 저장 오류: {e}")


# ──────────────────────────────────────────────────────
#  메인
# ──────────────────────────────────────────────────────
def main():
    logger  = setup_logger()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    logger.info("=" * 60)
    logger.info(f"  나라장터 입찰공고 수집 시작: {now_str}")
    logger.info("=" * 60)

    ok_cnt  = 0
    err_cnt = 0

    for category, endpoint in config.ENDPOINTS.items():
        logger.info(f"\n{'─' * 50}")
        logger.info(f"  ▶ 카테고리: {category}")
        logger.info(f"{'─' * 50}")

        try:
            df = fetch_bid_data(category, endpoint, logger)
            if df.empty:
                err_cnt += 1
                continue

            df.rename(
                columns={k: v for k, v in COLUMN_MAP.items()
                         if k in df.columns},
                inplace=True
            )
            df.insert(0, "수집일시",
                      datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

            save_to_csv(df, category, logger)
            ok_cnt += 1

        except Exception as e:
            logger.error(f"[{category}] 처리 오류: {e}", exc_info=True)
            err_cnt += 1

    logger.info("\n" + "=" * 60)
    logger.info(f"  완료 | 성공: {ok_cnt}  실패: {err_cnt}")
    logger.info(f"  종료: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()


