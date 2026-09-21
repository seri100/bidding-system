module.exports = {
  name: '한국전력공사',
  code: 'kepco',
  folderPath: 'X:\\VOL1\\bid\\bid\\bid_elec\\agreement_docs',
  evaluationMethod: '종합평가낙찰제',
  scoringCriteria: {
    기술점수: { weight: 40, description: '기술능력, 경험, 인력' },
    가격점수: { weight: 50, description: '입찰가격' },
    가산점: { weight: 10, description: '기술자격, 안전관리' }
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
    baseDiscount: { min: 3, max: 25 },
    profitMargin: 0.08,
    winningRate: 'formula'
  },
  requiredDocuments: [
    '입찰공고문',
    '입찰명세서',
    '기술제안서',
    '시공계획서'
  ],
  bidDeadline: null,
  contact: {
    phone: '02-XXXX-XXXX',
    email: 'bid@kepco.co.kr'
  }
};
