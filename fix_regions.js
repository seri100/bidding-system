const mongoose = require("mongoose");
require("dotenv").config({ path: "C:\\bidding-system\\.env.raspberry" });

const announcementSchema = new mongoose.Schema({}, { strict: false });
const Announcement = mongoose.model("Announcement", announcementSchema);

mongoose.connect(process.env.MONGODB_URI || "mongodb://localhost:27017/bidding_system")
  .then(async () => {
    console.log("🔧 지역 데이터 정규화 시작...");
    
    // null 제거
    const nullCount = await Announcement.countDocuments({ region: null });
    await Announcement.updateMany({ region: null }, { $set: { region: "전국" } });
    console.log(`✅ null → "전국": ${nullCount}개 수정`);
    
    // 정규화 규칙
    const regionMap = {
      "서울시": "서울",
      "서울특별시": "서울",
      "경기도": "경기도",
      "경기": "경기도",
      "강원도": "강원도",
      "강원": "강원도",
      "충청북도": "충북",
      "충청남도": "충남",
      "전라북도": "전북",
      "전라남도": "전남",
      "경상북도": "경북",
      "경상남도": "경남",
      "제주도": "제주",
      "제주특별자치도": "제주",
      "대구광역시": "대구",
      "부산광역시": "부산",
      "대전광역시": "대전",
      "인천광역시": "인천",
      "울산광역시": "울산",
      "광주광역시": "광주"
    };
    
    for (const [old, newVal] of Object.entries(regionMap)) {
      const count = await Announcement.countDocuments({ region: old });
      if (count > 0) {
        await Announcement.updateMany({ region: old }, { $set: { region: newVal } });
        console.log(`✅ "${old}" → "${newVal}": ${count}개 수정`);
      }
    }
    
    console.log("\n✨ 정규화 완료! 현재 지역 분포:");
    const regions = await Announcement.aggregate([
      { $group: { _id: "$region", count: { $sum: 1 } } },
      { $sort: { count: -1 } }
    ]);
    regions.forEach(r => console.log(`  ${r._id}: ${r.count}개`));
    
    process.exit(0);
  })
  .catch(err => console.error(err));
