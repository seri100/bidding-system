# n_data 공공데이터포털 API 변경 적용 기록 (2026-11-04)

공공데이터포털의 2026-11-03 조달청 입찰공고정보서비스 변경 공지를 반영했다.
공식 명세: https://www.data.go.kr/data/15129394/openapi.do

## 변경 파일

- `n_data/g2b_api02.py`: 운영 서버에서 가져온 신규 모듈.
- `n_data/patches/20261104_api02_main_send.patch`: 변경 전 백업과 운영 main_send.py를 비교해 생성한 패치.
- 이 저장소에는 기존 main_send.py 전체가 없으므로 변경 부분을 패치로 보관한다.

## 동작

기존 BidPublicInfoService 호출을 HTTPS BidPublicInfoService02 및 오퍼레이션명 02로 변환한다.
공사목록과 공사 검색 결과에 다음 별도 API 응답을 공고번호·차수로 병합한다.

| 별도 조회 | 오퍼레이션 |
| --- | --- |
| 공동도급 의무지역·비율 | getBidPblancJntcontrctDutyRgnListInfo02 |
| 가산지역 | getBidPblancIncntvRgnListInfo02 |
| 부공종 | getBidPblancSubsiCnsttyIndstrytyListInfo02 |
| 첨부파일 | getBidPblancListInfoAtchFileInfo02 |

기존 지역·파일 필드와 호환되도록 매핑하고 별도 응답 원문도 보존한다.
첨부 URL 중복을 피하며 기존 호환 필드는 최대 10개이다.
동일 조회조건의 별도 응답은 실행 중 캐시한다.
API 오류 응답은 빈 결과로 처리하지 않고 오류로 중단한다.

## 확인한 결과

- Python 문법 검사 통과.
- URL 변환, 중복 변환 방지, 차수 분리, 공동도급 지역 매핑 검사 통과.
- 실제 R26BK01787561-001: 경기도, 공동도급 49%, 첨부파일 3개 조회 확인.
- 공사목록, 공사검색, 참가지역, 공사기초금액 새 API 정상 응답 확인.
- 검증은 조회만 수행했고 알림톡·캘린더 쓰기는 수행하지 않았다.
- 전체 정기 실행 완료 여부는 이 기록 작성 시 확인 전이다.

## 운영 적용 및 복구

운영 경로: /home/pi/n_data
이미 운영 서버에 적용했으므로 같은 패치를 다시 적용하지 않는다.
변경 전 백업: /home/pi/n_data/backup_api02_20261104_155453/main_send.py

변경 전 파일에 재현할 경우 g2b_api02.py를 main_send.py와 같은 폴더에 복사하고,
먼저 `patch --dry-run -p1 < 20261104_api02_main_send.patch`로 일치 여부를 확인한다.
패치 적용 뒤 `python3 -m py_compile main_send.py g2b_api02.py`로 검사한다.
복구 시 실행 중인 서비스가 없는지 확인한 뒤 위 백업의 main_send.py를 복원한다.

운영 파일 SHA-256:
- main_send.py: e36df3eddb8b1cc2e026b182b74ef51e5481001da90e5da68ce514785c245d71
- g2b_api02.py: 317a2215a5095ee56b68842dfedcfbc9fe19b42d112df1f59ba3cbc4b3cd4a2a
