// 예정가격 기반 입찰가 계산
function calculateBidPrice(estimatedPrice, evaluationScore, competitorCount = 3) {
    // 기본 할인율: 평가점수 높을수록 낮은 할인율 (높은 가격)
    const baseDiscount = 0.05 + (100 - evaluationScore) / 1000; // 5~15% 범위
    
    // 경쟁사 수 기반 조정 (경쟁이 많을수록 더 낮은 가격)
    const competitionFactor = 1 - (competitorCount * 0.02);
    
    // 최종 입찰가 계산
    const bidPrice = estimatedPrice * (1 - baseDiscount) * competitionFactor;
    
    // 낙찰 확률 추정 (평가점수 + 가격 경쟁력)
    const winProbability = (evaluationScore / 100) * 0.6 + (1 - baseDiscount) * 0.4;
    
    // 예상 이익률 (입찰가 기반)
    const profitMargin = baseDiscount * 100; // %
    const expectedProfit = estimatedPrice - bidPrice;

    return {
        bidPrice: Math.round(bidPrice),
        baseDiscount: Math.round(baseDiscount * 100),
        profitMargin: Math.round(profitMargin),
        expectedProfit: Math.round(expectedProfit),
        winProbability: Math.round(winProbability * 100),
        recommendation: winProbability > 0.7 ? '낙찰 가능성 높음' : '신중한 검토 필요'
    };
}

module.exports = { calculateBidPrice };
