const fs = require('fs');
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

async function importG2BData() {
  try {
    if (!fs.existsSync('C:\\bidding-system\\kakao_backup.sql')) {
      console.log('⚠️  kakao_backup.sql 파일을 찾을 수 없습니다.');
      await checkExistingData();
      return;
    }

    const sqlFile = fs.readFileSync('C:\\bidding-system\\kakao_backup.sql', 'utf8');
    
    const valueRegex = /VALUES\s+(\(.*?\))\s*;/gs;
    let match;
    const announcements = [];
    let parseCount = 0;
    let errorCount = 0;

    while ((match = valueRegex.exec(sqlFile)) !== null) {
      const valuesBlock = match[1];
      
      try {
        const jsonMatch = valuesBlock.match(/\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}/);
        
        if (!jsonMatch) {
          console.log(`⚠️  행 ${parseCount + 1}: JSON을 찾을 수 없습니다.`);
          errorCount++;
          continue;
        }

        const jsonStr = jsonMatch[0];
        const rawJson = JSON.parse(jsonStr);

        const announcement = {
          announcementNumber: rawJson.bidNtceNo || '',
          title: rawJson.bidNtceNm || '',
          description: rawJson.ntceKindNm || '',
          agencyName: rawJson.ntceInsttNm || '조달청',
          workType: rawJson.sucsfbidMthdNm ? (rawJson.sucsfbidMthdNm.includes('공사') ? '공사' : '용역') : '용역',
          region: rawJson.cnstrtsiteRgnNm || '전국',
          basicAmount: parseInt(rawJson.presmptPrce) || 0,
          budget: parseInt(rawJson.bdgtAmt) || 0,
          deadline: rawJson.bidClseDt ? new Date(rawJson.bidClseDt) : null,
          createdAt: new Date(),
          updatedAt: new Date()
        };

        if (announcement.announcementNumber && announcement.title) {
          announcements.push(announcement);
          parseCount++;
        }
      } catch (e) {
        console.log(`⚠️  행 ${parseCount + errorCount + 1} 파싱 오류:`, e.message.substring(0, 50));
        errorCount++;
      }
    }

    console.log(`\n📊 파싱 결과: ${parseCount}개 성공, ${errorCount}개 오류`);

    if (parseCount > 0) {
      const existingNos = await Announcement.find({}, { announcementNumber: 1 }).lean();
      const existingSet = new Set(existingNos.map(a => a.announcementNumber));
      
      const newAnnouncements = announcements.filter(a => !existingSet.has(a.announcementNumber));
      
      if (newAnnouncements.length > 0) {
        await Announcement.insertMany(newAnnouncements);
        console.log(`✅ ${newAnnouncements.length}개의 새로운 공고를 저장했습니다.`);
      } else {
        console.log('ℹ️  새로운 공고가 없습니다 (모두 기존 데이터)');
      }
    }

    await checkExistingData();
  } catch (err) {
    console.error('✗ import 실패:', err.message);
    await checkExistingData();
  }
}

async function checkExistingData() {
  try {
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
    byAgency.forEach(item => console.log(`     - ${item._id || '(미정)'}: ${item.count}개`));
    console.log(`\n   업부구분별 분포:`);
    byWorkType.forEach(item => console.log(`     - ${item._id || '(미정)'}: ${item.count}개`));
  } catch (err) {
    console.error('✗ 데이터 조회 실패:', err.message);
  }
}

importG2BData().then(() => {
  mongoose.connection.close();
  process.exit(0);
});
