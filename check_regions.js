const mongoose = require("mongoose");
require("dotenv").config({ path: "C:\\bidding-system\\.env.raspberry" });

const announcementSchema = new mongoose.Schema({}, { strict: false });
const Announcement = mongoose.model("Announcement", announcementSchema);

mongoose.connect(process.env.MONGODB_URI || "mongodb://localhost:27017/bidding_system")
  .then(async () => {
    const regions = await Announcement.aggregate([
      { $group: { _id: "$region", count: { $sum: 1 } } },
      { $sort: { count: -1 } }
    ]);
    console.log("📍 실제 저장된 Region 값들:");
    regions.forEach(r => console.log(`  ${r._id}: ${r.count}개`));
    process.exit(0);
  })
  .catch(err => console.error(err));
