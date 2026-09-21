const mongoose = require('mongoose');

const mongoUri = 'mongodb://localhost:27017/bidding_system';
mongoose.connect(mongoUri, { useNewUrlParser: true, useUnifiedTopology: true })
  .then(() => console.log('✅ MongoDB 연결 성공'))
  .catch(err => console.error('✗ MongoDB 연결 실패:', err));

const announcementSchema = new mongoose.Schema({}, { strict: false });
const Announcement = mongoose.model('Announcement', announcementSchema);

async function checkData() {
  try {
    const count = await Announcement.countDocuments();
    console.log(`\n📊 현재 데이터베이스 상태:`);
    console.log(`   총 공고 수: ${count}개`);
    
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
    
    console.log(`\n   기관별 분포:`);
    byAgency.forEach(item => console.log(`     - ${item._id || '(미정)'}: ${item.count}개`));
    
    console.log(`\n   업부구분별 분포:`);
    byWorkType.forEach(item => console.log(`     - ${item._id || '(미정)'}: ${item.count}개`));
    
    console.log(`\n   지역별 분포:`);
    byRegion.forEach(item => console.log(`     - ${item._id || '(미정)'}: ${item.count}개`));
    
    // 샘플 공고 1개 출력
    const sample = await Announcement.findOne();
    console.log(`\n📋 샘플 공고 (첫 번째):`);
    console.log(`   기관: ${sample.agencyName}`);
    console.log(`   제목: ${sample.title}`);
    console.log(`   업부: ${sample.workType}`);
    console.log(`   지역: ${sample.region}`);
    
  } catch (err) {
    console.error('✗ 오류:', err.message);
  }
}

checkData().then(() => {
  mongoose.connection.close();
  process.exit(0);
});
