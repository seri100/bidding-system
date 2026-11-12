
import re, datetime, pathlib



path = pathlib.Path("/home/pi/n_data/main_send.py")

s = path.read_text(encoding="utf-8")

backup = path.with_suffix(".py.bak_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))

backup.write_text(s, encoding="utf-8")



pattern = r'(ntceInfo\s*=\s*self\.get_ntce_db\(rows\[i\]\[0\]\)\s*\n\s*if\s+not\s+ntceInfo:\s*\n\s*continue\s*\n)'

if not re.search(pattern, s):

    raise SystemExit("패턴을 찾을 수 없습니다. main_send.py의 640~650줄 주변을 확인해주세요.")



filter_block = r"""

\1                # === 알림톡 대상 필터링 (충북·전국 + 업종코드 0040/0038/0039/6202) ===

                # ntceInfo 구조 [.., bidNtceNm, bidClseDt, jntcontrctDutyRgnNm1, ..., indstrytyCd, prtcptPsblRgnNm]

                ind = str(ntceInfo[0][12]) if len(ntceInfo[0]) > 12 else ""

                region_fields = " ".join(str(x or "") for x in ntceInfo[0])

                target_inds = {"0040", "0038", "0039", "6202"}

                if not (ind in target_inds and ("충북" in region_fields or "충청북도" in region_fields or "전국" in region_fields)):

                    print(f"[FILTER] 스킵됨: {ind} / {ntceInfo[0][4]}")

                    continue

                print(f"[FILTER] 통과: {ind} / {ntceInfo[0][4]}")

"""

s2 = re.sub(pattern, filter_block, s)

path.write_text(s2, encoding="utf-8")

print("[PATCH] 충북·전국 필터 블록이 main_send.py에 삽입되었습니다.")

