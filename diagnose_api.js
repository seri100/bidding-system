const axios = require('axios');
require('dotenv').config({ path: 'C:\\bidding-system\\.env.raspberry' });

const API_KEY = process.env.PUBLIC_DATA_API_KEY;

async function diagnoseAPI() {
  console.log('🔍 API 진단 시작\n');

  // 여러 파라미터 조합 시도
  const testConfigs = [
    {
      name: '설정 1: 기본 파라미터',
      params: { serviceKey: API_KEY, pageNo: 1, numOfRows: 10, resultType: 'json' }
    },
    {
      name: '설정 2: 결과 타입 변경',
      params: { serviceKey: API_KEY, pageNo: 1, numOfRows: 10, resultType: 'XML' }
    },
    {
      name: '설정 3: 필수 파라미터만',
      params: { serviceKey: API_KEY }
    },
    {
      name: '설정 4: 인코딩된 키',
      params: { serviceKey: decodeURIComponent(API_KEY), pageNo: 1, numOfRows: 10 }
    }
  ];

  const baseUrl = 'https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPublicInfo';

  for (const config of testConfigs) {
    console.log(`\n🧪 ${config.name}`);
    console.log(`파라미터:`, config.params);
    
    try {
      const response = await axios.get(baseUrl, { params: config.params, timeout: 5000 });
      console.log('✅ 상태:', response.status);
      console.log('📋 응답:', JSON.stringify(response.data).substring(0, 500));
      
      if (response.data.response?.body?.items) {
        console.log(`📊 ${response.data.response.body.items.length}개 공고 수신`);
      }
    } catch (error) {
      console.log('❌ 상태:', error.response?.status);
      console.log('❌ 메시지:', error.message);
      if (error.response?.data) {
        console.log('📋 오류:', JSON.stringify(error.response.data).substring(0, 300));
      }
    }
    
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
}

diagnoseAPI();
