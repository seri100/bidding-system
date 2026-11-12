import requests
import urllib.parse

API_KEY = "REDACTED_PRIVATE_VALUE"

# URL 인코딩된 API 키 사용
encoded_key = urllib.parse.quote(API_KEY)

endpoints = [
    ("getBidPblancListInfo", {
        'serviceKey': encoded_key,
        'pageNo': 1,
        'numOfRows': 10
    }),
    ("getBidPblancListInfo", {
        'serviceKey': API_KEY,
        'pageNo': '1',
        'numOfRows': '10'
    }),
]

base_url = "https://apis.data.go.kr/1230000/BidPublicInfoService"

for endpoint_name, params in endpoints:
    url = f"{base_url}/{endpoint_name}"
    print(f"\n테스트: {endpoint_name}")
    print(f"파라미터: {params}")
    try:
        response = requests.get(url, params=params, timeout=10)
        print(f"상태: {response.status_code}")
        print(f"URL: {response.url}")
        print(f"응답 (처음 500자): {response.text[:500]}")
    except Exception as e:
        print(f"오류: {e}")
