const mongoose = require('mongoose');
const axios = require('axios');
require('dotenv').config({ path: 'C:\\bidding-system\\.env.raspberry' });

const MONGODB_URI = process.env.MONGODB_URI || 'mongodb://localhost:27017/bidding_system';
const API_KEY = process.env.PUBLIC_DATA_API_KEY;

mongoose.connect(MONGODB_URI, { useNewUrlParser: true, useUnifiedTopology: true })
  .then(async () => {
    const announcementSchema = new mongoose.Schema({}, { strict: false });
    const Announcement = mongoose.model('Announcement', announcementSchema);
    
    console.log('📥 공공데이터포털에서 실제 데이터 수집 중...\n');

    const url = 'https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwk';
    
    try {
      const resp = await axios.get(url, {
        params: {
          serviceKey: API_KEY,
          numOfRows: 10,
          pageNo: 1,
          type: 'json',
          inqryDiv: 1,
          inqryBgnDt: '202609220000',
          inqryEndDt: '202609222359'
        },
        timeout: 15000
      });

      const items = resp.data?.응답?.몸?.항목 || [];
      
      if (!items || items.length === 0) {
        console.log('❌ 데이터가 없습니다.');
        process.exit(1);
      }

      console.log(`📊 수신한 항목 수: ${items.length}개\n`);

      let totalInserted = 0;

      for (const item of items) {
        try {
          const externalId = item.bidNtceNo;
          
          const exists = await Announcement.findOne({ announcementNumber: externalId });
          if (exists) continue;

          const doc = new Announcement({
            announcementNumber: externalId,
            title: item.bidNtceNm || '제목없음',
            description: item.ntceKindNm || '',
            agencyName: item.ntceInsttNm || '미정',
            workType: item.mainCnsttyNm || '일반공사',
            region: item.cnstrtsiteRgnNm || '전국',
            basicAmount: parseInt(item.presmptPrce) || 0,
            budget: parseInt(item.bdgtAmt) || 0,
            deadline: item.bidClseDt ? new Date(item.bidClseDt) : null,
            createdAt: new Date()
          });
          
          await doc.save();
          totalInserted++;
          console.log(`✅ [${totalInserted}] ${item.bidNtceNm.substring(0, 50)}`);
        } catch (err) {
          console.error(`❌ 저장 오류:`, err.message);
        }
      }

      const totalCount = await Announcement.countDocuments();
      console.log(`\n${'='.repeat(60)}`);
      console.log(`✅ 실제 공공데이터 수집 완료!`);
      console.log(`📊 저장된 공고 수: ${totalInserted}개`);
      console.log(`📊 데이터베이스 총 공고 수: ${totalCount}개`);
      console.log(`${'='.repeat(60)}\n`);
      
      process.exit(0);
    } catch (error) {
      console.error('❌ API 오류:', error.response?.data || error.message);
      process.exit(1);
    }
  })
  .catch(err => {
    console.error('❌ MongoDB 연결 오류:', err);
    process.exit(1);
  });
