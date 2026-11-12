# 입찰 자동화 전체 운영·설치·복원 매뉴얼

기준일: 2026-11-12. 관리 저장소: `seri100/bidding-system`.

## 1. 무엇을 어디에서 관리하는가

| 구성 | 실제 실행 위치 | GitHub 위치 | 별도 복원 자료 |
|---|---|---|---|
| 나라장터 수집·금액 보완·발송·장애/복구 문자 | Raspberry Pi `/home/pi/n_data` | `operations/raspberrypi/source/home/pi/n_data` | 인증정보, 수신번호, SQLite, 발송 이력, NAS state |
| LH·나라장터 결과·수자원·한전·국방·원전·협회 등 연계 | Pi의 프로젝트별 폴더 | `operations/raspberrypi/source/home/pi/<프로젝트>` | 각 프로젝트 설정과 상태, NAS 자료 |
| 자동 실행 | Pi systemd 및 pi crontab | `operations/raspberrypi/schedules`, `crontab.reference` | 암호화 백업의 원본 unit/crontab |
| 입찰 대시보드 | Cloudflare Pages `webapp`, D1 `webapp-production` | `operations/windows/source/bid-dashboard` | D1 SQL, Cloudflare Secret, 계정 접근권한 |
| PC 대시보드 보관 작업 | Windows 작업 스케줄러 `BidDashboard-Archive` | 대시보드 `run-archive.ps1`, `archive-bids.mjs` | 작업 XML, NAS 드라이브 연결 |
| 기존 Node 서버 | `C:\bidding-system`에 소스 존재 | `operations/windows/source/bidding-system` | `.env`, 기존 DB/외부 MongoDB 별도 |
| 구형 PC 모니터 | `C:\Users\main\bid_monitor` | `operations/windows/source/bid_monitor` | 작업은 확인 시 Disabled |

`inventory.json`은 조사한 폴더, 자동 실행 상태, 누락 경로, 파일 목록의 기준이다. 폴더가 있다는 사실과 현재 사용 중이라는 사실은 다르다. 실행 진입점은 활성 timer/service 및 crontab으로 판단한다. 공개 소스에는 보조·구형 스크립트도 있으므로 전체를 실행하지 않는다.

**공개 저장소의 소스는 민감정보를 제거한 검토용 사본이다.** `REDACTED_*`가 있는 파일을 그대로 운영 폴더에 덮어쓰면 안 된다. 현재 소스에 인증정보·전화번호가 직접 들어 있는 부분이 있어, 정확한 원상복원에는 암호화 원본 백업이 필요하다. 모든 설정을 환경변수로 전환한 상태는 아니다.

## 2. 백업의 구성과 보관

1. GitHub: 소스, 설치/복원 도구, 일정 참조, 의존성 관측값, 매뉴얼.
2. 암호화 원본: 실제 코드·설정·인증정보·중복 발송 방지 이력·상태 및 PC 원본/D1 SQL. `.enc`, `.hmac`, `.sha256`를 한 묶음으로 보관한다.
3. 복호화 키 `backup.key`: GitHub에 올리지 않는다. 암호화 백업과 별개로 보관하고, 분실에 대비해 오프라인 사본도 마련한다.
4. NAS 원자료·첨부·과거 로그: 이번 코드/상태 백업의 대상이 아니다. NAS 자체의 스냅샷 또는 별도 디스크 백업이 필요하다.
5. Google Calendar·Cloudflare·GitHub 계정: 접근권한과 2단계 인증 복구 수단을 별도 보관한다. Cloudflare Secret은 API로 원래 값을 다시 읽을 수 없으므로 원본 키 또는 재발급 권한이 필요하다.

PC 비공개 보관 폴더는 `C:\Users\main\n_data-recovery-private`이다. 이 폴더는 현재 Windows 사용자만 접근하도록 ACL을 제한했다. Pi 키는 `/home/pi/.config/n_data-recovery/backup.key`다. 별도 물리 디스크의 `E:\n_data-recovery-key\backup.key` 사본도 만들고 이 키로 복원 시험했다. 같은 PC 안의 사본만으로는 PC 디스크 고장을 견딜 수 없다. 백업 파일과 키의 오프라인 사본을 별도 장치에 보관해야 한다.

SQLite는 실행 중 파일을 단순 복사하지 않고 SQLite backup API로 복제하고 `integrity_check`를 확인한다. 개별 파일 백업이므로 여러 프로그램 전체를 같은 순간에 정지한 원자적 스냅샷은 아니다. 엄격한 시점 일치가 필요하면 점검 시간에 해당 작업을 정지한 후 다시 백업한다.

## 3. 사고 발생 직후 순서

1. 기존 Pi가 살아 있는지 확인한다. 기존 Pi와 복원 Pi를 동시에 가동하지 않는다.
2. 복원 장치의 timer/crontab을 활성화하지 않는다. 수신번호·발송 이력이 없는 상태로 프로그램을 실행하지 않는다.
3. 암호화 파일·HMAC·키를 확보하고 별도 폴더에 복원한다.
4. NAS 마운트, 코드, 인증정보, 발송/캘린더 대기 이력 순으로 확인한다.
5. 외부 발송 없이 문법·DB·설정 경로를 확인한다.
6. 필요한 timer만 한 개씩 복구한다. `Persistent=true` timer는 활성화 직후 밀린 작업을 실행할 수 있으므로 마지막에 켠다.
7. 첫 실제 실행의 API 수집 완료, 정상 종료, 중복 발송 여부, Calendar 결과를 확인한다.

## 4. 암호화 백업의 안전한 복원 시험

Linux 또는 OpenSSL/Python이 있는 별도 복구 환경에서 실행한다. 키를 명령행에 직접 쓰지 않는다.

```bash
python3 operations/tools/verify_restore.py --archive /secure/raspberrypi_TIMESTAMP.tar.gz.enc --key /secure/backup.key --destination /secure/restore-pi
```

PC 원본도 같은 도구로 검사한다.

```bash
python3 operations/tools/verify_restore.py --archive /secure/pc-originals-20261112.tar.gz.enc --key /secure/backup.key --destination /secure/restore-pc
```

이 도구는 HMAC 검증 → 복호화 → 경로/링크 검사 → 빈 staging 폴더 추출 → 파일 SHA-256 및 SQLite 검사 순서로 동작한다. 운영 경로에 쓰거나 서비스를 켜지 않는다. `VERIFIED`가 나와도 외부 API·문자·일정 등록까지 확인한 것은 아니다.

## 5. Raspberry Pi 설치 및 복원

### 5.1 새 장치 준비

현재 확인한 운영체제는 Raspbian GNU/Linux 10, Python 3.7.3이다. 오래된 환경이므로 최신 OS에 그대로 복사하면 Chromium, 드라이버, Python 라이브러리 차이로 실패할 수 있다. 이번 작업에서 운영 OS를 변경하지 않았다. 단기 재해복구는 동일한 장치/OS 이미지가 유리하며, 최신 OS 전환은 별도 시험 장치에서 검증한다.

새 장치에 사용자 `pi`, SSH, 정확한 시간/한국시간, NAS 연결을 준비한다. Git, Python, OpenSSL, cron/systemd, 프로젝트가 필요로 하는 Chromium/드라이버 및 문서 변환 도구를 설치한다. 암호화 백업의 `metadata/dpkg-packages.txt`와 프로젝트별 `requirements.txt`, 관측된 의존성 목록을 비교한다. 목록은 설치 결과 기록이며 모든 OS에서 그대로 설치 가능한 잠금 파일은 아니다.

### 5.2 NAS를 먼저 확인

원본 백업의 `/etc/fstab` 및 `/usr/local/sbin/mount_bid.sh`는 참조하여 새 환경에 맞게 적용한다. 기존 fstab 전체를 무조건 덮어쓰지 않는다. NAS 자격증명 파일은 별도 확인한다. 마운트 성공과 `/mnt/vol1/bid`의 실제 파일을 확인한 후 코드/상태를 복구한다. NAS가 비어 있는데 같은 경로의 로컬 폴더에 자료를 새로 만들지 않는다.

### 5.3 파일 복원

복원된 `snapshot/metadata/inventory.json`의 `manifest`에는 원래 절대 경로와 파일 해시가 있다. 빈 새 장치에서 `snapshot/home/pi/<프로젝트>`를 대응 경로로 복사하고 파일 소유자를 `pi`로 맞춘다. 인증파일은 소유자 읽기/쓰기만 허용한다. 셸 진입점의 실행 권한은 manifest의 mode를 확인해 복구한다. 기존 운영 장치에 일괄 덮어쓰기하지 않는다.

각 프로젝트에 원래 가상환경이 있으면 원본을 복사하는 대신 같은 Python 환경에 재생성하고 프로젝트 요구사항을 설치한다. 특정 unit의 `ExecStart`가 `.venv/bin/python` 또는 `.local/bin`을 참조하면 그 경로를 별도로 재구성한다. 이번 소스 스냅샷에는 설치된 외부 라이브러리 전체를 넣지 않았다.

나라장터는 다음을 함께 복원해야 한다.

- `/home/pi/n_data` 코드와 인증·수신자 설정
- 로컬 `state`, `state.db`, 캘린더 대기 키
- NAS `/mnt/vol1/bid/n_data/state`, `send_history`, `sent_keys.txt`, `last_run.txt`, 토큰
- 원자료와 첨부가 필요한 기능은 NAS의 `raw`, `attachments` 별도 백업

이력이 누락되면 이전 공고가 재발송될 수 있다. 코드만 복원한 상태는 정상 복원이 아니다.

### 5.4 프로젝트별 연결

| 프로젝트 | 복원 시 함께 확인할 연결 |
|---|---|
| n_data | 나라장터 API02, 문자/카카오, Google 인증, 수신자 설정, NAS 경로, 복구 알림 상태 |
| bid-nr | 공고 수집 상태, bid-nr timer, Calendar 연계 service |
| bid-water | `.env`, 실행 래퍼, 가상환경/브라우저, NAS 출력 |
| bid_elec | KEPCO SRM 모듈·브라우저, SQLite 발송 상태 |
| bid-d2b | 국방 수집·Calendar·출력 동기화 unit |
| exroad | 도로공사 수집/알림, HWP 처리 환경, Calendar 연계 |
| khnp_auto / kiscon_auto / fire_assoc | 각 설정, 상태, timer/cron, 브라우저·문서 의존성 |
| seri_Alarm_Server 계열 | 활성 unit의 실제 ExecStart 파일, 인증·회사 설정, 각 NAS 출력 |
| gongo / g2b / bidsync / server-21 | crontab, API 설정, DB/Cloudflare 연결, 공유 출력 경로 |
| bid-schedule-sync | Calendar 권한, NAS 폴더, 기관별 연결 스크립트 |

위 표는 진입 안내이며 정확한 활성 상태는 `inventory.json`을 따른다. 누락 경로로 기록된 프로그램은 코드가 확보되지 않았으므로 그대로 복원 완료로 처리하지 않는다.

### 5.5 자동 실행은 마지막에 복구

원본 unit은 암호화 백업 `snapshot/metadata/systemd`에 있다. GitHub의 `.reference`는 일부 지시어만 남긴 참조본이므로 설치용으로 쓰지 않는다. 해당 원본을 검토하고 필요한 unit만 `/etc/systemd/system`에 설치한 다음 `systemctl daemon-reload`한다. 비활성/마스킹된 unit을 일괄 활성화하지 않는다.

pi crontab도 원본을 검토해 필요한 작업만 등록한다. 기존 등록 내용과 합쳐 중복을 제거한다. root crontab도 비공개 백업의 metadata/root-crontab.txt에 보관했다. 다른 사용자 계정의 개별 예약작업까지 조사한 것은 아니다.

## 6. Windows와 대시보드 설치·복원

### 6.1 코드 확보와 로컬 검증

Windows에 Git과 Node.js를 설치한다. 조사 당시 Node v24.20.0/npm 11.19.0이었다. 저장소를 clone하고 대시보드 디렉터리에서 아래를 실행한다.

```powershell
git clone https://github.com/seri100/bidding-system.git C:\bidding-system-recovery
Set-Location C:\bidding-system-recovery\operations\windows\source\bid-dashboard
npm ci
npm test
```

빌드/테스트 전후에 민감정보가 제거된 파일 목록을 `operations/windows/inventory.json`에서 확인한다. 정확한 운영 원본이 필요하면 PC 암호화 백업의 `pc-20261112/files/bid-dashboard`를 별도 작업 폴더로 복원한다. 기존 `seri100/-` 저장소의 원격 설정은 바꾸지 않았다. 통합 저장소 내 위 경로를 이번 복구 기준으로 사용하며, 두 저장소에서 같은 파일을 독립 수정하지 않도록 변경을 통합한다.

### 6.2 Cloudflare 복구

PC만 고장 난 경우 Pages/D1은 클라우드에서 계속 동작할 수 있다. 먼저 기존 `https://webapp-78e.pages.dev/gcal` 상태를 확인하고 기존 DB를 새로 만들거나 덮어쓰지 않는다.

Cloudflare까지 복구해야 하는 경우 별도 복구용 Pages 프로젝트/D1 DB를 생성하고, 복구 작업 폴더의 `wrangler.jsonc`에 **새 DB ID**를 지정한다. 기존 운영 DB ID를 그대로 두고 복원 명령을 실행하지 않는다.

```powershell
npx wrangler login
npx wrangler d1 create webapp-recovery
```

복구용 DB에 백업 SQL을 가져온다. 실제 생성한 DB 이름을 사용한다.

```powershell
npx wrangler d1 execute webapp-recovery --remote --file=C:\secure\dashboard-d1-20261112.sql
```

백업 SQL에는 테이블 정의도 포함되므로 가져오기 전에 기존 마이그레이션을 다시 적용해 테이블을 중복 생성하지 않는다. 이후 변경분 마이그레이션만 별도 검토한다. Google Calendar Secret `GCAL_SERVICE_ACCOUNT_JSON`을 복구 프로젝트에 다시 등록하고 해당 서비스 계정에 Calendar 접근권한을 부여한다. 비밀값을 Git에 저장하지 않는다. 기존 서비스 계정 키 원본이 없으면 Google 계정에서 재발급해야 한다.

새 환경에서 조회·상태·메모·회사별 처리·계산기·캘린더 동기화를 확인하고 배포한다. 기존 사용자 주소 전환은 검증 후 시행한다. D1 SQL은 DB 전체 복원 자료이고, `archives`의 CSV/JSON은 종료 공고 보관 자료이므로 서로 대신할 수 없다.

### 6.3 Windows 자동 보관

PC 원본 백업에 `BidDashboard-Archive.xml`을 보관했다. 새 PC의 사용자명과 코드 경로를 맞춘 후 등록한다. 작업은 사용자가 로그인한 상태에서 실행하도록 되어 있다. `run-archive.ps1`의 절대 경로도 새 설치 경로에 맞춘다.

현재 `archive-bids.mjs`는 `X:/`가 없으면 실패하도록 되어 있으며, 11월 11·12일 로그에 5행 실패 기록이 있다. X는 ipTIME ipDISK 가상 드라이브이고 이번 조사 당시에는 접근 가능했다. 자동 작업 실행 시점에 드라이브가 준비돼 있었는지는 보장되지 않는다. 복구 시 ipDISK 로그인/마운트를 먼저 완료하고 작업을 수동 실행해 SUCCESS와 실제 NAS 파일을 확인한다. 이번 정리에서 이 작업의 저장 정책이나 실행 시간을 바꾸지 않았다.

### 6.4 구형 PC 프로그램

`C:\bidding-system` Node 서버는 조사 시 실행 프로세스가 없었다. 해당 소스와 별도 `package-lock.json`을 보관했으나 외부 MongoDB 데이터 전체는 확보하지 않았다. 사용을 재개하려면 암호화 백업의 `.env` 복원, DB 연결/백업 및 서버 실행 설정 검증이 추가로 필요하다. 구형 `bid_monitor` 예약작업은 비활성 상태였으므로 자동으로 켜지 않는다.

## 7. GitHub 변경 관리

1. 변경 전 현재 운영 원본의 백업을 만들고 파일을 특정한다.
2. 기능 변경과 문서 변경을 같은 커밋에 반영한다. 민감정보가 포함된 원본은 공개 커밋하지 않는다.
3. 공개 스냅샷에서 수정했다면 운영 적용 전 비공개 설정/원본과의 차이를 검토한다. 마스킹된 파일을 운영에 그대로 배포하지 않는다.
4. Python 문법·관련 동작, 대시보드 빌드/테스트 등 변경에 맞는 검사를 수행한다.
5. `git diff`, 민감정보 검사, `git status` 확인 후 commit/push한다.
6. 반영한 운영 파일과 커밋 번호, 시험 결과를 문서로 남긴다. 운영 폴더와 저장소가 자동으로 완전 동기화되는 것은 아니다.

이번 작업은 현재 상태의 복구 기준을 만든 것이다. 장기적으로 공개 소스의 하드코딩 설정을 환경변수/비공개 설정으로 분리하면, Git 코드와 비공개 설정을 조합하는 설치 방식으로 단순화할 수 있다.

## 8. 확인 범위와 남은 항목

- 코드·실행 일정·설치 의존성 관측값, 암호화 원본과 무결성 검사, staging 복원 시험을 수행한다.
- 대시보드는 기존 로컬 환경의 build와 15개 테스트가 통과했다.
- 실제 새 SD카드/새 Windows PC로 부팅하는 전체 재해복구, 운영 문자·캘린더 재발송 시험은 수행하지 않는다.
- NAS 전체 원자료·첨부, 외부 MongoDB, Google/Cloudflare 계정 전체, 라우터 설정·Windows 사용자 전체는 이번 백업에 포함되지 않는다.
- 존재하지 않는 실행 경로, 개별 프로젝트의 외부 설정 파일, root 예약작업 등은 별도 점검이 필요하다. 상세 결과는 `VALIDATION.md`와 두 inventory를 확인한다.


## 9. 다음 백업을 만드는 명령

Pi에서 저장소의 백업 도구를 실행한다. 새 날짜의 폴더에 암호화 원본과 공개 검토 사본을 생성하며 프로그램·타이머는 실행하지 않는다.

```bash
python3 operations/tools/export_operations.py
```

출력된 destination의 public 폴더를 추가 검사한다. 이 검사는 공개 사본에만 실행한다.

```bash
python3 operations/tools/audit_snapshot.py /home/pi/operations_recovery_TIMESTAMP/public
```

공개 사본은 자동 push하지 않는다. 민감정보 제거 결과를 검토하고 파일 inventory/문서와 함께 commit한다. .enc·.hmac·.sha256는 비공개 저장소와 별도 장치에 보관하며, verify_restore.py로 매번 복원 시험한다. Pi 생성 도구는 기본적으로 사용자 pi, /home/pi, /mnt/vol1/bid를 기준으로 한다.

Windows에서는 아래 도구를 실행한다. 기본 대상은 현재 사용자 홈의 bid-dashboard/bid_monitor 및 C:\bidding-system이다. 다른 경로는 SourceRoots 인수로 지정한다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\operations\tools\backup_windows.ps1
```

Git에 포함된 OpenSSL 또는 PATH의 OpenSSL을 사용하며, 없으면 오류로 중단한다. 인증정보가 있는 원본 파일을 복사하므로 출력 위치는 접근이 제한된 비공개 폴더다. 도구 실행만으로 staging 원본은 삭제하지 않는다. 복원 검사 성공을 확인한 후 임시 원본을 정리한다.

D1도 함께 백업하려면 Cloudflare 로그인 권한이 있는 상태에서 -ExportD1을 추가한다. SQL 내보내기는 일시적으로 DB 조회를 대기시킬 수 있으므로 사용이 적은 시간에 시행한다. NAS 원자료 전체와 외부 MongoDB는 이 명령에 포함되지 않는다. 이번에는 반복 백업 예약작업을 새로 등록하지 않았다.


## 10. 백업 위치와 추가 복원 시험

정확한 파일명·PC/NAS 경로·키 위치와 2026-11-12 추가 시험은 [복구 시험 기록](RECOVERY_DRILL_20261112.md)을 따른다. Windows에서 직접 읽는 NAS 경로는 `X:\VOL1\bid\system_recovery\20261112`이며, Pi에서는 `/mnt/vol1/system_recovery/20261112`이다. 이전 `/mnt/vol1/bid/system_recovery/20261112` 보관본도 유지했다.

NAS 백업과 E 디스크 키를 사용한 Ubuntu WSL 복원, 백업 DB를 적용한 로컬 대시보드 조회·저장 시험은 통과했다. 새 Pi/SD카드가 연결돼 있지 않아 실물 부팅·ARM 의존성·NAS 재마운트·실제 발송까지의 전체 재해복구는 아직 완료되지 않았다.
