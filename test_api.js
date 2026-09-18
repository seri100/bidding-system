const http = require('http');

function testAPI(path) {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: 'localhost',
      port: 5000,
      path: path,
      method: 'GET'
    };

    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch (e) {
          resolve(data);
        }
      });
    });

    req.on('error', reject);
    req.end();
  });
}

(async () => {
  console.log('🧪 API 테스트 시작\n');

  try {
    console.log('📋 테스트 1: /api/filter-options');
    const filters = await testAPI('/api/filter-options');
    console.log(JSON.stringify(filters, null, 2));

    console.log('\n📋 테스트 2: /api/announcements (전체)');
    const allAnn = await testAPI('/api/announcements');
    console.log('총 개수:', allAnn.count);
    console.log('첫 번째 공고:', JSON.stringify(allAnn.data[0], null, 2));

    console.log('\n📋 테스트 3: /api/announcements/search (필터 - URL 인코딩)');
    // URL 인코딩으로 한글 처리
    const searchPath = '/api/announcements/search?agencyName=' + 
                       encodeURIComponent('기타공공기관') + 
                       '&workType=' + encodeURIComponent('용역') + 
                       '&region=' + encodeURIComponent('충북');
    console.log('요청 경로:', searchPath);
    
    const filtered = await testAPI(searchPath);
    console.log('검색 조건: 기타공공기관 + 용역 + 충북');
    console.log('결과 개수:', filtered.count);
    if (filtered.data && filtered.data.length > 0) {
      console.log('첫 번째 결과:', JSON.stringify(filtered.data[0], null, 2));
    }

    console.log('\n📋 테스트 4: /api/announcements/search (조달청)');
    const searchPath2 = '/api/announcements/search?agencyName=' + 
                        encodeURIComponent('조달청') + 
                        '&workType=' + encodeURIComponent('용역');
    const filtered2 = await testAPI(searchPath2);
    console.log('검색 조건: 조달청 + 용역');
    console.log('결과 개수:', filtered2.count);

    console.log('\n✅ 모든 테스트 완료');
  } catch (err) {
    console.error('❌ 오류:', err.message);
  }

  process.exit(0);
})();
