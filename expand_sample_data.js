const mongoose = require('mongoose');

// MongoDB 연결
const mongoUri = 'mongodb://localhost:27017/bidding_system';
mongoose.connect(mongoUri, { useNewUrlParser: true, useUnifiedTopology: true });

// 공고 스키마
const announcementSchema = new mongoose.Schema({
  announcementNumber: String,
  title: String,
  description: String,
  agencyName: String,
  workType: String,
  region: String,
  basicAmount: Number,
  budget: Number,
  deadline: Date,
  createdAt: { type: Date, default: Date.now },
  updatedAt: { type: Date, default: Date.now }
}, { strict: false });

const Announcement = mongoose.model('Announcement', announcementSchema);

// 확장된 샘플 데이터 생성
const expandedData = [
  // ===== LH (한국토지주택공사) =====
  { announcementNumber: 'LH-2026-001', title: '[LH] 부산 아파트 건설 공사', description: '공공주택 건설', agencyName: 'LH(한국토지주택공사)', workType: '공사', region: '부산', basicAmount: 250000000, budget: 275000000, deadline: new Date('2026-05-15') },
  { announcementNumber: 'LH-2026-002', title: '[LH] 대구 주거단지 조성 공사', description: '신규 주거지역 개발', agencyName: 'LH(한국토지주택공사)', workType: '공사', region: '대구', basicAmount: 180000000, budget: 198000000, deadline: new Date('2026-04-20') },
  { announcementNumber: 'LH-2026-003', title: '[LH] 주택관리 시스템 개발', description: 'IT 기반 주택관리 솔루션', agencyName: 'LH(한국토지주택공사)', workType: '용역', region: '전국', basicAmount: 60000000, budget: 66000000, deadline: new Date('2026-03-30') },
  { announcementNumber: 'LH-2026-004', title: '[LH] 건설 장비 임차', description: '중장비 및 건설장비 공급', agencyName: 'LH(한국토지주택공사)', workType: '물품', region: '경기도', basicAmount: 45000000, budget: 49500000, deadline: new Date('2026-02-28') },

  // ===== 한국도로공사 =====
  { announcementNumber: 'ROAD-2026-001', title: '[도로공사] 경부 고속도로 개선', description: '노후 도로 개선 공사', agencyName: '한국도로공사', workType: '공사', region: '경주', basicAmount: 320000000, budget: 352000000, deadline: new Date('2026-06-10') },
  { announcementNumber: 'ROAD-2026-002', title: '[도로공사] 중부 고속도로 확장', description: '도로 확장 및 개선', agencyName: '한국도로공사', workType: '공사', region: '강원도', basicAmount: 280000000, budget: 308000000, deadline: new Date('2026-05-25') },
  { announcementNumber: 'ROAD-2026-003', title: '[도로공사] 교통 모니터링 시스템', description: '지능형 교통 관제 시스템', agencyName: '한국도로공사', workType: '용역', region: '전국', basicAmount: 75000000, budget: 82500000, deadline: new Date('2026-04-15') },
  { announcementNumber: 'ROAD-2026-004', title: '[도로공사] 포장재료 공급', description: '도로 포장용 아스팔트 및 자재', agencyName: '한국도로공사', workType: '물품', region: '충북', basicAmount: 55000000, budget: 60500000, deadline: new Date('2026-03-20') },

  // ===== 국가철도공단 =====
  { announcementNumber: 'KORAIL-2026-001', title: '[철도공단] 경전선 복선화 공사', description: '기존 철도 복선화', agencyName: '국가철도공단', workType: '공사', region: '경주', basicAmount: 450000000, budget: 495000000, deadline: new Date('2026-07-10') },
  { announcementNumber: 'KORAIL-2026-002', title: '[철도공단] 신분당선 확장 공사', description: '지하철 신규 노선 건설', agencyName: '국가철도공단', workType: '공사', region: '서울', basicAmount: 380000000, budget: 418000000, deadline: new Date('2026-06-20') },
  { announcementNumber: 'KORAIL-2026-003', title: '[철도공단] 기관차 정비 용역', description: '철도 기관차 유지보수', agencyName: '국가철도공단', workType: '용역', region: '대전', basicAmount: 85000000, budget: 93500000, deadline: new Date('2026-04-10') },
  { announcementNumber: 'KORAIL-2026-004', title: '[철도공단] 철도 부품 공급', description: '철도차량 부품 및 소모품', agencyName: '국가철도공단', workType: '물품', region: '전국', basicAmount: 65000000, budget: 71500000, deadline: new Date('2026-03-15') },

  // ===== 조달청 추가 공고 =====
  { announcementNumber: 'G2B-2026-010', title: '[조달청] 정부청사 개축', description: '노후 청사 건축', agencyName: '조달청', workType: '공사', region: '서울', basicAmount: 280000000, budget: 308000000, deadline: new Date('2026-05-30') },
  { announcementNumber: 'G2B-2026-011', title: '[조달청] 공무원 교육 용역', description: '정부 직원 교육 및 훈련', agencyName: '조달청', workType: '용역', region: '전국', basicAmount: 45000000, budget: 49500000, deadline: new Date('2026-03-25') },
  { announcementNumber: 'G2B-2026-012', title: '[조달청] 사무기기 일괄구매', description: '정부기관용 사무 기기', agencyName: '조달청', workType: '물품', region: '전국', basicAmount: 38000000, budget: 41800000, deadline: new Date('2026-02-18') },
  { announcementNumber: 'G2B-2026-013', title: '[조달청] 정보보안 컨설팅', description: '정부 사이버 보안 용역', agencyName: '조달청', workType: '용역', region: '서울', basicAmount: 55000000, budget: 60500000, deadline: new Date('2026-04-05') },

  // ===== 환경부 =====
  { announcementNumber: 'ENV-2026-001', title: '[환경부] 수질 정화 시설 건설', description: '환경오염 방지 시설', agencyName: '환경부', workType: '공사', region: '대전', basicAmount: 220000000, budget: 242000000, deadline: new Date('2026-05-20') },
  { announcementNumber: 'ENV-2026-002', title: '[환경부] 대기 모니터링 용역', description: '대기질 측정 및 분석', agencyName: '환경부', workType: '용역', region: '전국', basicAmount: 42000000, budget: 46200000, deadline: new Date('2026-03-28') },
  { announcementNumber: 'ENV-2026-003', title: '[환경부] 환경 장비 공급', description: '환경 측정 장비 및 기기', agencyName: '환경부', workType: '물품', region: '서울', basicAmount: 35000000, budget: 38500000, deadline: new Date('2026-02-25') },

  // ===== 보건복지부 =====
  { announcementNumber: 'MOHW-2026-001', title: '[보건복지부] 의료시설 건설', description: '보건소 신축 공사', agencyName: '보건복지부', workType: '공사', region: '부산', basicAmount: 195000000, budget: 214500000, deadline: new Date('2026-05-15') },
  { announcementNumber: 'MOHW-2026-002', title: '[보건복지부] 사회복지 정책 연구', description: '복지 정책 개발 용역', agencyName: '보건복지부', workType: '용역', region: '전국', basicAmount: 48000000, budget: 52800000, deadline: new Date('2026-03-20') },
  { announcementNumber: 'MOHW-2026-003', title: '[보건복지부] 의료용품 공급', description: '보건시설용 의료 소모품', agencyName: '보건복지부', workType: '물품', region: '대구', basicAmount: 32000000, budget: 35200000, deadline: new Date('2026-02-20') },

  // ===== 국방부 =====
  { announcementNumber: 'MOD-2026-001', title: '[국방부] 군 막사 신축', description: '군부대 숙영시설 건설', agencyName: '국방부', workType: '공사', region: '강원도', basicAmount: 350000000, budget: 385000000, deadline: new Date('2026-06-15') },
  { announcementNumber: 'MOD-2026-002', title: '[국방부] 국방 정보시스템 구축', description: '군 통신망 및 정보망', agencyName: '국방부', workType: '용역', region: '서울', basicAmount: 95000000, budget: 104500000, deadline: new Date('2026-04-25') },
  { announcementNumber: 'MOD-2026-003', title: '[국방부] 군용 전자장비', description: '군 통신 및 전자장비', agencyName: '국방부', workType: '물품', region: '전국', basicAmount: 78000000, budget: 85800000, deadline: new Date('2026-03-10') },

  // ===== 경기도청 =====
  { announcementNumber: 'GGG-2026-001', title: '[경기도] 지방도로 개선', description: '도내 도로 포장 및 확장', agencyName: '경기도청', workType: '공사', region: '경기도', basicAmount: 165000000, budget: 181500000, deadline: new Date('2026-05-10') },
  { announcementNumber: 'GGG-2026-002', title: '[경기도] 도시계획 컨설팅', description: '경기도 도시 발전 전략', agencyName: '경기도청', workType: '용역', region: '경기도', basicAmount: 52000000, budget: 57200000, deadline: new Date('2026-03-25') },
  { announcementNumber: 'GGG-2026-003', title: '[경기도] 공용 물품 구매', description: '도청 및 산하기관용 물품', agencyName: '경기도청', workType: '물품', region: '경기도', basicAmount: 28000000, budget: 30800000, deadline: new Date('2026-02-15') },

  // ===== 서울시청 =====
  { announcementNumber: 'SEOUL-2026-001', title: '[서울시] 지하철역 개선', description: '지하철역 시설 개선 공사', agencyName: '서울시청', workType: '공사', region: '서울', basicAmount: 240000000, budget: 264000000, deadline: new Date('2026-05-25') },
  { announcementNumber: 'SEOUL-2026-002', title: '[서울시] 스마트 도시 구축', description: '서울 스마트시티 프로젝트', agencyName: '서울시청', workType: '용역', region: '서울', basicAmount: 68000000, budget: 74800000, deadline: new Date('2026-04-10') },
  { announcementNumber: 'SEOUL-2026-003', title: '[서울시] 공원 시설물 공급', description: '공원 및 광장 시설물', agencyName: '서울시청', workType: '물품', region: '서울', basicAmount: 25000000, budget: 27500000, deadline: new Date('2026-02-28') },

  // ===== 교육청 =====
  { announcementNumber: 'EDU-2026-001', title: '[교육청] 학교 신축', description: '신규 초등학교 건설', agencyName: '교육청', workType: '공사', region: '경기도', basicAmount: 185000000, budget: 203500000, deadline: new Date('2026-05-20') },
  { announcementNumber: 'EDU-2026-002', title: '[교육청] 교육정책 연구', description: '교육 혁신 정책 용역', agencyName: '교육청', workType: '용역', region: '전국', basicAmount: 38000000, budget: 41800000, deadline: new Date('2026-03-30') },
  { announcementNumber: 'EDU-2026-003', title: '[교육청] 교과서 및 교구', description: '학교용 교과서 및 교육용품', agencyName: '교육청', workType: '물품', region: '전국', basicAmount: 58000000, budget: 63800000, deadline: new Date('2026-02-22') },

  // ===== 기타공공기관 추가 =====
  { announcementNumber: 'OTHER-2026-001', title: '[공공기관] 시설 유지보수', description: '공공시설 일반 보수', agencyName: '기타공공기관', workType: '공사', region: '충북', basicAmount: 85000000, budget: 93500000, deadline: new Date('2026-04-15') },
  { announcementNumber: 'OTHER-2026-002', title: '[공공기관] 성능평가 용역', description: '공공기관 성과 평가', agencyName: '기타공공기관', workType: '용역', region: '서울', basicAmount: 28000000, budget: 30800000, deadline: new Date('2026-03-10') }
];

// 중복 확인 후 삽입
async function insertExpandedData() {
  try {
    console.log('📊 확장 데이터 삽입 시작...\n');
    
    let insertedCount = 0;
    let duplicateCount = 0;

    for (const data of expandedData) {
      const exists = await Announcement.findOne({ announcementNumber: data.announcementNumber });
      
      if (!exists) {
        await Announcement.create(data);
        insertedCount++;
        console.log(`✅ 삽입: ${data.announcementNumber} - ${data.title}`);
      } else {
        duplicateCount++;
        console.log(`⏭️  중복: ${data.announcementNumber}`);
      }
    }

    console.log('\n📈 삽입 결과:');
    console.log(`  새로운 공고: ${insertedCount}개`);
    console.log(`  중복된 공고: ${duplicateCount}개`);

    // 최종 통계
    const total = await Announcement.countDocuments();
    const byAgency = await Announcement.aggregate([
      { $group: { _id: '$agencyName', count: { $sum: 1 } } },
      { $sort: { count: -1 } }
    ]);
    const byWorkType = await Announcement.aggregate([
      { $group: { _id: '$workType', count: { $sum: 1 } } },
      { $sort: { count: -1 } }
    ]);
    const byRegion = await Announcement.aggregate([
      { $group: { _id: '$region', count: { $sum: 1 } } },
      { $sort: { count: -1 } }
    ]);

    console.log('\n📊 최종 데이터베이스 통계:');
    console.log(`  총 공고: ${total}개`);
    
    console.log('\n기관별 분포:');
    byAgency.forEach(item => {
      console.log(`  - ${item._id}: ${item.count}개`);
    });
    
    console.log('\n업무구분별 분포:');
    byWorkType.forEach(item => {
      console.log(`  - ${item._id}: ${item.count}개`);
    });
    
    console.log('\n지역별 분포:');
    byRegion.forEach(item => {
      console.log(`  - ${item._id || '(미정)'}: ${item.count}개`);
    });

    mongoose.connection.close();
    console.log('\n✅ 데이터 삽입 완료!');
  } catch (error) {
    console.error('❌ 오류:', error.message);
    mongoose.connection.close();
  }
}

mongoose.connection.on('connected', () => {
  console.log('✅ MongoDB 연결 성공\n');
  insertExpandedData();
});
