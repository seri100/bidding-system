const mongoose = require('mongoose');
const axios = require('axios');
const cheerio = require('cheerio');
require('dotenv').config({ path: 'C:\\bidding-system\\.env.raspberry' });

const MONGODB_URI = process.env.MONGODB_URI || 'mongodb://localhost:27017/bidding_system';

mongoose.connect(MONGODB_URI, { useNewUrlParser: true, useUnifiedTopology: true })
  .then(async () => {
    const announcementSchema = new mongoose.Schema({}, { strict: false });
    const Announcement = mongoose.model('Announcement', announcementSchema);
    
    console.log('🗑️  기존 데이터 삭제 중...');
    await Announcement.deleteMany({});
    console.log('✅ 삭제 완료\n');

    console.log('🌐 나라장터 웹 크롤링 시작...\n');

    // 나라장터 공고 검색 URL
    // 기본 조건: 과거 30일, 모든 지역, 모든 업무구분
    const now = new Date();
    const pastDate = new Date(now - 30 * 24 * 60 * 60 * 1000);
    
    const startDate = `${pastDate.getFullYear()}-${String(pastDate.getMonth() + 1).padStart(2, '0')}-${String(pastDate.getDate()).padStart(2, '0')}`;
    const endDate = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;

    console.log(`📅 수집 기간: ${startDate} ~ ${endDate}\n`);

    const g2bUrl = 'https://www.g2b.go.kr/BidSearchSevice';

    let totalInserted = 0;
    let totalPages = 0;

    // 최대 5페이지까지 크롤링
    for (let pageNum = 1; pageNum <= 5; pageNum++) {
      try {
        console.log(`📄 페이지 ${pageNum} 크롤링 중...`);

        // 나라장터 API 방식 (JSON 응답)
        const url = `https://www.g2b.go.kr/es/main/retrievePublicNoticeJson.do?pageIndex=${pageNum}&pageSize=100&orderBy=PUBLISH_DATE&orderByType=DESC`;

        const response = await axios.get(url, {
          headers: {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
          },
          timeout: 15000
        });

        const data = response.data;
        
        if (!data || !data.resultList || data.resultList.length === 0) {
          console.log(`  ℹ️  페이지 ${pageNum}: 데이터 없음 - 크롤링 종료\n`);
          break;
        }

        console.log(`  ✅ ${data.resultList.length}개 항목 수신\n`);
        totalPages++;

        for (const item of data.resultList) {
          try {
            // 마감일이 과거인 항목 제외
            if (item.bidClseDt) {
              const deadline = new Date(item.bidClseDt);
              if (deadline < pastDate) continue;
            }

            const externalId = item.bidNtceNo || item.BIDNTCENO;
            if (!externalId) continue;

            const exists = await Announcement.findOne({ announcementNumber: externalId });
            if (exists) continue;

            const doc = new Announcement({
              announcementNumber: externalId,
              title: item.bidNtceNm || item.BIDNTCENM || '제목없음',
              description: item.ntceKindNm || item.NTCEKINDNM || '',
              agencyName: item.ntceInsttNm || item.NTCEINSTTNM || '미정',
              workType: item.mainCnsttyNm || item.MAINCNSTTYNM || '일반공사',
              region: item.cnstrtsiteRgnNm || item.CNSTRSITERGNMM || '전국',
              basicAmount: parseInt(item.presmptPrce || item.PRESEMPTPRCE) || 0,
              budget: parseInt(item.bdgtAmt || item.BDGTAMT) || 0,
              deadline: item.bidClseDt ? new Date(item.bidClseDt) : null,
              createdAt: new Date()
            });
            
            await doc.save();
            totalInserted++;

            if (totalInserted % 50 === 0) {
              console.log(`  📦 누적: ${totalInserted}개 저장됨...`);
            }
          } catch (err) {
            // 개별 항목 오류는 무시하고 계속
          }
        }

        // Rate limit 준수 (1초 대기)
        await new Promise(r => setTimeout(r, 1000));

      } catch (error) {
        console.error(`  ❌ 페이지 ${pageNum} 오류:`, error.message);
        
        // 연속 실패 시 중단
        if (pageNum > 1) {
          break;
        }
      }
    }

    const totalCount = await Announcement.countDocuments();
    
    console.log(`\n${'='.repeat(70)}`);
    console.log(`✅ 나라장터 웹 크롤링 완료!`);
    console.log(`📊 수집 페이지: ${totalPages}페이지`);
    console.log(`📊 새로 추가됨: ${totalInserted}개`);
    console.log(`📊 데이터베이스 총 공고 수: ${totalCount}개`);
    console.log(`${'='.repeat(70)}\n`);

    if (totalCount === 0) {
      console.log('⚠️  경고: 데이터가 없습니다. 나라장터 접근을 확인하세요.\n');
    }
    
    process.exit(0);
  })
  .catch(err => {
    console.error('❌ MongoDB 연결 오류:', err);
    process.exit(1);
  });
