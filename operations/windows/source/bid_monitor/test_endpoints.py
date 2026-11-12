import requests

API_KEY = "REDACTED_PRIVATE_VALUE"

# 테스트할 엔드포인트들
endpoints = [
    "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwk",
    "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfo",
    "https://apis.data.go.kr/1230000/BidPublicInfoService/getBidPblancListInfoCnstwk",
    "https://apis.data.go.kr/1230000/BidPublicInfoService/getBidPblancListInfo",
]

params_base = {
    'serviceKey': API_KEY,
    'pageNo': 1,
    'numOfRows': 10,
    'resultType': 'json'
}

for endpoint in endpoints:
    print(f"\n테스트 중: {endpoint}")
    try:
        response = requests.get(endpoint, params=params_base, timeout=10)
        print(f"상태: {response.status_code}")
        if response.status_code == 200:
            print(f"성공! 응답 크기: {len(response.text)}")
            print(f"응답 (처음 300자): {response.text[:300]}")
        else:
            print(f"응답: {response.text[:200]}")
    except Exception as e:
        print(f"오류: {e}")
