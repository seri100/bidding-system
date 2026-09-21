module.exports = {
  name: '국가철도공단',
  code: 'krr',
  folderPath: 'X:\\VOL1\\bid\\bid\\bid-nr\\attachments',
  evaluationMethod: '종합평가낙찰제',
  scoringCriteria: {
    기술점수: { weight: 35, description: '철도사업 경험' },
    가격점수: { weight: 55, description: '입찰가격' },
    가산점: { weight: 10, description: '기술혁신, 환경친화' }
  },
  basicAmount: null,
  aValue: {
    nationalPension: 0.0865,
    healthInsurance: 0.0347,
    employmentInsurance: 0.0085,
    industrialAccident: 0.006,
    safetyManagement: 0.025
  },
  bidCalculation: {
    baseDiscount: { min: 3, max: 22 },
    profitMargin: 0.09,
    winningRate: 'bidPrice / basicAmount * 100'
  },
  requiredDocuments: [
    '입찰공고문',
    '입찰명세서',
    '기술제안서',
    '철도안전관리 계획서'
  ],
  bidDeadline: null,
  contact: {
    phone: '031-XXXX-XXXX',
    email: 'bid@krr.co.kr'
  }
};
