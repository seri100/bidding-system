# 백업 위치와 복구 시험 결과

시험일: 2026-11-12, 한국시간. 이 기록은 실제 NAS 백업과 별도 디스크의 키를 사용한 격리 복원·대시보드 실행 시험이다. **새 Pi의 실물 부팅 시험은 완료되지 않았다.**

## 1. 백업과 키의 정확한 위치

| 자료 | 위치 | 확인 결과 |
|---|---|---|
| PC 암호화 백업 | `C:\Users\main\n_data-recovery-private` | 2개 암호화 원본과 HMAC 인증 확인 |
| NAS 암호화 백업: Windows에서 접근 | `X:\VOL1\bid\system_recovery\20261112` | 직접 복사 후 해시 대조 및 여기서 읽은 파일로 복원 시험 |
| 위 NAS 폴더: Pi에서 접근 | `/mnt/vol1/system_recovery/20261112` | 같은 CIFS 공유의 폴더 존재 확인 |
| 이전 NAS 보관본 | `/mnt/vol1/bid/system_recovery/20261112` | 이전 작업의 보관본도 유지 |
| 키: PC 원래 사본 | `C:\Users\main\n_data-recovery-private\backup.key` | 파일 존재·사본 일치 확인 |
| 키: PC의 별도 물리 디스크 | `E:\n_data-recovery-key\backup.key` | C는 디스크 1, E는 디스크 0임을 확인; ACL 제한 후 복사·해시 대조; 이 키로 복원 성공 |
| 키: Pi 사본 | `/home/pi/.config/n_data-recovery/backup.key` | 읽기 가능 확인 |

현재 복원에 사용하는 파일 이름은 다음과 같다.

```text
raspberrypi_20261112_115442.tar.gz.enc
raspberrypi_20261112_115442.tar.gz.enc.hmac
raspberrypi_20261112_115442.tar.gz.enc.sha256
pc-originals-20261112.tar.gz.enc
pc-originals-20261112.tar.gz.enc.hmac
pc-originals-20261112.tar.gz.enc.sha256
```

`.enc`와 그에 대응하는 `.hmac`를 함께 사용한다. `.sha256`는 파일 전달 확인용이다. **키의 실제 내용은 문서·GitHub·복구 ZIP에 넣지 않는다.** E는 같은 PC 안의 별도 SSD이며 USB 같은 오프라인 보관장치는 아니다. 새 Windows 사용자 계정에서 접근이 거부되면 관리자 권한으로 해당 폴더의 소유권·읽기 권한을 복구한다. 새 PC에서 드라이브 문자가 달라질 수 있으므로 디스크를 먼저 확인한다.

## 2. 이번에 실제 수행한 시험

| 시험 | 결과 |
|---|---|
| NAS에서 암호화 파일을 읽고 E 디스크 키 사용 | 성공 |
| Ubuntu WSL 독립 작업 폴더에 Pi 원본 복원 | 1,245개 파일 해시 인증, SQLite 5개 무결성 검사 통과 |
| PC 원본 복원 | 115개 파일 해시 인증 통과 |
| 필수 비공개 복원 자료 | NAS 자격증명, pi/root crontab, systemd, 수신자 설정, NAS sent_keys 존재 확인 |
| n_data 핵심 코드 8개 | Python 컴파일 통과. 운영 import/실행 시험은 아님 |
| D1 SQL 별도 복원 | 5개 테이블, Calendar 공고 485건, SQLite integrity_check 통과 |
| 암호화 원본에서 꺼낸 대시보드 설치 | 별도 폴더에서 npm ci 성공 |
| 대시보드 build 및 테스트 | 15개 통과 |
| 백업 SQL을 로컬 D1에 적용 | 666개 SQL 명령 성공. 명시적으로 --local 사용 |
| 로컬 실제 화면/API | /gcal, JS, 공고 API가 HTTP 200; Calendar 공고 485건 확인 |
| 로컬 실제 상태 저장 | HTTP 200, 저장 후 재조회 성공, 기존 메모 보존 |
| 로컬 동시 수정 방지 | 오래된 expected 값으로 저장하면 HTTP 409 |
| 운영 영향 | 운영 DB/발송/캘린더 변경 및 타이머 재시작 없음 |

WSL 환경은 Ubuntu 26.04, x86_64, Python 3.14.4이다. 운영 Pi는 ARM/Raspbian 10/Python 3.7.3이므로 이 시험은 같은 하드웨어·OS의 재현이 아니다. WSL의 기본 Python에는 ensurepip가 없어 가상환경의 pip 초기화도 실패했으며, Pi 의존성을 새로 설치했다는 의미로 처리하지 않았다. 기존 의존성의 취약점 12건도 그대로 남아 있다.

## 3. 새 장치 전체 복구 시험의 남은 조건

현재 원격으로 확인 가능한 것은 운영 PC와 기존 운영 Pi다. 새 Pi, 부팅용 새 SD카드, Windows 시험용 새 PC는 연결되지 않았다. 기존 Pi의 운영 SD를 덮어쓰거나 운영 장치를 재설치하지 않았다.

실물 시험에는 다음이 필요하다.

1. **추가 Pi와 별도 SD카드**를 같은 네트워크에 연결한다. 기존 운영 SD와 구분한다.
2. 새 장치의 SSH 접근을 확보한다. 기존 Pi가 실행 중인 동안 새 장치의 발송 timer/crontab은 끈다.
3. OS 부팅, Python/브라우저·문서도구 설치, NAS 마운트를 새 장치에서 확인한다.
4. 암호화 원본을 복원하고 중복 발송 이력·인증정보·수신자 설정을 대조한다.
5. 외부 발송을 막은 상태로 수집부터 결과 파일 생성까지 시험한다.
6. 운영을 전환할 때만 기존 장치의 작업을 중지하고 새 장치에서 한 번의 실제 실행을 확인한다. 두 장치에서 동시에 발송하지 않는다.

Windows 전체 재설치 시험은 별도 PC 또는 새 Windows 가상머신이 필요하다. 이번에는 복원한 앱의 새 작업 폴더와 로컬 D1까지 검증했으며 Windows 설치·드라이버·NAS 가상 드라이브·예약작업 재등록을 처음부터 수행하지 않았다.

## 4. 재현 방법

키와 백업은 GitHub에서 내려받는 파일이 아니다. 위 보관 경로의 파일을 사용한다. Linux/WSL에서 저장소의 도구로 반복할 수 있다.

```bash
python3 operations/tools/recovery_drill.py --archive-root /secure/archives --key /secure/backup.key --destination /secure/new-empty-drill
```

archive-root에는 Pi/PC 암호화 백업을 각 한 개씩 넣는다. destination은 비어 있어야 한다. 복원된 폴더에는 인증정보와 수신번호가 있으므로 비공개로 보관하고, 시험이 끝나면 임시 평문을 정리한다. 도구는 복호화·해시·SQLite·SQL·컴파일 검사와 report.json 작성만 한다. 웹서버, 실제 수집, 발송, 타이머, 배포는 실행하지 않는다.

공개 가능한 결과 요약은 `drills/20261112_offline_report.json`, `drills/20261112_http_results.json`, `drills/20261112_local_write_results.json`에 있다. 원본 데이터·키는 이 보고서에 포함하지 않는다.

## 5. 오프라인 복구 묶음

`recovery-kit-20261112.zip`에는 암호화 원본 2종과 HMAC/SHA, 매뉴얼, 복원 검사 도구를 넣었다. 보관 경로는 PC `C:\Users\main\n_data-recovery-private\recovery-kit-20261112.zip`, NAS `X:\VOL1\bid\system_recovery\20261112\recovery-kit-20261112.zip`이다. **키는 ZIP에 포함하지 않는다.** 이 ZIP과 E의 키를 별도로 확보하면 GitHub 접속 없이 암호화 원본을 꺼내는 단계까지 진행할 수 있다. 프로그램 의존성 설치와 외부 계정 연결까지 오프라인으로 완결되는 구성은 아니다.
