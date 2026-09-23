const mongoose = require('mongoose');
require('dotenv').config({ path: 'C:\\bidding-system\\.env.raspberry' });

const MONGODB_URI = process.env.MONGODB_URI || 'mongodb://localhost:27017/bidding_system';

mongoose.connect(MONGODB_URI, { useNewUrlParser: true, useUnifiedTopology: true })
  .then(async () => {
    const announcementSchema = new mongoose.Schema({}, { strict: false });
    const Announcement = mongoose.model('Announcement', announcementSchema);
    
    await Announcement.deleteMany({});
    console.log('✅ 데이터 삭제 완료');
    process.exit(0);
  })
  .catch(err => {
    console.error('❌ 오류:', err);
    process.exit(1);
  });
