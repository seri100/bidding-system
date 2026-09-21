const ExcelJS = require('exceljs');
const fs = require('fs');

async function convertExcelToJSON() {
  try {
    const excelPath = '2026_08_31_전국업체명(소시,기시추가).xlsx';
    
    if (!fs.existsSync(excelPath)) {
      console.log('❌ 파일을 찾을 수 없습니다');
      return;
    }

    console.log('📖 엑셀 파일 읽기 중...\n');
    const workbook = new ExcelJS.Workbook();
    await workbook.xlsx.readFile(excelPath);
    
    // 첫 번째 시트 "전체" 사용
    const worksheet = workbook.worksheets[0];
    
    if (!worksheet) {
      console.log('❌ 워크시트를 찾을 수 없습니다');
      return;
    }

    const headers = [];
    const companies = [];
    let rowCount = 0;
    
    console.log(`📊 시트 "${worksheet.name}" 처리 중...`);
    
    // richText 값 추출 함수
    function extractValue(cellValue) {
      if (!cellValue) return '';
      
      // richText 객체인 경우
      if (cellValue.richText && Array.isArray(cellValue.richText)) {
        return cellValue.richText.map(rt => rt.text || '').join('');
      }
      
      // 일반 값
      if (typeof cellValue === 'string' || typeof cellValue === 'number') {
        return String(cellValue).trim();
      }
      
      // 숫자 값
      if (typeof cellValue === 'number') {
        return cellValue;
      }
      
      return '';
    }
    
    worksheet.eachRow((row, rowNumber) => {
      if (rowNumber === 1) {
        // 헤더 읽기
        row.eachCell((cell, colNumber) => {
          headers[colNumber] = extractValue(cell.value);
        });
        console.log(`✓ 헤더 ${headers.filter(h => h).length}개 읽음`);
        return;
      }
      
      const company = {};
      let hasData = false;
      
      row.eachCell((cell, colNumber) => {
        const header = headers[colNumber];
        const value = extractValue(cell.value);
        
        if (header && value) {
          company[header] = value;
          hasData = true;
        }
      });
      
      // 상호(업체명)가 있는 행만 추가
      if (hasData && company['상호']) {
        companies.push(company);
        rowCount++;
        
        // 진행 상황 표시
        if (rowCount % 50 === 0) {
          console.log(`  읽음: ${rowCount}개...`);
        }
      }
    });
    
    // JSON 파일로 저장
    fs.writeFileSync('companies.json', JSON.stringify(companies, null, 2), 'utf8');
    
    console.log(`\n✅ 변환 완료!`);
    console.log(`📊 총 ${companies.length}개 업체 데이터`);
    console.log(`💾 저장 위치: C:\\bidding-system\\companies.json`);
    console.log(`\n📌 다음 단계:`);
    console.log(`   1. 웹 브라우저에서 http://localhost:5000 열기`);
    console.log(`   2. "업체 관리" 탭 클릭`);
    console.log(`   3. "📥 엑셀 일괄 로드" 버튼 클릭`);
    
  } catch (error) {
    console.error('❌ 오류:', error.message);
  }
}

convertExcelToJSON();
