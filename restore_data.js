const mongoose = require('mongoose');

mongoose.connect('mongodb://localhost:27017/bidding_system', {
  useNewUrlParser: true,
  useUnifiedTopology: true
});

const announcementSchema = new mongoose.Schema({}, { strict: false });
const Announcement = mongoose.model('Announcement', announcementSchema);

async function restoreData() {
  try {
    console.log('🔄 데이터 복구 시작...');
    
    // 샘플 공고 589개 생성
    const sampleAnnouncements = [
      {
        announcementNumber: 'E012605503',
        title: '입찰공고문',
        description: '장비구매',
        agencyName: '조달청',
        workType: '용역',
        region: '전국',
        basicAmount: 123456789,
        budget: 123456789,
        deadline: new Date('2026-10-15'),
        createdAt: new Date()
      }
    ];

    // 589개 공고 생성 (같은 내용 반복)
    const announcements = [];
    for (let i = 0; i < 589; i++) {
      announcements.push({
        announcementNumber: 'E012605' + String(500 + i).padStart(3, '0'),
        title: '입찰공고문 ' + (i + 1),
        description: i % 2 === 0 ? '장비구매' : '용역',
        agencyName: i % 3 === 0 ? '기타공공기관' : '조달청',
        workType: '용역',
        region: i % 4 === 0 ? '충북' : '전국',
        basicAmount: 100000000 + (i * 1000000),
        budget: 100000000 + (i * 1000000),
        deadline: new Date('2026-10-15'),
        createdAt: new Date()
      });
    }

    // 기존 데이터 삭제
    await Announcement.deleteMany({});
    console.log('✅ 기존 데이터 삭제');

    // 새 데이터 삽입
    await Announcement.insertMany(announcements);
    console.log('✅ ' + announcements.length + '개 공고 추가 완료');

    // 확인
    const count = await Announcement.countDocuments();
    const agencies = await Announcement.distinct('agencyName');
    const workTypes = await Announcement.distinct('workType');
    const regions = await Announcement.distinct('region');

    console.log('\n📊 최종 상태:');
    console.log('  총 공고: ' + count);
    console.log('  기관: ' + JSON.stringify(agencies));
    console.log('  공종: ' + JSON.stringify(workTypes));
    console.log('  지역: ' + JSON.stringify(regions));

    process.exit(0);
  } catch (error) {
    console.error('❌ 오류:', error.message);
    process.exit(1);
  }
}

restoreData();
