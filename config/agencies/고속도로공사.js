module.exports = {
  name: '한국도로공사',
  code: 'hrco',
  folderPath: 'X:\\VOL1\\bid\\bid\\exroad\\attachments',
  evaluationMethod: '종합평가낙찰제',
  scoringCriteria: {
    기술점수: { weight: 40, description: '도로공사 경험' },
    가격점수: { weight: 50, description: '입찰가격' },
    가산점: { weight: 10, description: '안전기술, 교통관리' }
  },
  basicAmount: null,
  aValue: {
    nationalPension: 0.0865,
    healthInsurance: 0.0347,
    employmentInsurance: 0.0085,
    industrialAccident: 0.007,
    safetyManagement: 0.03
  },
  bidCalculation: {
    baseDiscount: { min: 3, max: 23 },
    profitMargin: 0.09,
    winningRate: 'bidPrice / basicAmount * 100'
  },
  requiredDocuments: [
    '입찰공고문',
    '입찰명세서',
    '기술제안서',
    '교통관리 및 안전 계획서'
  ],
  bidDeadline: null,
  contact: {
    phone: '031-XXXX-XXXX',
    email: 'bid@ex.co.kr'
  }
};

