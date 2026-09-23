const axios = require('axios');
require('dotenv').config({ path: 'C:\\bidding-system\\.env.raspberry' });

const API_KEY = process.env.PUBLIC_DATA_API_KEY;
const now = new Date();
const pastDate = new Date(now - 30 * 24 * 60 * 60 * 1000);

// 날짜 포맷 함수
function formatDate(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

const startDate = formatDate(pastDate);
const endDate = formatDate(now);

console.log('🔍 나라장터 공공데이터 API 테스트');
console.log(`📅 기간: ${startDate} ~ ${endDate}\n`);

// 공공데이터포털 API (공식 문서 기반)
const pubDataUrl = 'http://apis.data.go.kr/1230000/PubDataOpnStdService/getPubProcureBidInfoSrch';

const params = {
  ServiceKey: API_KEY,
  numOfRows: 100,
  pageNo: 1,
  resultType: 'json',
  inqryDiv: 1,                 // 1=입찰공고
  inqryBgnDt: startDate.replace(/-/g, ''),
  inqryEndDt: endDate.replace(/-/g, '')
};

console.log('📌 API 엔드포인트:', pubDataUrl);
console.log('📌 요청 파라미터:');
Object.entries(params).forEach(([k, v]) => {
  console.log(`   ${k}: ${k.includes('ServiceKey') ? '***' : v}`);
});

axios.get(pubDataUrl, { params, timeout: 10000 })
  .then(resp => {
    console.log('\n✅ API 응답 수신됨');
    console.log('📊 응답 구조:');
    console.log(JSON.stringify(resp.data, null, 2).substring(0, 1500));
  })
  .catch(err => {
    console.error('\n❌ API 오류:');
    console.error('메시지:', err.message);
    if (err.response) {
      console.error('상태코드:', err.response.status);
      console.error('응답:', JSON.stringify(err.response.data, null, 2).substring(0, 500));
    }
  });
