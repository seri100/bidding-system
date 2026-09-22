const mongoose = require("mongoose");
require("dotenv").config({ path: "C:\\bidding-system\\.env.raspberry" });

const announcementSchema = new mongoose.Schema({}, { strict: false });
const Announcement = mongoose.model("Announcement", announcementSchema);

mongoose.connect(process.env.MONGODB_URI || "mongodb://localhost:27017/bidding_system")
  .then(async () => {
    console.log("🔍 충북 관련 공고 검색:");
    
    // 정확히 "충북"으로 저장된 것
    const exact = await Announcement.countDocuments({ region: "충북" });
    console.log(`✅ region = "충북": ${exact}개`);
    
    // "충청북도"로 저장된 것
    const full = await Announcement.countDocuments({ region: "충청북도" });
    console.log(`❓ region = "충청북도": ${full}개`);
    
    // 충북이 포함된 모든 것
    const regex = await Announcement.countDocuments({ region: { $regex: "충", $options: "i" } });
    console.log(`🔎 region에 "충"이 포함된 것: ${regex}개`);
    
    // 실제 충북 공고 샘플 조회
    const samples = await Announcement.find({ region: "충북" }).limit(3).lean();
    console.log("\n📋 충북 공고 샘플:");
    samples.forEach(s => console.log(`  - ${s.title || s.announcementNumber}`));
    
    process.exit(0);
  })
  .catch(err => console.error(err));
