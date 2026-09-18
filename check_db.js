const mongoose = require('mongoose');

const mongoUri = 'mongodb://localhost:27017/bidding_system';

(async () => {
  try {
    await mongoose.connect(mongoUri, { useNewUrlParser: true, useUnifiedTopology: true });
    console.log('✅ MongoDB 연결 성공\n');

    // 방법 1: 직접 컬렉션에 접근
    const db = mongoose.connection.db;
    
    console.log('📦 컬렉션 데이터 확인:');
    
    // announcements 컬렉션
    const announcementCollection = db.collection('announcements');
    const announcementCount = await announcementCollection.countDocuments();
    console.log(`  📋 announcements: ${announcementCount}개`);
    
    if (announcementCount > 0) {
      const sample = await announcementCollection.findOne();
      console.log('\n  📋 샘플 문서:');
      console.log(JSON.stringify(sample, null, 2).substring(0, 500));
    }

    // 다른 컬렉션들 확인
    console.log('\n📊 전체 컬렉션 통계:');
    const collections = ['announcements', 'companies', 'evaluations', 'users'];
    
    for (const colName of collections) {
      try {
        const col = db.collection(colName);
        const count = await col.countDocuments();
        if (count > 0) {
          console.log(`  ✅ ${colName}: ${count}개`);
        }
      } catch (e) {
        // 무시
      }
    }

    // 모든 인덱스 확인
    console.log('\n🔍 announcements 인덱스:');
    const indexes = await announcementCollection.getIndexes();
    console.log(JSON.stringify(indexes, null, 2));

    await mongoose.disconnect();
    console.log('\n✅ 완료');
    process.exit(0);
  } catch (err) {
    console.error('❌ 오류:', err.message);
    process.exit(1);
  }
})();
