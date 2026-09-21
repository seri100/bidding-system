module.exports = {
  name: '조달청(나라장터)',
  code: 'g2b',
  folderPath: 'X:\\VOL1\\bid\\bid\\n_data\\attachments',
  evaluationMethod: '기술자격심사제',
  scoringCriteria: {
    기술능력: { weight: 50, description: '시공실적, 인력' },
    재정능력: { weight: 35, description: '자금 규모' },
    신용도: { weight: 15, description: '신용등급, 부실이력' }
  },
  basicAmount: null,
  aValue: {
    nationalPension: 0.0865,
    healthInsurance: 0.0347,
    employmentInsurance: 0.0085,
    industrialAccident: 0.005,
    safetyManagement: 0.015
  },
  bidCalculation: {
    baseDiscount: { min: 5, max: 30 },
    profitMargin: 0.07,
    winningRate: '예정가격 / 입찰가 * 100'
  },
  requiredDocuments: [
    '입찰공고문',
    '기술제안서',
    '재정능력 증명서',
    '신용등급 증명서'
  ],
  bidDeadline: null,
  contact: {
    phone: '02-XXXX-XXXX',
    email: 'support@g2b.go.kr'
  }
};
