const axios = require('axios');
const mongoose = require('mongoose');
require('dotenv').config({ path: 'C:\\bidding-system\\.env.raspberry' });

const API_KEY = process.env.PUBLIC_DATA_API_KEY;
const MONGODB_URI = process.env.MONGODB_URI || 'mongodb://localhost:27017/bidding_system';

// MongoDB 연결
mongoose.connect(MONGODB_URI, { useNewUrlParser: true, useUnifiedTopology: true })
  .then(async () => {
    console.log('✅ MongoDB 연결 성공\n');
    
    const Announcement = mongoose.model('Announcement', new mongoose.Schema({}, { strict: false }));
    
    // 기존 데이터 삭제
    console.log('🗑️  기존 데이터 삭제 중...');
    const deleteResult = await Announcement.deleteMany({});
    console.log(`✅ ${deleteResult.deletedCount}개 삭제됨\n`);
    
    // 수집 기간 설정 (지난 30일)
    const now = new Date();
    const pastDate = new Date(now - 30 * 24 * 60 * 60 * 1000);
    
    function formatDateForAPI(d) {
      return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}0000`;
    }
    
    const inqryBgnDt = formatDateForAPI(pastDate);
    const inqryEndDt = formatDateForAPI(now).replace('0000', '2359');
    
    console.log(`📅 수집 기간: ${inqryBgnDt} ~ ${inqryEndDt}`);
    console.log('🔄 업무구분: 공사(공사), 용역(용역), 물품(물품)\n');
    
    // 업무 구분별 엔드포인트
    const workTypes = [
      { name: '공사', endpoint: 'getBidPblancListInfoCnstwk' },
      { name: '용역', endpoint: 'getBidPblancListInfoSvc' },
      { name: '물품', endpoint: 'getBidPblancListInfoGoods' }
    ];
    
    let totalInserted = 0;
    let totalDuplicates = 0;
    let totalProcessed = 0;
    
    // 각 업무 구분별로 데이터 수집
    for (const workType of workTypes) {
      console.log(`\n📦 업무구분: ${workType.name}`);
      console.log(`   엔드포인트: ${workType.endpoint}`);
      
      const url = `http://apis.data.go.kr/1230000/ad/BidPublicInfoService/${workType.endpoint}`;
      
      let pageNo = 1;
      let hasMorePages = true;
      let pageInserted = 0;
      let pageDuplicates = 0;
      
      while (hasMorePages && pageNo <= 10) {
        try {
          const params = {
            ServiceKey: API_KEY,
            numOfRows: 100,
            pageNo: pageNo,
            type: 'json',
            inqryDiv: 1,
            inqryBgnDt: inqryBgnDt,
            inqryEndDt: inqryEndDt
          };
          
          console.log(`   📄 페이지 ${pageNo} 요청 중...`);
          const response = await axios.get(url, { params, timeout: 10000 });
          
          const items = response.data.response.body.items || [];
          const totalCount = response.data.response.body.totalCount || 0;
          
          if (items.length === 0) {
            hasMorePages = false;
            console.log(`   ✅ 페이지 ${pageNo}: ${items.length}개 (종료)`);
            break;
          }
          
          console.log(`   ✅ 페이지 ${pageNo}: ${items.length}개 항목 수신`);
          
          // 각 항목 처리
          for (const item of items) {
            try {
              const externalId = item.bidNtceNo || `${Date.now()}-${Math.random()}`;
              
              // 중복 확인
              const existing = await Announcement.findOne({ announcementNumber: externalId });
              if (existing) {
                pageDuplicates++;
                totalDuplicates++;
                continue;
              }
              
              // 새 문서 생성
              const doc = new Announcement({
                announcementNumber: externalId,
                title: item.bidNtceNm || '제목없음',
                description: item.ntceKindNm || '',
                agencyName: item.ntceInsttNm || '미정',
                workType: workType.name,
                region: item.dminsttNm || '전국',
                basicAmount: parseInt(item.presmptPrce) || 0,
                budget: parseInt(item.bdgtAmt) || 0,
                deadline: item.bidClseDt ? new Date(item.bidClseDt) : null,
                bidMethod: item.bidMethdNm || '',
                contractMethod: item.cntrctCnclsMthdNm || '',
                noticeDate: item.bidNtceDt ? new Date(item.bidNtceDt) : null,
                createdAt: new Date()
              });
              
              await doc.save();
              pageInserted++;
              totalInserted++;
            } catch (err) {
              console.error(`      ❌ 항목 저장 오류: ${err.message}`);
            }
          }
          
          // 다음 페이지 여부 확인
          if (pageInserted + pageDuplicates >= totalCount) {
            hasMorePages = false;
          }
          
          pageNo++;
          totalProcessed += items.length;
          
          // 레이트 제한 대응
          await new Promise(resolve => setTimeout(resolve, 1000));
          
        } catch (err) {
          console.error(`   ❌ 페이지 ${pageNo} 오류: ${err.message}`);
          hasMorePages = false;
        }
      }
      
      console.log(`   📊 ${workType.name}: ${pageInserted}개 추가, ${pageDuplicates}개 중복`);
    }
    
    // 최종 통계
    const totalInDB = await Announcement.countDocuments();
    
    console.log('\n' + '='.repeat(60));
    console.log('✅ 데이터 수집 완료');
    console.log('='.repeat(60));
    console.log(`📈 처리된 항목: ${totalProcessed}`);
    console.log(`✨ 새로 추가된 공고: ${totalInserted}`);
    console.log(`⚠️  중복 건수: ${totalDuplicates}`);
    console.log(`📊 DB 총 공고 건수: ${totalInDB}`);
    console.log('='.repeat(60) + '\n');
    
    process.exit(0);
  })
  .catch(err => {
    console.error('❌ MongoDB 연결 오류:', err.message);
    process.exit(1);
  });
