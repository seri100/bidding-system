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

function getFormattedDate(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  const h = String(date.getHours()).padStart(2, '0');
  const mm = String(date.getMinutes()).padStart(2, '0');
  return `${y}${m}${d}${h}${mm}`;
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

async function fetchBidData(operationName, workType) {
  const baseUrl = `http://apis.data.go.kr/1230000/ad/BidPublicInfoService/${operationName}`;
  let totalInserted = 0;
  let totalDuplicate = 0;

  const endDate = new Date();
  const startDate = new Date(endDate.getTime() - 7 * 24 * 60 * 60 * 1000);

  const inqryBgnDt = getFormattedDate(startDate);
  const inqryEndDt = getFormattedDate(endDate);

  console.log(`\n🔍 ${workType} 공고 조회 시작 (${operationName})`);
  console.log(`📅 기간: ${inqryBgnDt} ~ ${inqryEndDt}`);

  for (let page = 1; page <= 5; page++) {
    const params = {
      ServiceKey: API_KEY,
      numOfRows: 100,
      pageNo: page,
      type: 'json',
      inqryDiv: 1,
      inqryBgnDt: inqryBgnDt,
      inqryEndDt: inqryEndDt
    };

    try {
      const response = await axios.get(baseUrl, { params, timeout: 10000 });
      
      let announcements = [];
      if (response.data.response && response.data.response.body) {
        if (Array.isArray(response.data.response.body.items)) {
          announcements = response.data.response.body.items;
        } else if (response.data.response.body.items) {
          announcements = [response.data.response.body.items];
        }
      }
      
      if (!Array.isArray(announcements) || announcements.length === 0) {
        console.log(`✓ ${workType} 페이지 ${page}: 더 이상 데이터 없음`);
        break;
      }

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
            workType: workType,
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

      console.log(`✓ ${workType} 페이지 ${page}: ${announcements.length}개 처리 (신규: ${totalInserted}, 중복: ${totalDuplicate})`);
      await new Promise(resolve => setTimeout(resolve, 300));

    } catch (error) {
      console.error(`❌ ${workType} 페이지 ${page} 오류:`, error.message);
    }
  }

  return { totalInserted, totalDuplicate };
}

async function main() {
  try {
    await mongoose.connect(MONGODB_URI);
    console.log('✓ MongoDB 연결 성공\n');

    let grandTotalInserted = 0;
    let grandTotalDuplicate = 0;

    // 1. 공사 조회
    let result = await fetchBidData('getBidPblancListInfoCnstwkPPSSrch', '공사');
    grandTotalInserted += result.totalInserted;
    grandTotalDuplicate += result.totalDuplicate;

    // 2. 용역 조회
    result = await fetchBidData('getBidPblancListInfoServcPPSSrch', '용역');
    grandTotalInserted += result.totalInserted;
    grandTotalDuplicate += result.totalDuplicate;

    // 3. 물품 조회
    result = await fetchBidData('getBidPblancListInfoThngPPSSrch', '물품');
    grandTotalInserted += result.totalInserted;
    grandTotalDuplicate += result.totalDuplicate;

    // 최종 통계
    const stats = await Announcement.aggregate([
      { $group: { _id: '$workType', count: { $sum: 1 } } },
      { $sort: { count: -1 } }
    ]);

    const agencyStats = await Announcement.aggregate([
      { $group: { _id: '$agencyName', count: { $sum: 1 } } },
      { $sort: { count: -1 } },
      { $limit: 10 }
    ]);

    const totalCount = await Announcement.countDocuments();

    console.log('\n═════════════════════════════════════════');
    console.log('✅ 전체 데이터 수집 완료');
    console.log(`📊 이번 수집 신규: ${grandTotalInserted}개`);
    console.log(`⚠️  중복 제외: ${grandTotalDuplicate}개`);
    console.log(`📈 총 공고 수: ${totalCount}개`);
    console.log('\n업무유형별 분포:');
    stats.forEach(s => console.log(`  ${s._id}: ${s.count}개`));
    console.log('\n기관별 상위 10개:');
    agencyStats.forEach(s => console.log(`  ${s._id}: ${s.count}개`));
    console.log('═════════════════════════════════════════\n');

  } catch (error) {
    console.error('❌ 오류:', error.message);
  } finally {
    await mongoose.disconnect();
  }
}

main();
