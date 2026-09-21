const mysql = require('mysql2/promise');
const mongoose = require('mongoose');

// 라즈베리파이 MySQL (암호 없이 접속)
const connection = mysql.createConnection({
  host: '192.168.0.17',
  user: 'root',
  database: 'kakao',
  socketPath: '/var/run/mysqld/mysqld.sock' // 또는 직접 TCP
});

// MongoDB
mongoose.connect('mongodb://localhost:27017/bidding_system');

const announcementSchema = new mongoose.Schema({
  bidNtceNo: String,
  bidNtceNm: String,
  presmptPrce: Number,
  bidClseDt: Date,
  ntceInsttNm: String,
  indstrytyCd: String,
  rep_region: String,
  raw_json: String,
  fetched_at: { type: Date, default: Date.now }
});

const Announcement = mongoose.model('Announcement', announcementSchema);

async function syncData() {
  try {
    const conn = await connection;
    const [rows] = await conn.execute('SELECT * FROM bid_raw LIMIT 10');
    
    console.log(`라즈베리파이에서 ${rows.length}개 공고 조회`);
    
    // MongoDB에 저장
    for (const row of rows) {
      await Announcement.create({
        bidNtceNo: row.bidNtceNo,
        bidNtceNm: row.bidNtceNm,
        presmptPrce: row.presmptPrce,
        bidClseDt: row.bidClseDt,
        ntceInsttNm: JSON.parse(row.raw_json).ntceInsttNm,
        indstrytyCd: row.indstrytyCd,
        rep_region: row.rep_region,
        raw_json: row.raw_json
      });
    }
    
    console.log('✅ MongoDB에 저장 완료');
    process.exit(0);
  } catch (err) {
    console.error('❌ 오류:', err.message);
    process.exit(1);
  }
}

syncData();
