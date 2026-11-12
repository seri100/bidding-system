const axios = require('axios');
require('dotenv').config({ path: 'C:\\bidding-system\\.env.raspberry' });

const API_KEY = process.env.PUBLIC_DATA_API_KEY;

console.log('🔍 나라장터 입찰공고정보서비스 API 테스트\n');

// 공사 입찰공고 조회 (입찰공고 목록)
const constructionUrl = 'http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwk';

const params = {
  ServiceKey: API_KEY,
  numOfRows: 10,
  pageNo: 1,
  type: 'json',
  inqryDiv: 1,
  inqryBgnDt: '202609220000',
  inqryEndDt: '202609232359'
};

console.log('📌 API 엔드포인트: getBidPblancListInfoCnstwk (공사)');
console.log('📌 URL:', constructionUrl);
console.log('📌 요청 파라미터:');
Object.entries(params).forEach(([k, v]) => {
  if (k !== 'ServiceKey') console.log(`   ${k}: ${v}`);
});

axios.get(constructionUrl, { params, timeout: 10000 })
  .then(resp => {
    console.log('\n✅ API 응답 수신됨');
    console.log('📊 응답 구조:');
    
    const data = resp.data;
    console.log('최상위 키:', Object.keys(data));
    
    // 응답 구조 분석
    if (data.response) {
      console.log('response 내 키:', Object.keys(data.response));
      if (data.response.body) {
        console.log('body 내 키:', Object.keys(data.response.body));
        if (data.response.body.items) {
          console.log(`\n📈 총 ${data.response.body.items.length} 개 항목`);
          if (data.response.body.items.length > 0) {
            console.log('\n📄 첫 번째 항목 필드:');
            const firstItem = data.response.body.items[0];
            Object.keys(firstItem).slice(0, 15).forEach(key => {
              console.log(`   ${key}: ${firstItem[key]}`);
            });
          }
        }
      }
    }
  })
  .catch(err => {
    console.error('\n❌ API 오류:');
    console.error('메시지:', err.message);
    if (err.response) {
      console.error('상태코드:', err.response.status);
      console.error('응답:', JSON.stringify(err.response.data, null, 2).substring(0, 800));
    }
  });
