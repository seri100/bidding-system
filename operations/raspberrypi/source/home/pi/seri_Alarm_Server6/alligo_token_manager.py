
# -*- coding: utf-8 -*-

"""

alligo_token_manager.py

- Alligo 토큰을 발급/갱신하여 .env 파일에 저장하고, os.environ에도 반영

사용:

  from alligo_token_manager import ensure_alligo_token

  ensure_alligo_token(env_path=".env.prod", force=False)

CLI:

  python alligo_token_manager.py --env .env.prod --force

"""

import os, re, json, argparse

from datetime import datetime, timezone, timedelta

import requests



KST = timezone(timedelta(hours=9))

DEFAULT_TOKEN_URL = "REDACTED_PRIVATE_VALUE"



def _read_env_file(path: str) -> str:

    if not os.path.exists(path): return ""

    with open(path, "r", encoding="utf-8") as f: return f.read()



def _write_env_file(path: str, content: str) -> None:

    with open(path, "w", encoding="utf-8") as f: f.write(content)



def _set_env_kv(text: str, key: str, value: str) -> str:

    pat = re.compile(rf"^({re.escape(key)}=).*?$", re.M)

    if pat.search(text):

        return pat.sub(rf"\1{value}", text)

    return text + ("" if (not text or text.endswith("\n")) else "\n") + f"{key}={value}\n"



def _get_env_value(text: str, key: str, default: str = "") -> str:

    pat = re.compile(rf"^{re.escape(key)}=(.*)$", re.M)

    m = pat.search(text)

    return m.group(1).strip() if m else default



def _request_token(user_id: str, api_key: str, token_url: str) -> str:

    resp = requests.post(token_url, data={"userid": user_id, "apikey": api_key}, timeout=10)

    # 표준: {"code":0,"token":"..."} 혹은 단일 문자열 토큰 대응

    try:

        data = resp.json()

        if isinstance(data, dict) and data.get("token"):

            return data["token"]

        raise RuntimeError(f"Token API error: {data}")

    except Exception:

        tok = resp.text.strip()

        if tok:

            return tok

        raise RuntimeError(f"Unexpected token response: {resp.text}")



def ensure_alligo_token(env_path: str = ".env.prod", force: bool = False) -> str:

    text = _read_env_file(env_path)

    user_id = _get_env_value(text, "ALLIGO_USERID")

    api_key = _get_env_value(text, "ALLIGO_APIKEY")

    token   = _get_env_value(text, "ALLIGO_TOKEN")

    token_url = _get_env_value(text, "ALLIGO_TOKEN_URL", DEFAULT_TOKEN_URL)

    if not user_id or not api_key:

        raise RuntimeError("ALLIGO_USERID 또는 ALLIGO_APIKEY가 .env에 없습니다.")



    issued_key = "ALLIGO_TOKEN_ISSUED_AT"

    issued_at_str = _get_env_value(text, issued_key, "")

    need_refresh = force or (not token)

    if issued_at_str:

        try:

            issued_at = datetime.fromisoformat(issued_at_str)

            age_h = (datetime.now(KST) - issued_at).total_seconds() / 3600.0

            if age_h >= 12:

                need_refresh = True

        except Exception:

            need_refresh = True



    if need_refresh:

        new_token = _request_token(user_id, api_key, token_url)

        now_iso = datetime.now(KST).isoformat(timespec="seconds")

        text = _set_env_kv(text, "ALLIGO_TOKEN", new_token)

        text = _set_env_kv(text, issued_key, now_iso)

        text = _set_env_kv(text, "ALLIGO_TOKEN_URL", token_url)

        _write_env_file(env_path, text)

        os.environ["ALLIGO_TOKEN"] = new_token

        os.environ[issued_key] = now_iso

        return new_token

    else:

        os.environ["ALLIGO_TOKEN"] = token

        if issued_at_str: os.environ[issued_key] = issued_at_str

        return token





# === BEGIN SAFE_SET_ENV_KV PATCH ===

# re.sub 백참조 모호성(\1{value} -> \1<digit>…)을 피하기 위해 lambda 사용

def _set_env_kv(text, key, value):

    import re

    pat = re.compile(rf"(?m)^({re.escape(key)}=).*?$")

    new_text, n = pat.subn(lambda m: m.group(1) + str(value), text)

    if n == 0:

        # 키가 없으면 맨 끝에 추가

        if not new_text.endswith("\n"):

            new_text += "\n"

        new_text += f"{key}={value}\n"

    return new_text

# === END SAFE_SET_ENV_KV PATCH ===

if __name__ == "__main__":

    p = argparse.ArgumentParser()

    p.add_argument("--env", default=".env.prod")

    p.add_argument("--force", action="store_true")

    args = p.parse_args()

    t = ensure_alligo_token(env_path=args.env, force=args.force)

    print(f"OK: token set ({len(t)} chars)")

