const mongoose = require('mongoose');
const axios = require('axios');
require('dotenv').config({ path: 'C:\\bidding-system\\.env.raspberry' });

const MONGODB_URI = process.env.MONGODB_URI || 'mongodb://localhost:27017/bidding_system';
const API_KEY = process.env.PUBLIC_DATA_API_KEY;

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
  source: { type: String, default: 'public_data_portal' },
  externalId: String,
  createdAt: { type: Date, default: Date.now }
}, { strict: false });

const Announcement = mongoose.model('Announcement', announcementSchema);

// 정확한 날짜 포맷: YYYYMMDDHHMM
function getFormattedDate(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  const h = String(date.getHours()).padStart(2, '0');
  const mm = String(date.getMinutes()).padStart(2, '0');
  return `${y}${m}${d}${h}${mm}`;
}

async function fetchPublicDataAnnouncements() {
  try {
    await mongoose.connect(MONGODB_URI);
    console.log('✓ MongoDB 연결 성공');

    // 나라장터 검색조건에 의한 공사조회
    const baseUrl = 'http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwkPPSSrch';
    let totalInserted = 0;
    let totalDuplicate = 0;

    // 최근 7일 데이터 조회
    const endDate = new Date();
    const startDate = new Date(endDate.getTime() - 7 * 24 * 60 * 60 * 1000);

    const inqryBgnDt = getFormattedDate(startDate);
    const inqryEndDt = getFormattedDate(endDate);

    console.log(`📅 조회 기간: ${inqryBgnDt} ~ ${inqryEndDt}`);

    for (let page = 1; page <= 10; page++) {
      console.log(`\n📄 페이지 ${page} 데이터 조회 중...`);

      const params = {
        ServiceKey: API_KEY,
        numOfRows: 100,
        pageNo: page,
        type: 'json',
        inqryDiv: 1,  // 1: 공고게시일시 기준
        inqryBgnDt: inqryBgnDt,
        inqryEndDt: inqryEndDt
      };

      try {
        const response = await axios.get(baseUrl, { params, timeout: 10000 });
        
        console.log('응답 상태:', response.status);
        
        if (!response.data) {
          console.log('⚠️  응답 데이터 없음');
          break;
        }

        // API 응답 구조 분석
        let announcements = [];
        
        if (response.data.response && response.data.response.body) {
          if (Array.isArray(response.data.response.body.items)) {
            announcements = response.data.response.body.items;
          } else if (response.data.response.body.items) {
            announcements = [response.data.response.body.items];
          }
        }
        
        if (!Array.isArray(announcements) || announcements.length === 0) {
          console.log('✓ 더 이상 데이터 없음');
          break;
        }

        console.log(`📥 ${announcements.length}개 공고 수신`);

        for (const item of announcements) {
          const externalId = item.bidNtceNo;
          
          if (!externalId) continue;
          
          const existing = await Announcement.findOne({ externalId });
          
          if (existing) {
            totalDuplicate++;
          } else {
            const announcement = new Announcement({
              announcementNumber: externalId,
              title: item.bidNtceNm || '제목 없음',
              description: item.bidNtceNm || '',
              agencyName: item.ntceInsttNm || '조달청',
              workType: '공사',
              region: extractRegion(item.prtcptLmtRgnNm),
              basicAmount: parseInt(item.presmptPrce || 0),
              budget: parseInt(item.presmptPrce || 0),
              deadline: new Date(item.bidClseDt || Date.now()),
              externalId: externalId,
              source: 'public_data_portal',
              rawData: item
            });

            await announcement.save();
            totalInserted++;
          }
        }

        console.log(`✓ 페이지 ${page}: ${announcements.length}개 처리`);
        await new Promise(resolve => setTimeout(resolve, 500));

      } catch (error) {
        console.error(`❌ 페이지 ${page} 오류:`, error.message);
        if (error.response?.status === 429) {
          console.log('⏳ API 호출 제한 - 5초 대기...');
          await new Promise(resolve => setTimeout(resolve, 5000));
        }
        if (error.response?.data) {
          console.log('📋 오류 응답:', JSON.stringify(error.response.data).substring(0, 300));
        }
      }
    }

    const stats = await Announcement.aggregate([
      { $group: { _id: '$agencyName', count: { $sum: 1 } } },
      { $sort: { count: -1 } }
    ]);

    const totalCount = await Announcement.countDocuments();

    console.log('\n═════════════════════════════════════════');
    console.log('✅ 데이터 수집 완료');
    console.log(`📊 신규 삽입: ${totalInserted}개`);
    console.log(`⚠️  중복: ${totalDuplicate}개`);
    console.log(`📈 총 공고 수: ${totalCount}개`);
    console.log('═════════════════════════════════════════');

  } catch (error) {
    console.error('❌ 오류:', error.message);
  } finally {
    await mongoose.disconnect();
  }
}

function extractRegion(regionName) {
  if (!regionName) return null;
  const regions = ['서울', '부산', '대구', '인천', '광주', '대전', '울산', '세종',
    '경기도', '강원도', '충청북도', '충청남도', '전라북도', '전라남도', '경상북도', '경상남도', '제주도'];
  
  for (let r of regions) {
    if (regionName.includes(r)) return r;
  }
  return regionName.length <= 10 ? regionName : null;
}

fetchPublicDataAnnouncements();
