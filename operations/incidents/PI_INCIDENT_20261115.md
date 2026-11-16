# Pi 입찰 자동화 장애 점검 및 조치 기록 (2026-11-15 ~ 11-16)

> 공개 저장소용 문서입니다. 전화번호, 비밀번호, 토큰, 공인 IP, 접속 키는 일부러 적지 않았습니다.
> 작성: 점검 보조 에이전트(claw), 최종 갱신 2026-11-16 09:40 KST. 확정된 사실과 추정은 구분해 표시했습니다.
> 11-16 10:28(bid-water), 11:11(kepco-srm) 정기 실행 결과는 이 문서 작성 시점에는 아직 확인 전입니다. 8절 참고.

## 1. 요약
- 11-16 09:01 두 타이머(`main_send`, `bid-water`)를 재개했고 이후 정상 실행 중. 공백 구간에서 누락된 알림은 없음(6절).
- 2026-11-12 16:12:59, Pi가 복구 시험을 위해 정상 종료(systemd poweroff)됨. (계획된 작업, 확정)
- 11월 13일~15일 15:34까지 Pi는 꺼져 있었음. 그 사이 수집·발송 없음. (확정)
- 11월 15일 15:34 원본 SD/USB로 재부팅. 시험용 SD 부팅은 하지 않은 것으로 보임. (사용자 진술 + Pi 부팅 장치로 확인)
- 11월 15일 15:35 `main_send`가 NAS 미마운트로 실패(코드 73), 15:47~15:50 수집 불완전(코드 1) 후 15:52 정상 완료. 16:19~16:21 알림톡 50건 발송.
- 중복 발송은 확인되지 않음. (남아 있는 로그 범위, 아래 4절)

## 2. 타임라인
| 시각(KST) | 사건 |
|---|---|
| 11-12 16:10:13 | maintenance 도구가 새 작업 시작을 중지 (pending_window=202611121610) |
| 11-12 16:12:59 | Pi 정상 종료 |
| 11-12 16:13~16:14 | GitHub에 최종 커밋·푸시(마지막 푸시 16:14) |
| 11-15 15:34 | Pi 재부팅. 부팅 직후 NAS 마운트 실패(`CIFS ... Error connecting to socket`) |
| 11-15 15:35 | `main_send` RET=73 `NAS_DATA_MISSING` |
| 11-15 15:47~15:50 | RET=1, API 수집 불완전 (BACKFILL from=202611121610) |
| 11-15 15:52 | RET=0 정상 완료. 이후 알림톡 50건 발송(16:19~16:21) |
| 11-15 17:16 | 사용자 승인 하에 root crontab 20:20 재부팅 주석 처리 |
| 11-15 ~18:10 | 사용자 승인 하에 NAS 마운트 `nobrl` 적용, `main_send.timer`·`bid-water.timer` 비활성 |

## 3. 원인 분석
### 3.1 11-13 공백
- Pi가 꺼져 있었음. (확정)
- 종료 자체는 maintenance 도구로 계획한 정상 종료였음.
- 시험 카드 교체·원복이 이어지지 않았고, 11-15 원본으로 재부팅함. maintenance의 `resume`은 실행되지 않음.
- 11-12 일시 중지된 27개 타이머는 stop만 된 상태라서 11-15 부팅 때 자동 복귀함. (25개 enabled+active 확인)

### 3.2 bid-water 실패
- 증상: 매 실행 약 5분 뒤 `sqlite3.OperationalError: database is locked`. 11-09부터 성공 기록 없음.
- 원인(재현 확인): NAS(SMB, vers=2.1) 위에 SQLite 파일(`.../bid-water/state/alimtalk_sent.sqlite3`)이 있고, 이 마운트에서 SQLite 쓰기가 잠금 오류로 실패함. 같은 폴더에서 임시 SQLite 테스트도 같은 오류였음.
- 해당 DB는 11-11 10:31부터 0바이트라 발송 이력이 없음. 11-11 이후 K-water 알림 미발송 가능성.
- 조치: 마운트 옵션에 `nobrl` 추가. 적용 후 같은 테스트 정상. **실제 서비스 실행으로는 아직 검증 전.**

### 3.3 kepco-srm 실패
- 11-15 `exit 10`은 부팅 직후 NAS 미마운트(일회성, 확정).
- 11-10~12 20분 타임아웃은 래퍼 마지막 단계(NAS로 SQLite 백업)가 같은 잠금 문제로 멈춘 것으로 **추정**(미증명). 백업 파일이 10-27부터 0바이트.
- 실제 알림 발송과 엑셀 생성은 수행됨.

### 3.4 logrotate 실패
- mysql 로그 로테이트 postrotate 단계의 비밀번호 오류. 운영에는 영향이 작음. 조치 안 함.

## 4. 중복 발송 점검 결과
- 실제 가드 DB: `/home/pi/n_data/split/history/send_guard.sqlite3` (2915행, `(bid_key, phone)` 중복 0).
- NAS 발송 키 파일 `sent_keys.txt` 3568줄, 중복 0.
- 로그 33개(10-12 이후) 성공 발송 826건, 중복 0.
- 11-15 필터 후 234건 중 50건 발송. **나머지 184건이 제외된 이유는 확인하지 못함.**
- 참고: 과거 문서에 "send_guard 0바이트"라는 기재가 있으나 실제 경로는 위와 같고 정상 동작함.

## 5. 이번에 변경한 것 (되돌리는 방법 포함)
| 대상 | 변경 | 백업/되돌리기 |
|---|---|---|
| root crontab | `20 20 * * * reboot` 줄을 `#DISABLED_20261115# `로 주석 처리 | `/home/pi/crontab_root.bak_20261115_171600` 로 복원 |
| `/etc/systemd/system/mnt-vol1.mount` | Options에 `nobrl` 추가 | `mnt-vol1.mount.bak_20261115_before_nobrl` 복사 후 `daemon-reload`, `umount /mnt/vol1`, `systemctl restart mnt-vol1.mount` |
| `main_send.timer` | 11-15 disable -> **11-16 09:01 enable --now (재개 완료)** | 문제 시 `systemctl disable --now main_send.timer` |
| `bid-water.timer` | 11-15 disable+stop -> **11-16 09:01 enable --now (재개 완료)** | 문제 시 `systemctl disable --now bid-water.timer` |
| 원격 점검 터널(`claw-tunnel.service`) | 신규 생성·enable | 점검 종료 후 `disable --now` 및 키 삭제 (아래 6절) |

## 6. 11-16 재개와 공백 구간 확인
- 11-16 06:30 읽기 전용 점검: Pi 가동(재부팅 없음), NAS `nobrl` 유지, 20:20 재부팅 주석 유지, send_guard·sent_keys 중복 0.
- bid-water `--no-send` 시험 실행: rc=0, `database is locked` 없음(수정 효과 부분 확인). 운영 이력 파일 변화 없음.
- 11-16 09:01 사용자 승인 후 `bid-water.timer`, `main_send.timer` enable. `main_send.timer`는 `Persistent=true`라 즉시 1회 실행됨: RET=0, 발송 0건. (`bid-water.timer`는 `Persistent=false`라 08:28 회차는 건너뜀)
- 공백 구간 보충 조회(모두 `--no-send`, 운영 상태 불변):
  - G2B 11-15 14:38~11-16 09:08: 수집 51 -> 필터 통과 6 -> **발송 대상 0**. 제외 사유: 건축 단독 3, 취소공고 수신자 없음 2, 이미 완료 1, 기초금액 갱신 수신자 없음 4.
  - K-water 11-09 14:28~11-16 09:10: 수집 11 -> 필터 통과 2 -> **발송 대상 0**(알림 대상 N, 수신번호 없음).
- 결론: 두 공백 구간에서 누락된 알림은 없음.
- 발견: main_send는 `N_DATA_AUTO_RECOVERY=1`에서만 pending window를 사용하고 정상 종료 시 삭제함. 타이머가 꺼진 시간만큼의 공백은 자동 보충되지 않음. 운영 중지 후 재개할 때는 `--hours N --no-send`로 구간을 먼저 확인할 것.

## 7. 점검 종료 후 정리 (접속 해제)
1. Pi `claw-tunnel.service` disable/stop, 서비스 파일 삭제.
2. Pi `~/.ssh/authorized_keys`에서 `claw-vm-to-pi` 줄 삭제. Pi `~/.ssh/id_tunnel*` 삭제.
3. 점검용 VM의 터널 계정 키 삭제.

## 7-1. 주의 사항 (다음 관리자에게)
- **`pi_maintenance.py resume`을 실행하지 말 것.** `/home/pi/.config/n_data-recovery/maintenance-20261112.json`(`phase=shutdown_prepared`)은 오래된 기록이며, 실행하면 `main_send`·`bid-water` 타이머가 켜짐. 정리가 필요함.
- 20:20 재부팅은 `main_send` 15분 주기 실행과 겹칠 수 있어 비활성화함. 재도입하려면 실행 중 발송이 끝난 뒤로 시각을 조정할 것.
- bid-water 재개 시 "11-09 이후 밀린 공고 일괄 발송" 위험은 **없음**(11-16 확인). 아침 첫 실행은 last_run과 무관하게 전날 00:00부터만 조회함. 대신 11-09 14:28~11-14 23:59 구간은 정기 실행으로는 수집되지 않는 공백이며, 11-16 `--force-from`으로 조회해 보니 발송 대상 0건이었음(6절).
- 전원 어댑터 점검 권장. `vcgencmd get_throttled`가 `0x50000`(과거 저전압).
- Pi에는 RTC가 없음(fake-hwclock). 부팅 직후 로그 시각이 어긋날 수 있음.
- `kepco-srm` 월요일 11:11 실행으로 NAS 수정 효과를 확인할 것.

## 8. 남은 일
- [x] 11-16 06:30 사전 점검 및 재개(완료, 6절)
- [ ] 11-16 10:28 bid-water 첫 정기 실행 결과 확인
- [ ] 11-16 11:11 kepco-srm 정기 실행 결과 확인(NAS 잠금 해소 여부)
- [ ] 11-15 필터 후 184건 제외 사유 확인(11-16 로그에서 건축 단독·수신자 없음 등 필터 규칙 사유 확인, 11-15 건 자체는 미확인)
- [ ] `maintenance-20261112.json` 정리
- [ ] `bid-water`/`kepco-srm`/`logrotate` 실패 이력 재확인
- [ ] 점검 터널 해제
