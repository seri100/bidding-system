# -*- coding: utf-8 -*-
"""Install code and units; explicitly start timer after deployment verification."""
import ast
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=Path('/home/pi/n_data')
STAMP=dt.datetime.now().strftime('%Y%m%d_%H%M%S')
BACKUP=BASE/'backups'/('fire_share_auto_'+STAMP)
MARKER='# FIRE_SHARE_QUEUE_V1'
HOOK='''\n\n# FIRE_SHARE_QUEUE_V1
_FIRE_SHARE_ORIGINAL_ENRICH = enrich_score_cap
def enrich_score_cap(row, root, log=lambda text: None):
    result = _FIRE_SHARE_ORIGINAL_ENRICH(row, root, log)
    if result.get('시공경험배점한도') is True:
        try:
            from fire_share_auto import enqueue
            enqueue(result, root, logger=log)
        except Exception as exc:
            log('[FIRE_SHARE][QUEUE_RETRY] %s %s' %
                (result.get('공고번호', ''), type(exc).__name__))
    return result
'''


def main():
    target=BASE/'g2b_score_cap.py'
    original=target.read_text(encoding='utf-8')
    updated=original if MARKER in original else original+HOOK
    ast.parse(updated)
    for name in ('fire_share_auto.py','test_fire_share_auto.py'):
        ast.parse((HERE/name).read_text(encoding='utf-8'))
    BACKUP.mkdir(parents=True)
    for name in ('g2b_score_cap.py','fire_share_auto.py','test_fire_share_auto.py'):
        if (BASE/name).exists():
            shutil.copy2(str(BASE/name),str(BACKUP/name))
    for name in ('fire-share-auto.service','fire-share-auto.timer'):
        p=Path('/etc/systemd/system')/name
        if p.exists():
            shutil.copy2(str(p),str(BACKUP/name))
    # Prepare and validate before replacing the live source.
    temp=BASE/'g2b_score_cap.py.fire_share_new'
    temp.write_text(updated,encoding='utf-8')
    for name in ('fire_share_auto.py','test_fire_share_auto.py'):
        shutil.copy2(str(HERE/name),str(BASE/name))
    os.replace(str(temp),str(target))
    subprocess.check_call(['python3','-m','py_compile',str(target),str(BASE/'fire_share_auto.py')])
    for name in ('fire-share-auto.service','fire-share-auto.timer'):
        subprocess.check_call(['sudo','-n','install','-m','644',str(HERE/name),'/etc/systemd/system/'+name])
    subprocess.check_call(['sudo','-n','systemctl','daemon-reload'])
    subprocess.check_call(['sudo','-n','systemd-analyze','verify','/etc/systemd/system/fire-share-auto.service','/etc/systemd/system/fire-share-auto.timer'])
    archive=Path('/mnt/vol1/소방분담/_자동화')
    archive.mkdir(parents=True,exist_ok=True)
    shutil.copytree(str(HERE),str(archive/('설치패키지_'+STAMP)))
    shutil.copytree(str(BACKUP),str(archive/('변경전백업_'+STAMP)))
    receipt=dict(installed_at=STAMP,backup=str(BACKUP),queue=str(BASE/'state/fire_share_auto/queue'),
                 output='/mnt/vol1/소방분담',files={name:hashlib.sha256((BASE/name).read_bytes()).hexdigest()
                 for name in ('g2b_score_cap.py','fire_share_auto.py')})
    (archive/'설치정보.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False))


if __name__=='__main__':
    main()
