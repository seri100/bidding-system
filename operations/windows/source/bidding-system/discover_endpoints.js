const axios = require('axios');
require('dotenv').config({ path: 'C:\\bidding-system\\.env.raspberry' });

const API_KEY = process.env.PUBLIC_DATA_API_KEY;

console.log('🔍 용역/물품 API 엔드포인트 탐색\n');

// 공공데이터포털 API 문서에서 제시된 엔드포인트 패턴들
const possibleEndpoints = [
  // 공식 문서 기반
  { name: '용역 (공식)', endpoint: 'getBidPblancListInfoSvc' },
  { name: '물품 (공식)', endpoint: 'getBidPblancListInfoGoods' },
  // 대체 패턴
  { name: '용역 (대체1)', endpoint: 'getBidPblancListSvc' },
  { name: '물품 (대체1)', endpoint: 'getBidPblancListGoods' },
  { name: '용역 (대체2)', endpoint: 'getBidPblancListInfoSvcPPSSrch' },
  { name: '물품 (대체2)', endpoint: 'getBidPblancListInfoGoodsPPSSrch' }
];

async function testEndpoint(name, endpoint) {
  try {
    const url = `http://apis.data.go.kr/1230000/ad/BidPublicInfoService/${endpoint}`;
    
    const params = {
      ServiceKey: API_KEY,
      numOfRows: 1,
      pageNo: 1,
      type: 'json',
      inqryDiv: 1,
      inqryBgnDt: '202609220000',
      inqryEndDt: '202609232359'
    };
    
    const response = await axios.get(url, { params, timeout: 5000 });
    
    if (response.data.response.body.items && response.data.response.body.items.length > 0) {
      console.log(`✅ ${name}: 성공 (${response.data.response.body.totalCount}개)`);
      return true;
    }
  } catch (err) {
    // 실패
  }
  return false;
}

(async () => {
  for (const ep of possibleEndpoints) {
    await testEndpoint(ep.name, ep.endpoint);
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  process.exit(0);
})();
