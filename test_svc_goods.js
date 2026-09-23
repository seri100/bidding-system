const axios = require('axios');
require('dotenv').config({ path: 'C:\\bidding-system\\.env.raspberry' });

const API_KEY = process.env.PUBLIC_DATA_API_KEY;

console.log('🔍 용역/물품 API 재테스트\n');

// 정확한 엔드포인트 (공사 패턴을 따름)
const endpoints = [
  { name: '용역', endpoint: 'getBidPblancListInfoSvc' },
  { name: '물품', endpoint: 'getBidPblancListInfoGoods' }
];

async function testEndpoint(name, endpoint) {
  try {
    const url = `http://apis.data.go.kr/1230000/ad/BidPublicInfoService/${endpoint}`;
    
    const params = {
      ServiceKey: API_KEY,
      numOfRows: 1,
      pageNo: 1,
      type: 'json'
      // inqryDiv, inqryBgnDt, inqryEndDt 제외
    };
    
    console.log(`📌 ${name}:`);
    console.log(`   URL: ${endpoint}`);
    
    const response = await axios.get(url, { params, timeout: 5000 });
    
    const items = response.data?.response?.body?.items || [];
    const totalCount = response.data?.response?.body?.totalCount || 0;
    
    if (items.length > 0) {
      console.log(`   ✅ 성공 (총 ${totalCount}개)\n`);
      console.log(`   첫 항목 필드 (일부):`);
      const firstItem = items[0];
      ['bidNtceNo', 'bidNtceNm', 'ntceInsttNm', 'bdgtAmt'].forEach(key => {
        console.log(`     ${key}: ${firstItem[key]}`);
      });
    } else {
      console.log(`   ⚠️  데이터 없음\n`);
    }
  } catch (err) {
    console.log(`   ❌ 오류: ${err.response?.status || err.message}\n`);
    if (err.response?.data) {
      console.log(`   응답:`, JSON.stringify(err.response.data, null, 2).substring(0, 300));
    }
  }
}

(async () => {
  for (const ep of endpoints) {
    await testEndpoint(ep.name, ep.endpoint);
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  process.exit(0);
})();
