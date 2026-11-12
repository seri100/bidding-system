from khnp_auto import Bid, bid_from_text, eligible, parse_amount


def test_parse_amount():
    assert parse_amount("추정금액 : 123,456,789원") == 123456789


def test_parse_bid():
    bid = bid_from_text("공고번호 K26S123000-01 공고명 소방시설 개선공사 추정금액 50,000,000원 지역 전국", "https://example.invalid")
    assert bid and bid.bid_no == "K26S123000" and bid.revision == "001"


def test_filter():
    cfg = {"work_keywords": ["공사"], "trade_keywords": ["소방"], "min_amount": 30000000, "allowed_regions": ["전국", "충북"]}
    assert eligible(Bid("K26S1", title="소방시설 공사", region="전국", amount=50000000), cfg)[0]
    assert not eligible(Bid("K26S2", title="소방시설 공사", region="제주", amount=50000000), cfg)[0]
