# -*- coding: utf-8 -*-
"""
지역 판정 테스트 스크립트
/home/pi/n_data/seri_n_data/test_region.py
"""

from region_filter import classify_region


def run_test(desc, region, amount, has_jnt):
    print("\n-----------------------------------------")
    print(f"[TEST] {desc}")
    print(f"입력: 공동도급지역='{region}', 추정금액={amount:,}, 공동도급지역존재={has_jnt}")

    out = classify_region(region, amount, has_jnt)

    print(f"결과 = '{out}'")


def main():
    print("\n============================")
    print("  지역 분류 RULE TEST START ")
    print("============================\n")

    # --- 1) 대구 11억 미만 → 지역(대구)
    run_test(
        "대구 6억 (지역 유지)",
        "대구광역시",
        6_0000_0000,
        True
    )

    # --- 2) 대구 11억 이상 → 전국
    run_test(
        "대구 15억 (전국)",
        "대구광역시",
        15_0000_0000,
        True
    )

    # --- 3) 경북 9억 → 지역
    run_test(
        "경북 9억 (지역)",
        "경상북도 포항시",
        9_0000_0000,
        True
    )

    # --- 4) 경북 20억 → 전국
    run_test(
        "경북 20억 (전국)",
        "경상북도 구미시",
        20_0000_0000,
        True
    )

    # --- 5) 충북 8억 → 지역
    run_test(
        "충북 8억 (지역)",
        "충청북도 청주시",
        8_0000_0000,
        True
    )

    # --- 6) 충북 30억 → 전국
    run_test(
        "충북 30억 (전국)",
        "충청북도 충주시",
        30_0000_0000,
        True
    )

    # --- 7) 세종 10억 → 지역
    run_test(
        "세종 10억 (지역)",
        "세종특별자치시",
        10_0000_0000,
        True
    )

    # --- 8) 세종 18억 → 전국
    run_test(
        "세종 18억 (전국)",
        "세종특별자치시",
        18_0000_0000,
        True
    )

    # --- 9) 공동도급지역 없음 → 수요지역 기반 판단
    run_test(
        "공동도급지역 없음(수요지역=충북) 5억",
        "",
        5_0000_0000,
        False
    )

    print("\n============================")
    print("        TEST COMPLETE       ")
    print("============================")


if __name__ == "__main__":
    main()
