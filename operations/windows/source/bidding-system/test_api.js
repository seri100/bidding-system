const axios = require('axios');
require('dotenv').config({ path: 'C:\\bidding-system\\.env.raspberry' });

const API_KEY = process.env.PUBLIC_DATA_API_KEY;

async function testAPI() {
  console.log('🔍 API 키:', API_KEY ? '설정됨' : '미설정');
  
  const endpoints = [
    'https://apis.data.go.kr/1230000/PubDataPortalService/getPubDataPrtcList',
    'https://apis.data.go.kr/1230000/PubDataPortalService/getPubData',
    'https://www.g2b.go.kr/api/v1/announcements'
  ];

  for (const baseUrl of endpoints) {
    console.log(`\n🔗 엔드포인트: ${baseUrl}`);
    
    const params = {
      serviceKey: API_KEY,
      pageNo: 1,
      numOfRows: 10,
      type: 'json'
    };

    try {
      const response = await axios.get(baseUrl, { params, timeout: 5000 });
      console.log('✅ 응답 성공:', response.status);
      console.log('📋 응답 데이터:', JSON.stringify(response.data).substring(0, 200));
    } catch (error) {
      console.log('❌ 오류:', error.response?.status, error.message);
      if (error.response?.data) {
        console.log('📋 오류 응답:', JSON.stringify(error.response.data).substring(0, 300));
      }
    }
    
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
}

testAPI();
