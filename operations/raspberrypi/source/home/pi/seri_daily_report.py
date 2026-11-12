
#!/usr/bin/env python3

# -*- coding: utf-8 -*-



import os, sys, subprocess, datetime, html, pathlib



NOW = datetime.datetime.now()

DATE_STR = NOW.strftime("%Y-%m-%d %H:%M:%S")

YMD = NOW.strftime("%Y%m%d")



# 출력 대상 폴더(두 군데 모두 생성: Z:\n_data 와 Z:\bid\n_data 매핑)

OUT_DIRS = [

    pathlib.Path("/mnt/vol1/n_data"),

    pathlib.Path("/mnt/vol1/bid/n_data"),

]



# 점검 대상 로그/경로 (없는 경우 스킵)

LOG_CANDIDATES = [

    "/home/pi/seri_Alarm_Server6/logs/send.log",

    "/home/pi/seri_Alarm_Server6/logs/error.log",

    "/home/pi/seri_Alarm_Server6/logs/alligo_last_request_form.txt",

    "/home/pi/n_data/logs/main_send_*.log",

    "REDACTED_PRIVATE_VALUE",

]



# 환경 변수 상태

ENV_KEYS = ["TEST_MODE", "ALLOW_PROD_SEND", "ALLIGO_FORCE_PHONE"]



def sh(cmd):

    try:

        out = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, timeout=25)

        return out.decode("utf-8", "replace")

    except subprocess.CalledProcessError as e:

        return (e.output or b"").decode("utf-8", "replace")

    except Exception as e:

        return f"[ERROR] {e}"



def read_tail(path, lines=200):

    if "*" in path:

        # glob

        import glob

        parts = []

        for p in sorted(glob.glob(path))[-5:]:

            parts.append(f"===== {p} (tail {lines}) =====\n" + sh(f"tail -n {lines} {shlex_quote(p)}"))

        return "\n".join(parts) if parts else f"(no match: {path})"

    p = pathlib.Path(path)

    if not p.exists():

        return f"(missing: {path})"

    return sh(f"tail -n {lines} {shlex_quote(path)}")



def list_dir(path, depth=1):

    p = pathlib.Path(path)

    if not p.exists():

        return f"(missing: {path})"

    try:

        if depth <= 0:

            return str(p)

        out_lines = [f"DIR: {path}"]

        for entry in sorted(p.iterdir()):

            try:

                stat = entry.stat()

                size = stat.st_size

                mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")

                out_lines.append(f"{mtime}  {size:>10}  {entry}")

            except Exception:

                out_lines.append(str(entry))

        return "\n".join(out_lines)

    except Exception as e:

        return f"(error listing {path}: {e})"



def shlex_quote(s):

    return "'" + s.replace("'", "'\"'\"'") + "'"



def gather_section(title, body):

    return f"<h2>{html.escape(title)}</h2>\n<pre>{html.escape(body)}</pre>\n"



def main():

    sections = []



    # 헤더

    sections.append(f"<h1>Seri_Alarm_Server6 일일 점검 리포트</h1><p>생성시각: {html.escape(DATE_STR)}</p>")



    # 제어 스위치 상태

    env_dump = []

    for k in ENV_KEYS:

        env_dump.append(f"{k}={os.getenv(k, '')}")

    sections.append(gather_section("제어 스위치(Environment)", "\n".join(env_dump)))



    # 타이머/서비스 상태 (키워드 필터)

    timers = sh("systemctl list-timers --all | sed -e '1,3d' | grep -Ei 'send|alarm|seri|g2b|lh' || true")

    sections.append(gather_section("systemd 타이머(키워드 필터)", timers or "(no match)"))



    unit_files = sh("systemctl list-unit-files | grep -Ei 'send|alarm|seri|g2b|lh' || true")

    sections.append(gather_section("systemd 유닛파일(키워드 필터)", unit_files or "(no match)"))



    proc_list = sh("pgrep -af 'python3|bash|sh' | grep -Ei 'send|alarm|seri|main|crawl|g2b|lh' || echo '(no related process)'")

    sections.append(gather_section("관련 프로세스", proc_list))



    # 로그/디렉터리 스냅샷

    import glob

    for cand in LOG_CANDIDATES:

        if cand.endswith("/exports"):

            body = list_dir(cand, depth=1)

            sections.append(gather_section(f"디렉터리 스냅샷: {cand}", body))

        elif "*" in cand:

            body = read_tail(cand, 100)

            sections.append(gather_section(f"로그(TAIL): {cand}", body))

        else:

            body = read_tail(cand, 200)

            sections.append(gather_section(f"로그(TAIL): {cand}", body))



    # 마운트 상태

    mnt = sh("mount | grep -E '(/mnt/vol1|/mnt/ipdisk)' || true")

    sections.append(gather_section("마운트 상태", mnt or "(empty)"))



    # HTML 조립

    html_doc = f"""<!doctype html>

<html lang="ko">

<meta charset="utf-8"/>

<title>Seri_Alarm_Server6 점검 리포트 - {html.escape(DATE_STR)}</title>

<style>

 body {{ font-family: -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Arial,맑은 고딕,Malgun Gothic,sans-serif; line-height:1.4; }}

 h1 {{ margin: 0.5em 0; }}

 h2 {{ border-left: 4px solid #555; padding-left: 8px; margin-top: 1.2em; }}

 pre {{ background:#f7f7f7; padding:10px; overflow:auto; border:1px solid #ddd; }}

 .footer {{ margin-top:2em; color:#555; font-size:12px; }}

</style>

<body>

{''.join(sections)}

<div class="footer">

 자동 생성 스크립트: /home/pi/seri_daily_report.py<br/>

 저장 위치: /mnt/vol1/n_data 및 /mnt/vol1/bid/n_data (윈도우 Z:\\ 경로 매핑)

</div>

</body></html>

"""



    ok_any = False

    for out_dir in OUT_DIRS:

        try:

            out_dir.mkdir(parents=True, exist_ok=True)

            out_file = out_dir / f"Seri_Alarm_Server6_점검리포트_{YMD}.html"

            out_file.write_text(html_doc, encoding="utf-8")

            print(f"[OK] REPORT:", out_file)

            ok_any = True

        except Exception as e:

            print(f"[WARN] write failed: {out_dir} -> {e}", file=sys.stderr)



    if not ok_any:

        print("[FAIL] no report written", file=sys.stderr)

        sys.exit(1)



if __name__ == "__main__":

    main()

