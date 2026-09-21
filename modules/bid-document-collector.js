const fs = require('fs');
const path = require('path');

const BID_SOURCES = {
  한전공고: 'X:\\VOL1\\bid\\bid\\bid_elec\\agreement_docs',
  국가철도공단: 'X:\\VOL1\\bid\\bid\\bid-nr\\attachments',
  한전: 'X:\\VOL1\\bid\\bid\\bid_elec\\attachments',
  한국수력원자력: 'X:\\VOL1\\bid\\bid\\khnp\\2026년\\09월\\14일\\첨부파일',
  고속도로: 'X:\\VOL1\\bid\\bid\\exroad\\attachments',
  LH: 'X:\\VOL1\\bid\\bid\\토지가져오기-경현\\LH\\첨부파일',
  나라장터: 'X:\\VOL1\\bid\\bid\\n_data\\attachments'
};

// 폴더에서 모든 파일 수집
function collectBidDocuments() {
  const allDocs = [];
  const stats = {};

  for (const [source, dirPath] of Object.entries(BID_SOURCES)) {
    try {
      if (!fs.existsSync(dirPath)) {
        stats[source] = { count: 0, files: [] };
        continue;
      }

      const files = fs.readdirSync(dirPath)
        .filter(f => fs.statSync(path.join(dirPath, f)).isFile())
        .map(fileName => ({
          fileName,
          filePath: path.join(dirPath, fileName),
          source,
          agency: source,
          fileType: path.extname(fileName).toLowerCase().slice(1),
          fileSize: fs.statSync(path.join(dirPath, fileName)).size,
          lastModified: fs.statSync(path.join(dirPath, fileName)).mtime,
          status: 'pending'
        }));

      stats[source] = { count: files.length, files: files.map(f => f.fileName) };
      allDocs.push(...files);
    } catch (err) {
      console.error(`❌ ${source} 오류:`, err.message);
      stats[source] = { count: 0, files: [], error: err.message };
    }
  }

  return { documents: allDocs, stats, total: allDocs.length };
}

module.exports = { collectBidDocuments, BID_SOURCES };
