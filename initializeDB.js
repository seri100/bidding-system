require('dotenv').config();
const mongoose = require('mongoose');

mongoose.connect(process.env.MONGODB_URI || 'mongodb://localhost:27017/bidding-system')
  .then(() => console.log('✓ MongoDB 연결 성공'))
  .catch(err => {
    console.error('✗ MongoDB 연결 실패:', err);
    process.exit(1);
  });

const criteriaSchema = new mongoose.Schema({
  institution: String,
  sizeRange: String,
  minScore: Number,
  performanceWeight: Number,
  priceWeight: Number,
  others: Number,
  minCreditRating: String,
  minBondRating: String,
  minNoteRating: String,
  description: String,
  lastUpdated: { type: Date, default: Date.now }
});

const Criteria = mongoose.model('Criteria', criteriaSchema);

const initialData = [
  { institution: 'pcs', sizeRange: '300+', minScore: 95, performanceWeight: 30, priceWeight: 50, others: 20, minCreditRating: 'BBB-', minBondRating: 'BBB-', minNoteRating: 'BBB-', description: '조달청 300억원 이상' },
  { institution: 'pcs', sizeRange: '100-300', minScore: 95, performanceWeight: 35, priceWeight: 45, others: 20, minCreditRating: 'BB+', minBondRating: 'BB+', minNoteRating: 'BB+', description: '조달청 100~300억원' },
  { institution: 'pcs', sizeRange: '50-100', minScore: 95, performanceWeight: 30, priceWeight: 50, others: 20, minCreditRating: 'BB+', minBondRating: 'BB+', minNoteRating: 'BB+', description: '조달청 50~100억원' },
  { institution: 'pcs', sizeRange: '10-50', minScore: 95, performanceWeight: 25, priceWeight: 55, others: 20, minCreditRating: 'BB-', minBondRating: 'BB-', minNoteRating: 'BB-', description: '조달청 10~50억원' },
  { institution: 'pcs', sizeRange: '0.2-10', minScore: 95, performanceWeight: 20, priceWeight: 60, others: 20, minCreditRating: 'BB-', minBondRating: 'BB-', minNoteRating: 'BB-', description: '조달청 2천만~10억원' },
  { institution: 'pcs', sizeRange: '<0.2', minScore: 95, performanceWeight: 10, priceWeight: 70, others: 20, minCreditRating: 'B+', minBondRating: 'B+', minNoteRating: 'B+', description: '조달청 2천만원 미만' },
  { institution: 'lh', sizeRange: '300+', minScore: 95, performanceWeight: 40, priceWeight: 35, others: 25, minCreditRating: 'BBB-', minBondRating: 'BBB-', minNoteRating: 'BBB-', description: 'LH 300억원 이상' },
  { institution: 'lh', sizeRange: '100-300', minScore: 95, performanceWeight: 40, priceWeight: 35, others: 25, minCreditRating: 'BB+', minBondRating: 'BB+', minNoteRating: 'BB+', description: 'LH 100~300억원' },
  { institution: 'lh', sizeRange: '50-100', minScore: 95, performanceWeight: 38, priceWeight: 37, others: 25, minCreditRating: 'BB+', minBondRating: 'BB+', minNoteRating: 'BB+', description: 'LH 50~100억원' },
  { institution: 'lh', sizeRange: '10-50', minScore: 95, performanceWeight: 35, priceWeight: 40, others: 25, minCreditRating: 'BB-', minBondRating: 'BB-', minNoteRating: 'BB-', description: 'LH 10~50억원' },
  { institution: 'lh', sizeRange: '0.2-10', minScore: 95, performanceWeight: 30, priceWeight: 45, others: 25, minCreditRating: 'BB-', minBondRating: 'BB-', minNoteRating: 'BB-', description: 'LH 2천만~10억원' },
  { institution: 'lh', sizeRange: '<0.2', minScore: 95, performanceWeight: 20, priceWeight: 55, others: 25, minCreditRating: 'B+', minBondRating: 'B+', minNoteRating: 'B+', description: 'LH 2천만원 미만' },
  { institution: 'local', sizeRange: '300+', minScore: 92, performanceWeight: 44, priceWeight: 30, others: 26, minCreditRating: 'BB-', minBondRating: 'BB-', minNoteRating: 'BB-', description: '지방자치단체 300억원 이상' },
  { institution: 'local', sizeRange: '100-300', minScore: 92, performanceWeight: 44, priceWeight: 30, others: 26, minCreditRating: 'BB-', minBondRating: 'BB-', minNoteRating: 'BB-', description: '지방자치단체 100~300억원' },
  { institution: 'local', sizeRange: '50-100', minScore: 92, performanceWeight: 42, priceWeight: 32, others: 26, minCreditRating: 'BB-', minBondRating: 'BB-', minNoteRating: 'BB-', description: '지방자치단체 50~100억원' },
  { institution: 'local', sizeRange: '10-50', minScore: 92, performanceWeight: 40, priceWeight: 34, others: 26, minCreditRating: 'BB-', minBondRating: 'BB-', minNoteRating: 'BB-', description: '지방자치단체 10~50억원' },
  { institution: 'local', sizeRange: '0.2-10', minScore: 92, performanceWeight: 35, priceWeight: 39, others: 26, minCreditRating: 'B+', minBondRating: 'B+', minNoteRating: 'B+', description: '지방자치단체 2천만~10억원' },
  { institution: 'local', sizeRange: '<0.2', minScore: 92, performanceWeight: 25, priceWeight: 49, others: 26, minCreditRating: 'B+', minBondRating: 'B+', minNoteRating: 'B+', description: '지방자치단체 2천만원 미만' }
];

async function initializeDB() {
  try {
    const count = await Criteria.countDocuments();
    if (count > 0) {
      console.log(`⚠ 기준 데이터가 이미 ${count}개 존재합니다. 초기화를 건너뜁니다.`);
      process.exit(0);
    }

    await Criteria.insertMany(initialData);
    console.log(`✓ 초기 데이터 저장 완료 (${initialData.length}개 항목)`);
    process.exit(0);
  } catch (err) {
    console.error('✗ 초기 데이터 저장 실패:', err);
    process.exit(1);
  }
}

initializeDB();
