
# -*- coding: utf-8 -*-

import json

from pathlib import Path

from datetime import datetime



HISTORY = Path("REDACTED_PRIVATE_VALUE")



def _load():

    if not HISTORY.exists():

        return {}

    return json.loads(HISTORY.read_text(encoding="utf-8"))



def _save(data):

    HISTORY.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")



def is_sent(lh_no: str) -> bool:

    data = _load()

    return lh_no in data



def mark_sent(lh_no: str):

    data = _load()

    data[lh_no] = datetime.now().isoformat()

    _save(data)

