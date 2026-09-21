const mongoose = require('mongoose');
const mongoUri = 'mongodb://localhost:27017/bidding_system';

mongoose.connect(mongoUri, { useNewUrlParser: true, useUnifiedTopology: true });

const announcementSchema = new mongoose.Schema({}, { strict: false });
const Announcement = mongoose.model('Announcement', announcementSchema);

async function addMissingFields() {
  try {
    console.log('🔄 기존 공고에 필드 추가 중...');
    
    // 기관 매핑 (description 또는 title 기반)
    const agencyMap = {
      '한국전력': '한국전력공사',
      '수력원자력': '한국수력원자력',
      '철도': '국가철도공단',
      'LH': 'LH',
      '도로': '한국도로공사',
      '조달': '조달청',
      '의료원': '기타공공기관',
      '공사': '기타공공기관'
    };
    
    // 공종 매핑
    const workTypeMap = {
      '구매': '용역',
      '설치': '용역',
      '용역': '용역',
      '건설': '건설',
      '설계': '용역',
      '용품': '용품'
    };
    
    const announcements = await Announcement.find().lean();
    let updated = 0;
    
    for (const ann of announcements) {
      let agencyName = '조달청'; // 기본값
      let workType = '용역'; // 기본값
      
      const searchText = `${ann.title || ''} ${ann.description || ''}`.toLowerCase();
      
      // 기관명 추출
      for (const [key, value] of Object.entries(agencyMap)) {
        if (searchText.includes(key.toLowerCase())) {
          agencyName = value;
          break;
        }
      }
      
      // 공종 추출
      for (const [key, value] of Object.entries(workTypeMap)) {
        if (searchText.includes(key.toLowerCase())) {
          workType = value;
          break;
        }
      }
      
      // 업데이트
      await Announcement.updateOne(
        { _id: ann._id },
        {
          $set: {
            agencyName: agencyName,
            workType: workType,
            basicAmount: ann.budget || 0,
            announcementNumber: ann._id.toString().substring(0, 12)
          }
        }
      );
      
      updated++;
      if (updated % 100 === 0) {
        console.log(`✅ ${updated}개 공고 처리 완료`);
      }
    }
    
    console.log(`\n✅ 모든 ${updated}개 공고에 필드 추가 완료`);
    
    // 샘플 확인
    const sample = await Announcement.findOne().lean();
    console.log('\n📋 업데이트된 샘플:');
    console.log(JSON.stringify(sample, null, 2));
    
    process.exit(0);
  } catch (err) {
    console.error('❌ 오류:', err.message);
    process.exit(1);
  }
}

addMissingFields();
