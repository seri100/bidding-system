from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import time

# Chrome 옵션 설정
chrome_options = Options()
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

# 테스트할 URL들
urls = [
    "https://www.g2b.go.kr/notification/tbidList.do",
    "https://www.g2b.go.kr:8101/ep/tbid/tbidList.do",
    "https://www.g2b.go.kr/ep/tbid/tbidList.do",
    "https://g2b.go.kr/notification/tbidList.do",
    "https://www.g2b.go.kr/",
]

for url in urls:
    try:
        print(f"\n테스트 중: {url}")
        driver.get(url)
        time.sleep(2)
        
        # 현재 URL 확인
        print(f"현재 URL: {driver.current_url}")
        
        # 페이지 제목 확인
        print(f"페이지 제목: {driver.title}")
        
        # 테이블 있는지 확인
        tables = driver.find_elements("tag name", "table")
        print(f"테이블 개수: {len(tables)}")
        
        # 페이지 소스 길이
        print(f"페이지 소스 길이: {len(driver.page_source)}")
        
    except Exception as e:
        print(f"오류: {e}")

driver.quit()
print("\n테스트 완료")
