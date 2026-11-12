import json
import os
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pytz

# ===== 설정 영역 =====
GMAIL_ADDRESS = 'REDACTED_PRIVATE_VALUE'
GMAIL_PASSWORD = 'REDACTED_PRIVATE_VALUE'
RECIPIENT_EMAIL = 'REDACTED_PRIVATE_VALUE'

DATA_FILE = r"C:\Users\main\bid_monitor\bid_data.json"
LOG_FILE = r"C:\Users\main\bid_monitor\bid_monitor.log"

def log_message(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    print(log_entry)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")
    except Exception as e:
        print(f"로그 저장 실패: {e}")

def is_running_time():
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    hour = now.hour
    weekday = now.weekday()
    if weekday < 5:
        if 7 <= hour <= 20:
            return True
    else:
        if hour == 17:
            return True
    return False

def fetch_sample_bids():
    """샘플 데이터 반환 (테스트용)"""
    log_message("샘플 입찰공고 데이터 생성 중...")
    
    # 테스트용 샘플 데이터
    bids = [
        {
            'id': '2026040601',
            'title': '[2026] 정보시스템 개발 사업',
            'org': '정보통신부',
            'deadline': '2026-04-20 15:00',
            'budget': '100,000,000',
            'timestamp': datetime.now().isoformat()
        },
        {
            'id': '2026040602',
            'title': '[2026] 웹사이트 유지보수 용역',
            'org': '행정안전부',
            'deadline': '2026-04-15 10:00',
            'budget': '50,000,000',
            'timestamp': datetime.now().isoformat()
        },
        {
            'id': '2026040603',
            'title': '[2026] 건축공사 입찰',
            'org': '국토교통부',
            'deadline': '2026-04-25 14:00',
            'budget': '500,000,000',
            'timestamp': datetime.now().isoformat()
        }
    ]
    
    log_message(f"샘플 데이터 생성 완료: {len(bids)}개")
    return bids

def load_previous_data():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except Exception as e:
        log_message(f"기존 데이터 로드 실패: {e}")
        return []

def save_bids(bids):
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(bids, f, ensure_ascii=False, indent=2)
        log_message(f"데이터 저장 완료: {len(bids)}개")
    except Exception as e:
        log_message(f"데이터 저장 실패: {e}")

def find_new_bids(current_bids, previous_bids):
    previous_ids = {bid.get('id', '') for bid in previous_bids}
    new_bids = [bid for bid in current_bids if bid.get('id', '') not in previous_ids]
    return new_bids

def send_email(new_bids):
    if not new_bids:
        return
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_ADDRESS, GMAIL_PASSWORD)
        subject = f"[나라장터] 신규 입찰공고 {len(new_bids)}건"
        body = "신규 입찰공고\n" + "="*60 + "\n\n"
        for i, bid in enumerate(new_bids, 1):
            body += f"[{i}] {bid.get('title', 'N/A')}\n"
            body += f"    기관: {bid.get('org', 'N/A')}\n"
            body += f"    마감: {bid.get('deadline', 'N/A')}\n"
            body += f"    예정가격: {bid.get('budget', 'N/A')}\n"
            body += "-"*60 + "\n\n"
        body += "\n나라장터: https://www.g2b.go.kr\n"
        body += f"조회 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        msg = MIMEMultipart()
        msg['From'] = GMAIL_ADDRESS
        msg['To'] = RECIPIENT_EMAIL
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        server.send_message(msg)
        server.quit()
        log_message(f"이메일 발송 성공: {len(new_bids)}건")
    except Exception as e:
        log_message(f"이메일 발송 실패: {e}")

def main():
    log_message("=" * 60)
    log_message("나라장터 입찰공고 모니터링 시작")
    if not is_running_time():
        log_message("현재 실행 시간이 아닙니다. 스킵합니다.")
        return
    log_message("실행 시간 확인 완료. 모니터링 진행 중...")
    previous_bids = load_previous_data()
    log_message(f"이전 저장 데이터: {len(previous_bids)}개")
    
    # 샘플 데이터 사용 (실제 API 구현 대기)
    current_bids = fetch_sample_bids()
    
    if not current_bids:
        log_message("조회된 공고가 없습니다")
        return
    new_bids = find_new_bids(current_bids, previous_bids)
    log_message(f"신규 공고: {len(new_bids)}개")
    if new_bids:
        send_email(new_bids)
    save_bids(current_bids)
    log_message("모니터링 완료")
    log_message("=" * 60)

if __name__ == "__main__":
    main()
