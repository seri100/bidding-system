const mongoose = REDACTED_PRIVATE_VALUE
mongoose.connect('REDACTED_PRIVATE_VALUE').then(async () => {
  const count = await mongoose.connection.db.collection('companies').countDocuments();
  const sample = await mongoose.connection.db.collection('companies').findOne();
  console.log('총 레코드:', count);
  console.log('샘플 데이터:');
  console.log('companyName:', sample.companyName);
  console.log('region:', sample.region);
  console.log('businessRegistration:', sample.businessRegistration);
  mongoose.disconnect();
});
