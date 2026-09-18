const mongoose = require('mongoose');

const mongoUri = 'mongodb://localhost:27017/bidding_system';

(async () => {
  try {
    await mongoose.connect(mongoUri, { useNewUrlParser: true, useUnifiedTopology: true });
    console.log('✅ MongoDB 연결 성공');

    // companies 컬렉션 삭제 후 재생성
    const db = mongoose.connection.db;
    try {
      await db.dropCollection('companies');
      console.log('✅ companies 컬렉션 삭제됨');
    } catch (e) {
      console.log('ℹ️  companies 컬렉션이 없습니다');
    }

    // 컬렉션 재생성 (unique 제약 제거)
    const companySchema = new mongoose.Schema({
      companyName: { type: String, required: true },
      registrationNumber: { type: String, required: true },
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

    const Company = mongoose.model('Company', companySchema);

    // 샘플 데이터 추가
    const sampleCompanies = [
      {
        companyName: '한국건설공사',
        registrationNumber: '123-45-67890',
        businessType: '건설',
        employees: 150,
        establishedYear: 2010,
        revenue: 5000000000,
        creditRating: 'AAA',
        representative: '김철수',
        phone: '02-1234-5678',
        address: '서울시 강남구'
      },
      {
        companyName: '서울정보통신',
        registrationNumber: '234-56-78901',
        businessType: '용역',
        employees: 80,
        establishedYear: 2015,
        revenue: 3000000000,
        creditRating: 'AA',
        representative: '이영희',
        phone: '02-2345-6789',
        address: '서울시 서초구'
      },
      {
        companyName: '부산제조산업',
        registrationNumber: '345-67-89012',
        businessType: '제조',
        employees: 200,
        establishedYear: 2008,
        revenue: 8000000000,
        creditRating: 'A',
        representative: '박민수',
        phone: '051-3456-7890',
        address: '부산시 사하구'
      },
      {
        companyName: '대전솔루션',
        registrationNumber: '456-78-90123',
        businessType: '용역',
        employees: 50,
        establishedYear: 2018,
        revenue: 1500000000,
        creditRating: 'BBB',
        representative: '최지현',
        phone: '042-4567-8901',
        address: '대전시 중구'
      },
      {
        companyName: '인천종합물류',
        registrationNumber: '567-89-01234',
        businessType: '용역',
        employees: 120,
        establishedYear: 2012,
        revenue: 4000000000,
        creditRating: 'A',
        representative: '정상훈',
        phone: '032-5678-9012',
        address: '인천시 남동구'
      }
    ];

    await Company.insertMany(sampleCompanies);
    console.log('✅ 5개의 샘플 회사 데이터 추가됨');

    const count = await Company.countDocuments();
    console.log(`📊 현재 companies 컬렉션: ${count}개`);

    await mongoose.disconnect();
    console.log('✅ 작업 완료');
    process.exit(0);
  } catch (err) {
    console.error('❌ 오류:', err.message);
    process.exit(1);
  }
})();
