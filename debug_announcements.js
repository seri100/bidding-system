const mongoose = require('mongoose');
const mongoUri = 'mongodb://localhost:27017/bidding_system';

mongoose.connect(mongoUri, { useNewUrlParser: true, useUnifiedTopology: true });

const announcementSchema = new mongoose.Schema({}, { strict: false });
const Announcement = mongoose.model('Announcement', announcementSchema);

async function debugData() {
  try {
    const count = await Announcement.countDocuments();
    console.log(`📊 MongoDB 공고 총 개수: ${count}`);
    
    // 첫 번째 공고 샘플 조회
    const sample = await Announcement.findOne().lean();
    console.log('\n📋 샘플 공고 구조:');
    console.log(JSON.stringify(sample, null, 2));
    
    // 필드 목록 추출
    if (sample) {
      console.log('\n🔍 포함된 필드:');
      console.log(Object.keys(sample).join(', '));
    }
    
    process.exit(0);
  } catch (err) {
    console.error('❌ 오류:', err.message);
    process.exit(1);
  }
}

debugData();
