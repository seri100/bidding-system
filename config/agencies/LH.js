module.exports = {
  name: 'LH(한국토지주택공사)',
  code: 'lh',
  folderPath: 'X:\\VOL1\\bid\\bid\\토지가져오기-경현\\LH\\첨부파일',
  evaluationMethod: '종합평가낙찰제',
  scoringCriteria: {
    기술점수: { weight: 45, description: '주택건설 경험' },
    가격점수: { weight: 45, description: '입찰가격' },
    가산점: { weight: 10, description: '친환경, 품질관리' }
  },
  basicAmount: null,
  aValue: {
    nationalPension: 0.0865,
    healthInsurance: 0.0347,
    employmentInsurance: 0.0085,
    industrialAccident: 0.005,
    safetyManagement: 0.02
  },
  bidCalculation: {
    baseDiscount: { min: 4, max: 25 },
    profitMargin: 0.08,
    winningRate: 'bidPrice / basicAmount * 100'
  },
  requiredDocuments: [
    '입찰공고문',
    '입찰명세서',
    '기술제안서',
    '시공계획서',
    '품질관리 계획서'
  ],
  bidDeadline: null,
  contact: {
    phone: '031-XXXX-XXXX',
    email: 'bid@lh.or.kr'
  }
};
