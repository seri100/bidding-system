require('dotenv').config({ path: '.env.raspberry' });
const express = require('express');
const mongoose = require('mongoose');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 5001;

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// MongoDB 연결
const mongoUri = process.env.MONGODB_URI || 'mongodb://localhost:27017/bidding_system';
mongoose.connect(mongoUri, { useNewUrlParser: true, useUnifiedTopology: true })
  .then(() => console.log('✅ MongoDB 연결 성공'))
  .catch(err => console.error('❌ MongoDB 연결 실패:', err.message));

// 공고 스키마
const announcementSchema = new mongoose.Schema({
  announcementNumber: String,
  title: String,
  description: String,
  agencyName: String,
  workType: String,
  region: String,
  basicAmount: Number,
  budget: Number,
  deadline: Date,
  createdAt: { type: Date, default: Date.now },
  updatedAt: { type: Date, default: Date.now }
}, { strict: false });

const Announcement = mongoose.model('Announcement', announcementSchema);

// 1. 공고 검색 (기관 필터 포함)
app.get('/api/announcements/search', async (req, res) => {
  try {
    const { agencyName, workType, region, minBudget, maxBudget } = req.query;
    let filter = {};

    if (agencyName && agencyName !== 'all' && agencyName !== '') {
      filter.agencyName = agencyName;
    }
    if (workType && workType !== 'all' && workType !== '') {
      filter.workType = workType;
    }
    if (region && region !== 'all' && region !== '') {
      filter.region = region;
    }
    if (minBudget) {
      filter.basicAmount = { $gte: parseInt(minBudget) };
    }
    if (maxBudget) {
      if (!filter.basicAmount) filter.basicAmount = {};
      filter.basicAmount.$lte = parseInt(maxBudget);
    }

    const announcements = await Announcement.find(filter)
      .limit(100)
      .sort({ createdAt: -1 })
      .lean();

    res.json({
      success: true,
      count: announcements.length,
      data: announcements
    });
  } catch (error) {
    console.error('❌ 공고 검색 오류:', error.message);
    res.status(500).json({ success: false, error: error.message });
  }
});

// 2. 필터 옵션 조회
app.get('/api/filter-options', async (req, res) => {
  try {
    const agencies = await Announcement.distinct('agencyName');
    const workTypes = await Announcement.distinct('workType');
    const regions = await Announcement.distinct('region');

    res.json({
      success: true,
      agencies: agencies.filter(a => a).sort(),
      workTypes: workTypes.filter(w => w).sort(),
      regions: regions.filter(r => r).sort()
    });
  } catch (error) {
    console.error('❌ 필터 옵션 조회 오류:', error.message);
    res.status(500).json({ success: false, error: error.message });
  }
});

// 3. 전체 공고 조회
app.get('/api/announcements', async (req, res) => {
  try {
    const announcements = await Announcement.find()
      .limit(50)
      .sort({ createdAt: -1 })
      .lean();

    res.json({
      success: true,
      count: announcements.length,
      data: announcements
    });
  } catch (error) {
    console.error('❌ 공고 조회 오류:', error.message);
    res.status(500).json({ success: false, error: error.message });
  }
});

// 4. 통계 정보 조회
app.get('/api/statistics', async (req, res) => {
  try {
    const total = await Announcement.countDocuments();
    const byAgency = await Announcement.aggregate([
      { $group: { _id: '$agencyName', count: { $sum: 1 } } },
      { $sort: { count: -1 } }
    ]);
    const byWorkType = await Announcement.aggregate([
      { $group: { _id: '$workType', count: { $sum: 1 } } },
      { $sort: { count: -1 } }
    ]);
    const byRegion = await Announcement.aggregate([
      { $group: { _id: '$region', count: { $sum: 1 } } },
      { $sort: { count: -1 } }
    ]);

    res.json({
      success: true,
      total,
      byAgency,
      byWorkType,
      byRegion
    });
  } catch (error) {
    console.error('❌ 통계 조회 오류:', error.message);
    res.status(500).json({ success: false, error: error.message });
  }
});

// 서버 시작
app.listen(PORT, () => {
  console.log('🚀 서버 실행 중: http://localhost:' + PORT);
  console.log('✅ MongoDB 연결 성공');
});

const agencies = [
  { name: 'LH(한국토지주택공사)', code: 'LH' },
  { name: '한국도로공사', code: 'ROAD' },
  { name: '국가철도공단', code: 'KORAIL' },
  { name: '조달청(나라장터)', code: 'G2B' },
  { name: '한국수력원자력', code: 'KHNP' },
  { name: '한국전력공사', code: 'KEPCO' }
];

console.log('\n📋 지원하는 기관 목록:');
agencies.forEach(agency => {
  console.log('  ✅ ' + agency.name + ' (' + agency.code + ')');
});
