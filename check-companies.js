const mongoose = require('mongoose');
const schema = new mongoose.Schema({}, {strict: false});
const Company = mongoose.model('companies', schema);

mongoose.connect('mongodb://localhost:27017/bidding_system').then(async () => {
  const count = await Company.countDocuments();
  console.log('✓ 총 업체 수:', count);
  const sample = await Company.find().limit(5);
  console.log('\n📌 첫 5개 업체:');
  sample.forEach((c, i) => console.log((i+1) + '. ' + (c.companyName || c['상호'] || '(이름없음)')));
  mongoose.disconnect();
}).catch(e => console.error('오류:', e.message));
