const fs = require('fs');
const path = require('path');

const BID_SOURCES = {
  kepco: {
    name: '한국전력공사',
    path: 'X:\\VOL1\\bid\\bid\\bid_elec\\agreement_docs',
    workType: '용역',
    region: '전국'
  },
  khnp: {
    name: '한국수력원자력(주)',
    path: 'X:\\VOL1\\bid\\bid\\khnp\\2026년\\09월\\14일\\첨부파일',
    workType: '용역',
    region: '전국'
  },
  krr: {
    name: '국가철도공단',
    path: 'X:\\VOL1\\bid\\bid\\bid-nr\\attachments',
    workType: '용역',
    region: '전국'
  },
  lh: {
    name: 'LH(한국토지주택공사)',
    path: 'X:\\VOL1\\bid\\bid\\토지가져오기-경현\\LH\\첨부파일',
    workType: '용역',
    region: '전국'
  },
  hrco: {
    name: '한국도로공사',
    path: 'X:\\VOL1\\bid\\bid\\exroad\\attachments',
    workType: '용역',
    region: '전국'
  },
  g2b: {
    name: '조달청(나라장터)',
    path: 'X:\\VOL1\\bid\\bid\\n_data\\attachments',
    workType: '기타',
    region: '전국'
  }
};

function extractAnnouncementNumber(filename) {
  const match = filename.match(/^([EKPC]\d{10,12})/);
  return match ? match[1] : null;
}

function extractTitle(filename) {
  return filename.replace(/\.[^/.]+$/, '').replace(/_/g, ' ');
}

function collectAnnouncementsFromLocal() {
  const documents = [];
  const stats = {};

  Object.entries(BID_SOURCES).forEach(([key, source]) => {
    console.log(`\n📁 ${source.name} 수집 중...`);
    console.log(`   경로: ${source.path}`);

    if (!fs.existsSync(source.path)) {
      console.log(`⚠️  경로 없음`);
      stats[source.name] = 0;
      return;
    }

    const files = fs.readdirSync(source.path).filter(f => {
      return /\.(txt|hwp|doc|docx|pdf)$/i.test(f);
    });

    const collected = [];
    files.forEach(file => {
      const announcementNumber = extractAnnouncementNumber(file);
      const title = extractTitle(file);

      if (announcementNumber && title) {
        collected.push({
          announcementNumber,
          title,
          agencyName: source.name,
          agencyCode: key,
          workType: source.workType,
          region: source.region,
          basicAmount: 0,
          filename: file,
          createdAt: new Date()
        });
      }
    });

    console.log(`✅ ${source.name}: ${collected.length}개 공고문 수집`);
    documents.push(...collected);
    stats[source.name] = collected.length;
  });

  return { documents, stats };
}

module.exports = {
  collectAnnouncements: collectAnnouncementsFromLocal,
  BID_SOURCES
};
