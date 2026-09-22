require('dotenv').config({ path: 'C:\\bidding-system\\.env.raspberry' });
const express = require('express');
const mongoose = require('mongoose');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 5001;

console.log('🔧 환경 설정:');
console.log('  PORT:', process.env.PORT || '5001 (기본값)');

app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ limit: '50mb' }));
app.use(express.static(path.join(__dirname, 'public')));

const mongoUri = process.env.MONGODB_URI || 'mongodb://localhost:27017/bidding_system';
mongoose.connect(mongoUri, { useNewUrlParser: true, useUnifiedTopology: true })
  .then(() => console.log('✅ MongoDB 연결 성공'))
  .catch(err => console.error('❌ MongoDB 연결 실패:', err.message));

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

// 1. 공고 검색
app.get('/api/announcements/search', async (req, res) => {
  try {
    const { agencyName, workType, region, minBudget, maxBudget, limit } = req.query;
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

    const pageLimit = Math.min(parseInt(limit) || 50, 100);
    const announcements = await Announcement.find(filter).limit(pageLimit).sort({ createdAt: -1 }).lean();

    res.json({
      success: true,
      count: announcements.length,
      data: announcements
    });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// 2. 필터 옵션
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
    res.status(500).json({ success: false, error: error.message });
  }
});

// 3. 전체 공고
app.get('/api/announcements', async (req, res) => {
  try {
    const limit = Math.min(parseInt(req.query.limit) || 50, 100);
    const announcements = await Announcement.find().limit(limit).sort({ createdAt: -1 }).lean();

    res.json({
      success: true,
      count: announcements.length,
      data: announcements
    });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// 4. 통계
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
    res.status(500).json({ success: false, error: error.message });
  }
});

// 5. 헬스 체크
app.get('/api/health', (req, res) => {
  res.json({ success: true, message: 'Server is running', port: PORT });
});

// 6. 기관별 공고
app.get('/api/agencies/:agencyName/announcements', async (req, res) => {
  try {
    const { agencyName } = req.params;
    const limit = Math.min(parseInt(req.query.limit) || 50, 100);
    const announcements = await Announcement.find({ agencyName }).limit(limit).sort({ createdAt: -1 }).lean();
    const total = await Announcement.countDocuments({ agencyName });

    res.json({
      success: true,
      agency: agencyName,
      count: announcements.length,
      total: total,
      data: announcements
    });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// 7. 업무별 공고
app.get('/api/worktype/:workType/announcements', async (req, res) => {
  try {
    const { workType } = req.params;
    const limit = Math.min(parseInt(req.query.limit) || 50, 100);
    const announcements = await Announcement.find({ workType }).limit(limit).sort({ createdAt: -1 }).lean();
    const total = await Announcement.countDocuments({ workType });

    res.json({
      success: true,
      workType: workType,
      count: announcements.length,
      total: total,
      data: announcements
    });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// 8. 지역별 공고
app.get('/api/region/:region/announcements', async (req, res) => {
  try {
    const { region } = req.params;
    const limit = Math.min(parseInt(req.query.limit) || 50, 100);
    const announcements = await Announcement.find({ region }).limit(limit).sort({ createdAt: -1 }).lean();
    const total = await Announcement.countDocuments({ region });

    res.json({
      success: true,
      region: region,
      count: announcements.length,
      total: total,
      data: announcements
    });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// 9. 공고 상세 조회
app.get('/api/announcements/:id', async (req, res) => {
  try {
    const { id } = req.params;
    const announcement = await Announcement.findById(id).lean();

    if (!announcement) {
      return res.status(404).json({ success: false, error: '공고를 찾을 수 없습니다' });
    }

    res.json({
      success: true,
      data: announcement
    });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});

app.listen(PORT, () => {
  console.log('🚀 서버 실행 중: http://localhost:' + PORT);
});
