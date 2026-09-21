const ExcelJS = require('exceljs');

async function getHeaders() {
  const workbook = new ExcelJS.Workbook();
  await workbook.xlsx.readFile('2026_08_31_전국업체명(소시,기시추가).xlsx');
  
  const ws = workbook.getWorksheet('전체');
  const headerRow = ws.getRow(1);
  
  console.log('헤더 목록:');
  for(let i = 1; i <= 35; i++) {
    const cell = headerRow.getCell(i);
    const value = cell.value;
    if(value) {
      console.log('열' + i + ':', JSON.stringify(value));
    }
  }
  
  console.log('');
  console.log('데이터 샘플 (행2):');
  const dataRow = ws.getRow(2);
  for(let i = 1; i <= 15; i++) {
    const val = dataRow.getCell(i).value;
    console.log('열' + i + ':', val);
  }
}

getHeaders();
