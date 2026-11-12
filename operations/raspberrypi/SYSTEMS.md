# System catalogue

Captured: 20261112_115442 (Pi local time). See OPERATIONS_MANUAL.md for Korean installation and restoration instructions.

Only enabled/active schedules represent observed scheduling; folders also contain auxiliary and historical files.

## bid-d2b

- Runtime: /home/pi/bid-d2b
- Public source files: 3
- Schedules: d2b-collect.service (static)

- Restore: decrypt/authenticate originals into staging; restore this project and its private configuration/state; install its recorded dependencies; review its schedules; enable only after shared restore checks pass.

## bid-nr

- Runtime: /home/pi/bid-nr
- Public source files: 4
- Schedules: bid-nr-cleanup.service (static), bid-nr.service (static)

- Restore: decrypt/authenticate originals into staging; restore this project and its private configuration/state; install its recorded dependencies; review its schedules; enable only after shared restore checks pass.

## bid-schedule-sync

- Runtime: /home/pi/bid-schedule-sync
- Public source files: 9
- Schedules: bid-nr-gcal-sync.service (static), bid-schedule-sync.service (static), exroad-gcal-sync.service (static)

- Restore: decrypt/authenticate originals into staging; restore this project and its private configuration/state; install its recorded dependencies; review its schedules; enable only after shared restore checks pass.

## bid-water

- Runtime: /home/pi/bid-water
- Public source files: 8
- Schedules: bid-water.service (static)

- Dependencies: operations/raspberrypi/source/home/pi/bid-water/requirements.txt
- Restore: decrypt/authenticate originals into staging; restore this project and its private configuration/state; install its recorded dependencies; review its schedules; enable only after shared restore checks pass.

## bid_elec

- Runtime: /home/pi/bid_elec
- Public source files: 33
- Schedules: kepco-srm.service (disabled)

- Restore: decrypt/authenticate originals into staging; restore this project and its private configuration/state; install its recorded dependencies; review its schedules; enable only after shared restore checks pass.

## bidsync

- Runtime: /home/pi/bidsync
- Public source files: 7
- Schedules: crontab or indirect invocation; inspect inventory

- Restore: decrypt/authenticate originals into staging; restore this project and its private configuration/state; install its recorded dependencies; review its schedules; enable only after shared restore checks pass.

## exroad

- Runtime: /home/pi/exroad
- Public source files: 6
- Schedules: exroad-cleanup.service (static), exroad-notify.service (static)

- Restore: decrypt/authenticate originals into staging; restore this project and its private configuration/state; install its recorded dependencies; review its schedules; enable only after shared restore checks pass.

## fire_assoc

- Runtime: /home/pi/fire_assoc
- Public source files: 1
- Schedules: fire_assoc_new.service (static)

- Restore: decrypt/authenticate originals into staging; restore this project and its private configuration/state; install its recorded dependencies; review its schedules; enable only after shared restore checks pass.

## g2b

- Runtime: /home/pi/g2b
- Public source files: 3
- Schedules: g2b-outbox-sender.service (static), outbox_sender_clean.service (static)

- Restore: decrypt/authenticate originals into staging; restore this project and its private configuration/state; install its recorded dependencies; review its schedules; enable only after shared restore checks pass.

## gongo

- Runtime: /home/pi/gongo
- Public source files: 7
- Schedules: crontab or indirect invocation; inspect inventory

- Restore: decrypt/authenticate originals into staging; restore this project and its private configuration/state; install its recorded dependencies; review its schedules; enable only after shared restore checks pass.

## khnp_auto

- Runtime: /home/pi/khnp_auto
- Public source files: 4
- Schedules: khnp-auto.service (disabled)

- Dependencies: operations/raspberrypi/source/home/pi/khnp_auto/requirements.txt
- Restore: decrypt/authenticate originals into staging; restore this project and its private configuration/state; install its recorded dependencies; review its schedules; enable only after shared restore checks pass.

## kiscon_auto

- Runtime: /home/pi/kiscon_auto
- Public source files: 2
- Schedules: kiscon-daily.service (disabled)

- Dependencies: operations/raspberrypi/source/home/pi/kiscon_auto/requirements.txt
- Restore: decrypt/authenticate originals into staging; restore this project and its private configuration/state; install its recorded dependencies; review its schedules; enable only after shared restore checks pass.

## n_data

- Runtime: /home/pi/n_data
- Public source files: 101
- Schedules: daum_mail_daily.service (static), daum_mail_smc.service (static), daum_mail_sync.service (static), main_send-healthcheck.service (static), main_send.service (disabled), main_send_autocheck.service (static), main_send_healthcheck.service (static), main_send_test.service (static), n_data-raw-cleanup.service (static), n_data-raw-collector.service (static), n_data-raw-watchdog.service (static), n_data_test-main-send.service (static), ndata-main-send.service (disabled), send_road_exbid.service (static), seri-n-data-main-send.service (disabled)

- Dependencies: operations/raspberrypi/source/home/pi/n_data/requirements.txt
- Restore: decrypt/authenticate originals into staging; restore this project and its private configuration/state; install its recorded dependencies; review its schedules; enable only after shared restore checks pass.

## road

- Runtime: /home/pi/road
- Public source files: 0
- Schedules: crontab or indirect invocation; inspect inventory

- Restore: decrypt/authenticate originals into staging; restore this project and its private configuration/state; install its recorded dependencies; review its schedules; enable only after shared restore checks pass.

## seri_Alarm_Server

- Runtime: /home/pi/seri_Alarm_Server
- Public source files: 4
- Schedules: alarmserver.service (disabled), bid-gon-auto.service (static), bidalert.service (disabled), bidalert7.service (disabled), g2b-send.service (disabled), gd2512.service (static), gon-auto-cleanup.service (static), gon-auto-maint.service (disabled), gon_auto_maint.service (disabled), land_crawl.service (disabled), lh-crawl.service (disabled), lh-main.service (disabled), lh-send.service (disabled), lh6-main.service (static), lh6-merge.service (static), lh6-notify.service (static), lh_crawling.service (disabled), main_crawling6.service (static), main_crawling_ok.service (disabled), run-gd1-after-mount.service (enabled), run-gd1.service (static), seri-alarm-main-send.service (disabled), seri-gon-auto.service (static), seri-healthcheck.service (static), seri-lh.service (disabled), seri6-exports-daily.service (static), seri_alarm.service (disabled), seri_alarm_server6.service (static)

- Restore: decrypt/authenticate originals into staging; restore this project and its private configuration/state; install its recorded dependencies; review its schedules; enable only after shared restore checks pass.

## seri_Alarm_Server10

- Runtime: /home/pi/seri_Alarm_Server10
- Public source files: 0
- Schedules: crontab or indirect invocation; inspect inventory

- Restore: decrypt/authenticate originals into staging; restore this project and its private configuration/state; install its recorded dependencies; review its schedules; enable only after shared restore checks pass.

## seri_Alarm_Server2

- Runtime: /home/pi/seri_Alarm_Server2
- Public source files: 20
- Schedules: lh-send.service (disabled), lh_crawling.service (disabled), seri-lh.service (disabled)

- Dependencies: operations/raspberrypi/source/home/pi/seri_Alarm_Server2/requirements.txt
- Restore: decrypt/authenticate originals into staging; restore this project and its private configuration/state; install its recorded dependencies; review its schedules; enable only after shared restore checks pass.

## seri_Alarm_Server3

- Runtime: /home/pi/seri_Alarm_Server3
- Public source files: 17
- Schedules: bid-gon-auto.service (static), gd2512.service (static), gon-auto-cleanup.service (static), gon-auto-maint.service (disabled), gon_auto_maint.service (disabled), run-gd1-after-mount.service (enabled), run-gd1.service (static), seri-gon-auto.service (static)

- Restore: decrypt/authenticate originals into staging; restore this project and its private configuration/state; install its recorded dependencies; review its schedules; enable only after shared restore checks pass.

## seri_Alarm_Server6

- Runtime: /home/pi/seri_Alarm_Server6
- Public source files: 37
- Schedules: g2b-send.service (disabled), land_crawl.service (disabled), lh-crawl.service (disabled), lh-main.service (disabled), lh6-main.service (static), lh6-merge.service (static), lh6-notify.service (static), main_crawling6.service (static), main_crawling_ok.service (disabled), seri6-exports-daily.service (static), seri_alarm_server6.service (static)

- Dependencies: operations/raspberrypi/source/home/pi/seri_Alarm_Server6/requirements.txt
- Restore: decrypt/authenticate originals into staging; restore this project and its private configuration/state; install its recorded dependencies; review its schedules; enable only after shared restore checks pass.

## server-21

- Runtime: /home/pi/server-21
- Public source files: 5
- Schedules: crontab or indirect invocation; inspect inventory

- Restore: decrypt/authenticate originals into staging; restore this project and its private configuration/state; install its recorded dependencies; review its schedules; enable only after shared restore checks pass.
