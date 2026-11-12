const PDFDocument = require('pdfkit');
const fs = require('fs');
const path = require('path');

async function generateBidReport(bidData, companyData, evaluationResult, bidPrice) {
    const fileName = `bid_report_${bidData.announcementId}_${Date.now()}.pdf`;
    const filePath = path.join(__dirname, '../reports', fileName);

    // reports 폴더 생성
    if (!fs.existsSync(path.join(__dirname, '../reports'))) {
        fs.mkdirSync(path.join(__dirname, '../reports'), { recursive: true });
    }

    const doc = new PDFDocument();
    const stream = fs.createWriteStream(filePath);

    doc.pipe(stream);

    // 제목
    doc.fontSize(20).font('Courier').text('입찰 분석 보고서', { align: 'center' });
    doc.fontSize(10).text(`작성일: ${new Date().toLocaleString('ko-KR')}`, { align: 'center' });
    doc.moveTo(50, 80).lineTo(550, 80).stroke();

    // 공고 정보
    doc.fontSize(12).font('Courier-Bold').text('1. 공고 정보');
    doc.fontSize(10).font('Courier').text(`제목: ${bidData.title}`);
    doc.text(`기관: ${bidData.agency}`);
    doc.text(`예정가격: ${bidData.estimatedPrice.toLocaleString()} 원`);
    doc.text(`마감일: ${new Date(bidData.deadline).toLocaleString('ko-KR')}`);
    doc.text(`카테고리: ${bidData.category}`);
    doc.moveDown();

    // 회사 정보
    doc.fontSize(12).font('Courier-Bold').text('2. 회사 정보');
    doc.fontSize(10).font('Courier').text(`회사명: ${companyData.name}`);
    doc.text(`사업자번호: ${companyData.bizNo || 'N/A'}`);
    doc.text(`신용등급: ${companyData.creditRating || 'N/A'}`);
    doc.text(`부채율: ${companyData.debtRatio || 'N/A'}%`);
    doc.moveDown();

    // 평가 결과
    doc.fontSize(12).font('Courier-Bold').text('3. 평가 결과');
    doc.fontSize(10).font('Courier').text(`기술점수: ${evaluationResult.technicalScore.toFixed(1)} / 100`);
    doc.text(`재무점수: ${evaluationResult.financialScore.toFixed(1)} / 100`);
    doc.text(`이력점수: ${evaluationResult.historyScore.toFixed(1)} / 100`);
    doc.fontSize(12).font('Courier-Bold').text(`종합점수: ${evaluationResult.totalScore.toFixed(1)} / 100`);
    doc.moveDown();

    // 입찰가 분석
    doc.fontSize(12).font('Courier-Bold').text('4. 입찰가 분석');
    doc.fontSize(10).font('Courier').text(`기본 할인율: ${bidPrice.baseDiscount}%`);
    doc.text(`예상 이익률: ${bidPrice.profitMargin}%`);
    doc.fontSize(11).font('Courier-Bold').text(`추천 입찰가: ${bidPrice.bidPrice.toLocaleString()} 원`);
    doc.text(`예상 이익: ${bidPrice.expectedProfit.toLocaleString()} 원`);
    doc.text(`낙찰 확률: ${bidPrice.winProbability}%`);
    doc.moveDown();

    // 권고사항
    doc.fontSize(12).font('Courier-Bold').text('5. 권고사항');
    doc.fontSize(10).font('Courier').text(bidPrice.recommendation, { width: 500, align: 'left' });
    doc.moveDown();

    doc.text('본 분석 결과는 참고용이며, 최종 입찰 결정은 담당자의 판단에 따릅니다.');

    doc.end();

    return new Promise((resolve, reject) => {
        stream.on('finish', () => resolve(filePath));
        stream.on('error', reject);
    });
}

module.exports = { generateBidReport };
