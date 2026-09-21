module.exports = {
  name: '한국수력원자력(주)',
  code: 'khnp',
  folderPath: 'X:\\VOL1\\bid\\bid\\khnp\\2026년\\09월\\14일\\첨부파일',
  evaluationMethod: '기술자격심사제',
  scoringCriteria: {
    기술능력: { weight: 50, description: '원자력 관련 경험' },
    재정능력: { weight: 30, description: '자금 조달 능력' },
    안전관리: { weight: 20, description: '원자력 안전관리 경험' }
  },
  basicAmount: null,
  aValue: {
    nationalPension: 0.0865,
    healthInsurance: 0.0347,
    employmentInsurance: 0.0085,
    industrialAccident: 0.008,
    safetyManagement: 0.03
  },
  bidCalculation: {
    baseDiscount: { min: 2, max: 20 },
    profitMargin: 0.10,
    winningRate: 'bidPrice / basicAmount * 100'
  },
  requiredDocuments: [
    '입찰공고문',
    '기술자격서',
    '재정능력 증명서',
    '안전관리 계획서'
  ],
  bidDeadline: null,
  contact: {
    phone: '042-XXXX-XXXX',
    email: 'bid@khnp.co.kr'
  }
};
