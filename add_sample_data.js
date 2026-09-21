const mongoose = require('mongoose');

const mongoUri = 'mongodb://localhost:27017/bidding_system';
mongoose.connect(mongoUri, { useNewUrlParser: true, useUnifiedTopology: true })
  .then(() => console.log('✅ MongoDB 연결 성공'))
  .catch(err => console.error('✗ MongoDB 연결 실패:', err));

const announcementSchema = new mongoose.Schema({
  announcementNumber: String,
  title: String,
  description: String,
  agencyName: String,
  workType: String,
  region: String,
  basicAmount: Number,
  budget: Number,
  deadline: { type: Date, default: null },
  createdAt: { type: Date, default: Date.now },
  updatedAt: { type: Date, default: Date.now }
}, { strict: false });

const Announcement = mongoose.model('Announcement', announcementSchema);

async function addSampleData() {
  try {
    // 잘못된 데이터 삭제 (옥산신계1리새물래골구거정비공사, 2026-02-06 10:00:00가 업부)
    const deleteResult = await Announcement.deleteOne({ agencyName: '옥산신계1리새물래골구거정비공사' });
    console.log(`🗑️  잘못된 데이터 ${deleteResult.deletedCount}개 삭제됨`);

    const sampleAnnouncements = [
      // 공사 관련 공고들
      {
        announcementNumber: 'G2B-2026-CONST-001',
        title: '[조달청] 서울시 도로포장 공사',
        description: '도로 포장 신설 및 개량 공사',
        agencyName: '조달청',
        workType: '공사',
        region: '서울',
        basicAmount: 50000000,
        budget: 55000000,
        deadline: new Date('2026-03-31'),
        createdAt: new Date(),
        updatedAt: new Date()
      },
      {
        announcementNumber: 'G2B-2026-CONST-002',
        title: '[조달청] 경기도 건물신축 공사',
        description: '행정기관 건물 신축',
        agencyName: '조달청',
        workType: '공사',
        region: '경기도',
        basicAmount: 100000000,
        budget: 110000000,
        deadline: new Date('2026-03-15'),
        createdAt: new Date(),
        updatedAt: new Date()
      },
      {
        announcementNumber: 'G2B-2026-CONST-003',
        title: '[LH] 대전시 아파트 건설 공사',
        description: '공공주택 건설 사업',
        agencyName: 'LH(한국토지주택공사)',
        workType: '공사',
        region: '대전',
        basicAmount: 150000000,
        budget: 165000000,
        deadline: new Date('2026-04-10'),
        createdAt: new Date(),
        updatedAt: new Date()
      },
      {
        announcementNumber: 'G2B-2026-CONST-004',
        title: '[도로공사] 고속도로 확장 공사',
        description: '기존 고속도로 확장 및 개선',
        agencyName: '한국도로공사',
        workType: '공사',
        region: '강원도',
        basicAmount: 200000000,
        budget: 220000000,
        deadline: new Date('2026-05-20'),
        createdAt: new Date(),
        updatedAt: new Date()
      },
      {
        announcementNumber: 'G2B-2026-CONST-005',
        title: '[철도공단] 철도 신선 건설',
        description: '경전선 고속철도 신설 공사',
        agencyName: '국가철도공단',
        workType: '공사',
        region: '경주',
        basicAmount: 300000000,
        budget: 330000000,
        deadline: new Date('2026-06-30'),
        createdAt: new Date(),
        updatedAt: new Date()
      },
      // 물품 관련 공고들
      {
        announcementNumber: 'G2B-2026-GOODS-001',
        title: '[조달청] 의료기기 구매',
        description: '병원용 고급 의료기기 구매',
        agencyName: '조달청',
        workType: '물품',
        region: '서울',
        basicAmount: 10000000,
        budget: 11000000,
        deadline: new Date('2026-02-28'),
        createdAt: new Date(),
        updatedAt: new Date()
      },
      {
        announcementNumber: 'G2B-2026-GOODS-002',
        title: '[경기도] 사무용품 구매',
        description: '도청용 사무용품 및 소모품',
        agencyName: '경기도청',
        workType: '물품',
        region: '경기도',
        basicAmount: 5000000,
        budget: 5500000,
        deadline: new Date('2026-02-20'),
        createdAt: new Date(),
        updatedAt: new Date()
      },
      {
        announcementNumber: 'G2B-2026-GOODS-003',
        title: '[국방부] 군용 차량 부품',
        description: '전술차량 교체용 부품',
        agencyName: '국방부',
        workType: '물품',
        region: '전국',
        basicAmount: 30000000,
        budget: 33000000,
        deadline: new Date('2026-03-10'),
        createdAt: new Date(),
        updatedAt: new Date()
      },
      {
        announcementNumber: 'G2B-2026-GOODS-004',
        title: '[교육청] 학용품 일괄 구매',
        description: '전국 학교용 학용품 및 교과서',
        agencyName: '교육청',
        workType: '물품',
        region: '전국',
        basicAmount: 20000000,
        budget: 22000000,
        deadline: new Date('2026-02-15'),
        createdAt: new Date(),
        updatedAt: new Date()
      },
      // 용역 관련 공고들 (다양한 종류)
      {
        announcementNumber: 'G2B-2026-SERVICE-001',
        title: '[조달청] 시스템 개발 용역',
        description: 'ICT 기반 행정시스템 개발',
        agencyName: '조달청',
        workType: '용역',
        region: '전국',
        basicAmount: 80000000,
        budget: 88000000,
        deadline: new Date('2026-04-15'),
        createdAt: new Date(),
        updatedAt: new Date()
      },
      {
        announcementNumber: 'G2B-2026-SERVICE-002',
        title: '[서울시] 도시계획 컨설팅 용역',
        description: '스마트시티 구축 컨설팅',
        agencyName: '서울시청',
        workType: '용역',
        region: '서울',
        basicAmount: 40000000,
        budget: 44000000,
        deadline: new Date('2026-03-20'),
        createdAt: new Date(),
        updatedAt: new Date()
      },
      {
        announcementNumber: 'G2B-2026-SERVICE-003',
        title: '[환경부] 환경영향평가 용역',
        description: '신규 개발사업 환경영향평가',
        agencyName: '환경부',
        workType: '용역',
        region: '전국',
        basicAmount: 25000000,
        budget: 27500000,
        deadline: new Date('2026-03-05'),
        createdAt: new Date(),
        updatedAt: new Date()
      },
      {
        announcementNumber: 'G2B-2026-SERVICE-004',
        title: '[보건복지부] 정책연구 용역',
        description: '사회복지정책 연구 및 분석',
        agencyName: '보건복지부',
        workType: '용역',
        region: '전국',
        basicAmount: 35000000,
        budget: 38500000,
        deadline: new Date('2026-03-25'),
        createdAt: new Date(),
        updatedAt: new Date()
      }
    ];

    // 중복 체크
    const existingNos = await Announcement.find({}, { announcementNumber: 1 }).lean();
    const existingSet = new Set(existingNos.map(a => a.announcementNumber));
    
    const newAnnouncements = sampleAnnouncements.filter(a => !existingSet.has(a.announcementNumber));

    if (newAnnouncements.length > 0) {
      await Announcement.insertMany(newAnnouncements);
      console.log(`✅ ${newAnnouncements.length}개의 샘플 공고 추가됨`);
    }

    // 최종 통계
    const count = await Announcement.countDocuments();
    const byAgency = await Announcement.aggregate([
      { $group: { _id: '$agencyName', count: { $sum: 1 } } },
      { $sort: { count: -1 } }
    ]);
    const byWorkType = await Announcement.aggregate([
      { $group: { _id: '$workType', count: { $sum: 1 } } },
      { $sort: { count: -1 } }
    ]);

    console.log(`\n📊 최종 데이터베이스 상태:`);
    console.log(`   총 공고 수: ${count}개`);
    console.log(`\n   기관별 분포:`);
    byAgency.forEach(item => console.log(`     - ${item._id}: ${item.count}개`));
    console.log(`\n   업부구분별 분포:`);
    byWorkType.forEach(item => console.log(`     - ${item._id}: ${item.count}개`));
  } catch (err) {
    console.error('✗ 오류:', err.message);
  }
}

addSampleData().then(() => {
  mongoose.connection.close();
  process.exit(0);
});
