const ExcelJS = require('exceljs');
const MongoClient = require('mongodb').MongoClient;

(async () => {
  try {
    console.log('📂 Excel 파일 읽기 시작...');
    const wb = new ExcelJS.Workbook();
    await wb.xlsx.readFile('2026_08_31_전국업체명(소시,기시추가).xlsx');
    const ws = wb.getWorksheet('전체');
    
    const companies = [];
    
    // 행 2부터 시작 (행 1은 헤더)
    for (let rowNum = 2; rowNum <= ws.rowCount; rowNum++) {
      const row = ws.getRow(rowNum);
      
      // 각 셀의 값을 직접 추출
      const companyName = row.getCell(1).value;
      const region = row.getCell(3).value;
      const businessReg = row.getCell(4).value;
      const debtRatio = row.getCell(5).value;
      const currentRatio = row.getCell(6).value;
      const fireConst = row.getCell(7).value;
      const firePerf5 = row.getCell(8).value;
      const firePerf3 = row.getCell(9).value;
      const fireDateStr = row.getCell(10).value;
      const mechConst = row.getCell(11).value;
      const mechPerf5 = row.getCell(12).value;
      const mechPerf3 = row.getCell(13).value;
      const businessStartDate = row.getCell(14).value;
      
      // companyName이 없으면 스킵
      if (!companyName) continue;
      
      const company = {
        companyName: String(companyName || ''),
        region: String(region || ''),
        businessRegistration: String(businessReg || ''),
        debtRatio: typeof debtRatio === 'number' ? debtRatio : null,
        currentRatio: typeof currentRatio === 'number' ? currentRatio : null,
        fireConstruction: {
          constructionCapacity: typeof fireConst === 'number' ? fireConst : null,
          performance5Years: typeof firePerf5 === 'number' ? firePerf5 : null,
          performance3Years: typeof firePerf3 === 'number' ? firePerf3 : null,
          registrationDate: fireDateStr ? String(fireDateStr) : ''
        },
        mechanicalEquipment: {
          constructionCapacity: typeof mechConst === 'number' ? mechConst : null,
          performance5Years: typeof mechPerf5 === 'number' ? mechPerf5 : null,
          performance3Years: typeof mechPerf3 === 'number' ? mechPerf3 : null
        },
        businessStartDate: businessStartDate ? String(businessStartDate) : '',
        creditRating: '',
        certificates: { fireSafety: false, mechanicalFacility: false },
        source: '2026_08_31_전국업체명(소시,기시추가)',
        importedAt: new Date()
      };
      
      companies.push(company);
    }
    
    console.log('✓ Excel 파싱 완료: ' + companies.length + '개');
    
    // MongoDB 연결 및 저장
    const client = new MongoClient('mongodb://localhost:27017');
    await client.connect();
    const db = client.db('bidding_system');
    const col = db.collection('companies');
    
    // 기존 데이터 삭제
    const delRes = await col.deleteMany({});
    console.log('✓ 기존 데이터 ' + delRes.deletedCount + '개 삭제');
    
    // 새 데이터 삽입
    const insRes = await col.insertMany(companies);
    console.log('✓ 신규 데이터 ' + companies.length + '개 삽입');
    
    // 최종 확인
    const count = await col.countDocuments();
    console.log('✓ 최종 DB 레코드: ' + count + '개');
    
    // 샘플 출력
    const sample = await col.findOne();
    console.log('\n📋 샘플 레코드:');
    console.log('- 상호: ' + sample.companyName);
    console.log('- 지역: ' + sample.region);
    console.log('- 사업자: ' + sample.businessRegistration);
    console.log('- 부채율: ' + sample.debtRatio);
    console.log('- 유동비: ' + sample.currentRatio);
    
    await client.close();
    console.log('\n✅ 완료!');
  } catch (err) {
    console.error('❌ 오류:', err.message);
  }
})();
