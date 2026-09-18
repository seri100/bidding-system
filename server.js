require('dotenv').config({ path: '.env.raspberry' });
const express = require('express');
const mongoose = require('mongoose');
const path = require('path');
const jwt = require('jsonwebtoken');
const bcryptjs = require('bcryptjs');
const ExcelJS = require('exceljs');
const PDFDocument = require('pdfkit');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 5000;
const JWT_SECRET = process.env.JWT_SECRET || 'your-secret-key-change-in-production';

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// MongoDB 연결
const mongoUri = 'mongodb://localhost:27017/bidding_system';
mongoose.connect(mongoUri, { useNewUrlParser: true, useUnifiedTopology: true });

mongoose.connection.on('connected', () => {
  console.log('✅ MongoDB 연결 성공');
});

mongoose.connection.on('error', (err) => {
  console.error('❌ MongoDB 에러:', err.message);
});

// ===== 스키마 정의 =====

// 1. 입찰 공고 스키마
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
  userId: String,
  userEmail: String,
  createdAt: { type: Date, default: Date.now }
}, { collection: 'announcements', strict: false });

// 2. 기업 정보 스키마
const companySchema = new mongoose.Schema({
  companyName: { type: String, required: true },
  registrationNumber: { type: String, required: true, unique: true },
  businessType: String,
  employees: Number,
  establishedYear: Number,
  revenue: Number,
  creditRating: String,
  phone: String,
  address: String,
  representative: String,
  createdAt: { type: Date, default: Date.now },
  updatedAt: { type: Date, default: Date.now }
}, { collection: 'companies' });

// 3. 평가 스키마
const evaluationSchema = new mongoose.Schema({
  announcementId: mongoose.Schema.Types.ObjectId,
  announcementNumber: String,
  announcementTitle: String,
  companyId: mongoose.Schema.Types.ObjectId,
  companyName: String,
  registrationNumber: String,
  financialScore: Number,
  experienceScore: Number,
  creditScore: Number,
  totalScore: Number,
  financialDetails: {
    revenueScore: Number,
    profitMarginScore: Number,
    debtRatioScore: Number,
    notes: String
  },
  experienceDetails: {
    yearsInBusiness: Number,
    similarProjectCount: Number,
    notes: String
  },
  creditDetails: {
    creditRating: String,
    ratingScore: Number,
    notes: String
  },
  evaluationStatus: { type: String, enum: ['진행', '평가중', '완료'], default: '진행' },
  rank: Number,
  evaluatedAt: Date,
  evaluatedBy: String,
  notes: String,
  createdAt: { type: Date, default: Date.now },
  updatedAt: { type: Date, default: Date.now }
}, { collection: 'evaluations' });

// 4. 사용자 스키마 (인증용)
const userSchema = new mongoose.Schema({
  username: { type: String, required: true, unique: true },
  email: { type: String, required: true, unique: true },
  password: { type: String, required: true },
  role: { type: String, enum: ['user', 'admin'], default: 'user' },
  createdAt: { type: Date, default: Date.now }
}, { collection: 'users' });

const Announcement = mongoose.model('Announcement', announcementSchema);
const Company = mongoose.model('Company', companySchema);
const Evaluation = mongoose.model('Evaluation', evaluationSchema);
const User = mongoose.model('User', userSchema);

// ===== 인증 미들웨어 =====
function authenticateToken(req, res, next) {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];

  if (!token) {
    return res.status(401).json({ success: false, error: '토큰 없음' });
  }

  jwt.verify(token, JWT_SECRET, (err, user) => {
    if (err) {
      return res.status(403).json({ success: false, error: '토큰 무효' });
    }
    req.user = user;
    next();
  });
}

// ===== API: 필터 옵션 =====
app.get('/api/filter-options', async (req, res) => {
  try {
    const agencies = await Announcement.distinct('agencyName');
    const workTypes = await Announcement.distinct('workType');
    const regions = await Announcement.distinct('region');

    res.json({
      agencies: agencies.filter(a => a).sort(),
      workTypes: workTypes.filter(w => w).sort(),
      regions: regions.filter(r => r).sort()
    });
  } catch (error) {
    console.error('필터 옵션 조회 에러:', error);
    res.status(500).json({ error: error.message });
  }
});

// ===== API: 공고 검색 =====
app.get('/api/announcements/search', async (req, res) => {
  try {
    const { agencyName, workType, region } = req.query;
    let filter = {};

    if (agencyName && agencyName !== 'all') {
      filter.agencyName = agencyName;
    }
    if (workType && workType !== 'all') {
      filter.workType = workType;
    }
    if (region && region !== 'all') {
      filter.region = region;
    }

    const announcements = await Announcement.find(filter).limit(100).sort({ createdAt: -1 });

    res.json({
      success: true,
      count: announcements.length,
      data: announcements.map(ann => ({
        _id: ann._id,
        announcementNumber: ann.announcementNumber,
        title: ann.title,
        agencyName: ann.agencyName || '미분류',
        workType: ann.workType || '분류',
        region: ann.region || '전국',
        basicAmount: ann.basicAmount || ann.budget || 0
      }))
    });
  } catch (error) {
    console.error('검색 에러:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

// ===== API: 전체 공고 =====
app.get('/api/announcements', async (req, res) => {
  try {
    const announcements = await Announcement.find().limit(50).sort({ createdAt: -1 });

    res.json({
      success: true,
      count: announcements.length,
      data: announcements.map(ann => ({
        _id: ann._id,
        announcementNumber: ann.announcementNumber,
        title: ann.title,
        agencyName: ann.agencyName || '미분류',
        workType: ann.workType || '분류',
        region: ann.region || '전국',
        basicAmount: ann.basicAmount || ann.budget || 0
      }))
    });
  } catch (error) {
    console.error('공고 조회 에러:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

// ===== API: 통계 =====
app.get('/api/statistics', async (req, res) => {
  try {
    const byAgency = await Announcement.aggregate([
      {
        $group: {
          _id: '$agencyName',
          count: { $sum: 1 },
          totalBudget: { $sum: '$basicAmount' },
          avgBudget: { $avg: '$basicAmount' }
        }
      },
      { $sort: { count: -1 } }
    ]);

    const byWorkType = await Announcement.aggregate([
      {
        $group: {
          _id: '$workType',
          count: { $sum: 1 },
          totalBudget: { $sum: '$basicAmount' }
        }
      },
      { $sort: { count: -1 } }
    ]);

    const byRegion = await Announcement.aggregate([
      {
        $group: {
          _id: '$region',
          count: { $sum: 1 },
          totalBudget: { $sum: '$basicAmount' }
        }
      },
      { $sort: { count: -1 } }
    ]);

    const totalAnnouncements = await Announcement.countDocuments();
    const totalBudget = await Announcement.aggregate([
      { $group: { _id: null, total: { $sum: '$basicAmount' } } }
    ]);

    res.json({
      success: true,
      totalAnnouncements,
      totalBudget: totalBudget[0]?.total || 0,
      byAgency,
      byWorkType,
      byRegion
    });
  } catch (error) {
    console.error('통계 조회 에러:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

// ===== API: 기업 관리 =====

// 기업 목록 조회
app.get('/api/companies', async (req, res) => {
  try {
    const companies = await Company.find().sort({ createdAt: -1 });
    res.json({ success: true, count: companies.length, data: companies });
  } catch (error) {
    console.error('기업 조회 에러:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

// 기업 등록
app.post('/api/companies', async (req, res) => {
  try {
    const newCompany = new Company(req.body);
    const saved = await newCompany.save();
    res.json({ success: true, data: saved });
  } catch (error) {
    console.error('기업 등록 에러:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

// 기업 상세 조회
app.get('/api/companies/:id', async (req, res) => {
  try {
    const company = await Company.findById(req.params.id);
    if (!company) return res.status(404).json({ success: false, error: '기업을 찾을 수 없습니다' });
    res.json({ success: true, data: company });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// 기업 수정
app.put('/api/companies/:id', async (req, res) => {
  try {
    const updated = await Company.findByIdAndUpdate(req.params.id, req.body, { new: true });
    res.json({ success: true, data: updated });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// 기업 삭제 (추가 기능 3)
app.delete('/api/companies/:id', async (req, res) => {
  try {
    const company = await Company.findByIdAndDelete(req.params.id);
    if (!company) return res.status(404).json({ success: false, error: '기업을 찾을 수 없습니다' });
    
    // 해당 기업의 평가 기록도 삭제
    await Evaluation.deleteMany({ companyId: req.params.id });
    
    res.json({ success: true, message: '기업 및 평가 기록이 삭제되었습니다' });
  } catch (error) {
    console.error('기업 삭제 에러:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

// ===== API: 평가 계산 함수 =====
function calculateEvaluation(company, announcement) {
  let financialScore = 0;
  const revenueScore = Math.min((company.revenue || 0) / 100000000 * 30, 30);
  const yearsInBusiness = new Date().getFullYear() - (company.establishedYear || 2024);
  const profitMarginScore = yearsInBusiness >= 5 ? 35 : 20;
  const debtRatioScore = 35;
  financialScore = Math.round(revenueScore + profitMarginScore + debtRatioScore);

  let experienceScore = 0;
  const yearsScore = Math.min(yearsInBusiness * 10, 50);
  const businessTypeScore = company.businessType === '건설' ? 30 : 20;
  const employeeScore = (company.employees || 10) > 50 ? 20 : 10;
  experienceScore = Math.round(yearsScore + businessTypeScore + employeeScore);

  let creditScore = 0;
  const creditRatingMap = { 'AAA': 100, 'AA': 90, 'A': 80, 'BBB': 70, 'BB': 60, 'B': 50 };
  creditScore = creditRatingMap[company.creditRating] || 50;

  const totalScore = Math.round((financialScore * 0.4 + experienceScore * 0.3 + creditScore * 0.3));

  return {
    financialScore: Math.min(financialScore, 100),
    experienceScore: Math.min(experienceScore, 100),
    creditScore: creditScore,
    totalScore: totalScore,
    financialDetails: {
      revenueScore: Math.round(revenueScore),
      profitMarginScore: profitMarginScore,
      debtRatioScore: debtRatioScore,
      notes: `매출액: ${company.revenue || 0}원, 경영지수: ${yearsInBusiness}년`
    },
    experienceDetails: {
      yearsInBusiness: yearsInBusiness,
      similarProjectCount: 0,
      notes: `설립년도: ${company.establishedYear}, 직원수: ${company.employees || 0}명`
    },
    creditDetails: {
      creditRating: company.creditRating || 'BB',
      ratingScore: creditScore,
      notes: `신용등급: ${company.creditRating || 'BB'}`
    }
  };
}

// ===== API: 평가 =====

// 평가 생성/계산
app.post('/api/evaluations', async (req, res) => {
  try {
    const { announcementId, companyId, evaluatedBy } = req.body;

    const announcement = await Announcement.findById(announcementId);
    const company = await Company.findById(companyId);

    if (!announcement || !company) {
      return res.status(404).json({ success: false, error: '공고 또는 기업을 찾을 수 없습니다' });
    }

    const scores = calculateEvaluation(company, announcement);

    const evaluation = new Evaluation({
      announcementId,
      announcementNumber: announcement.announcementNumber,
      announcementTitle: announcement.title,
      companyId,
      companyName: company.companyName,
      registrationNumber: company.registrationNumber,
      ...scores,
      evaluationStatus: '완료',
      evaluatedAt: new Date(),
      evaluatedBy: evaluatedBy || '시스템'
    });

    const saved = await evaluation.save();
    res.json({ success: true, data: saved });
  } catch (error) {
    console.error('평가 생성 에러:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

// 공고별 평가 조회 및 순위 (추가 기능 2)
app.get('/api/evaluations/announcement/:announcementId', async (req, res) => {
  try {
    const evaluations = await Evaluation.find({ announcementId: req.params.announcementId }).sort({ totalScore: -1 });

    const ranked = evaluations.map((eval, idx) => ({
      ...eval.toObject(),
      rank: idx + 1
    }));

    res.json({ success: true, count: ranked.length, data: ranked });
  } catch (error) {
    console.error('평가 조회 에러:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

// 평가 히스토리 조회 (추가 기능 1)
app.get('/api/evaluation-history', async (req, res) => {
  try {
    const { companyId, announcementId, limit = 50 } = req.query;
    let filter = {};

    if (companyId) filter.companyId = new mongoose.Types.ObjectId(companyId);
    if (announcementId) filter.announcementId = new mongoose.Types.ObjectId(announcementId);

    const history = await Evaluation.find(filter)
      .sort({ createdAt: -1 })
      .limit(parseInt(limit));

    res.json({ success: true, count: history.length, data: history });
  } catch (error) {
    console.error('히스토리 조회 에러:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

// 평가 삭제
app.delete('/api/evaluations/:id', async (req, res) => {
  try {
    const evaluation = await Evaluation.findByIdAndDelete(req.params.id);
    if (!evaluation) return res.status(404).json({ success: false, error: '평가를 찾을 수 없습니다' });
    res.json({ success: true, message: '평가가 삭제되었습니다' });
  } catch (error) {
    console.error('평가 삭제 에러:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

// ===== API: Excel 다운로드 (추가 기능 4) =====
app.get('/api/export/evaluations-excel', async (req, res) => {
  try {
    const { announcementId } = req.query;
    let filter = {};
    if (announcementId) {
      filter.announcementId = new mongoose.Types.ObjectId(announcementId);
    }

    const evaluations = await Evaluation.find(filter).sort({ totalScore: -1 });

    const workbook = new ExcelJS.Workbook();
    const worksheet = workbook.addWorksheet('평가 결과');

    // 헤더
    worksheet.columns = [
      { header: '순위', key: 'rank', width: 10 },
      { header: '공고번호', key: 'announcementNumber', width: 15 },
      { header: '공고명', key: 'announcementTitle', width: 30 },
      { header: '기업명', key: 'companyName', width: 20 },
      { header: '사업자등록번호', key: 'registrationNumber', width: 18 },
      { header: '재정점수', key: 'financialScore', width: 12 },
      { header: '경험점수', key: 'experienceScore', width: 12 },
      { header: '신용점수', key: 'creditScore', width: 12 },
      { header: '총점', key: 'totalScore', width: 10 },
      { header: '평가상태', key: 'evaluationStatus', width: 12 },
      { header: '평가일시', key: 'evaluatedAt', width: 20 }
    ];

    // 데이터
    evaluations.forEach((eval, idx) => {
      worksheet.addRow({
        rank: idx + 1,
        announcementNumber: eval.announcementNumber,
        announcementTitle: eval.announcementTitle,
        companyName: eval.companyName,
        registrationNumber: eval.registrationNumber,
        financialScore: eval.financialScore,
        experienceScore: eval.experienceScore,
        creditScore: eval.creditScore,
        totalScore: eval.totalScore,
        evaluationStatus: eval.evaluationStatus,
        evaluatedAt: eval.evaluatedAt ? new Date(eval.evaluatedAt).toLocaleString('ko-KR') : ''
      });
    });

    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    res.setHeader('Content-Disposition', 'attachment; filename=evaluation_results.xlsx');
    await workbook.xlsx.write(res);
    res.end();
  } catch (error) {
    console.error('Excel 내보내기 에러:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

// ===== API: PDF 다운로드 (추가 기능 4) =====
app.get('/api/export/evaluations-pdf', async (req, res) => {
  try {
    const { announcementId } = req.query;
    let filter = {};
    if (announcementId) {
      filter.announcementId = new mongoose.Types.ObjectId(announcementId);
    }

    const evaluations = await Evaluation.find(filter).sort({ totalScore: -1 });

    const doc = new PDFDocument({ margin: 50, bufferPages: true });
    res.setHeader('Content-Type', 'application/pdf');
    res.setHeader('Content-Disposition', 'attachment; filename=evaluation_results.pdf');

    doc.pipe(res);

    // 제목
    doc.fontSize(20).font('Courier').text('입찰 적격성 평가 결과', { align: 'center' });
    doc.moveDown();
    doc.fontSize(12).text(`생성일: ${new Date().toLocaleString('ko-KR')}`);
    doc.moveDown();

    // 테이블 헤더
    const startX = 50;
    const startY = doc.y;
    const colWidths = [40, 80, 120, 120, 60, 60, 60];
    const headers = ['순위', '공고번호', '기업명', '사업자등록번호', '총점', '상태', '평가일'];

    headers.forEach((header, i) => {
      doc.fontSize(10).text(header, startX + colWidths.slice(0, i).reduce((a, b) => a + b, 0), startY, {
        width: colWidths[i],
        align: 'center'
      });
    });

    doc.moveTo(startX, startY + 20).lineTo(startX + colWidths.reduce((a, b) => a + b, 0), startY + 20).stroke();
    doc.moveDown(2);

    // 데이터
    evaluations.forEach((eval, idx) => {
      const y = doc.y;
      doc.fontSize(9);
      const row = [
        idx + 1,
        eval.announcementNumber,
        eval.companyName,
        eval.registrationNumber,
        eval.totalScore,
        eval.evaluationStatus,
        eval.evaluatedAt ? new Date(eval.evaluatedAt).toLocaleDateString('ko-KR') : ''
      ];

      row.forEach((cell, i) => {
        doc.text(String(cell), startX + colWidths.slice(0, i).reduce((a, b) => a + b, 0), y, {
          width: colWidths[i],
          align: 'center'
        });
      });

      doc.moveDown(1.5);
    });

    doc.end();
  } catch (error) {
    console.error('PDF 내보내기 에러:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

// ===== API: 사용자 인증 (추가 기능 5) =====

// 회원가입
app.post('/api/auth/signup', async (req, res) => {
  try {
    const { username, email, password } = req.body;

    // 중복 확인
    const existing = await User.findOne({ $or: [{ username }, { email }] });
    if (existing) {
      return res.status(400).json({ success: false, error: '이미 존재하는 사용자입니다' });
    }

    // 비밀번호 해시화
    const hashedPassword = await bcryptjs.hash(password, 10);

    const newUser = new User({
      username,
      email,
      password: hashedPassword,
      role: 'user'
    });

    const saved = await newUser.save();
    res.json({ success: true, message: '회원가입 성공', user: { username: saved.username, email: saved.email } });
  } catch (error) {
    console.error('회원가입 에러:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

// 로그인
app.post('/api/auth/login', async (req, res) => {
  try {
    const { username, password } = req.body;

    const user = await User.findOne({ username });
    if (!user) {
      return res.status(401).json({ success: false, error: '사용자를 찾을 수 없습니다' });
    }

    const isPasswordValid = await bcryptjs.compare(password, user.password);
    if (!isPasswordValid) {
      return res.status(401).json({ success: false, error: '비밀번호가 틀렸습니다' });
    }

    // JWT 토큰 생성
    const token = jwt.sign({ userId: user._id, username: user.username, role: user.role }, JWT_SECRET, { expiresIn: '7d' });

    res.json({ success: true, token, user: { username: user.username, email: user.email, role: user.role } });
  } catch (error) {
    console.error('로그인 에러:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

// 현재 사용자 정보
app.get('/api/auth/me', authenticateToken, async (req, res) => {
  try {
    const user = await User.findById(req.user.userId).select('-password');
    res.json({ success: true, user });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// 서버 시작
app.listen(PORT, () => {
  console.log(`🚀 서버 실행 중 @ http://localhost:${PORT}`);
});
