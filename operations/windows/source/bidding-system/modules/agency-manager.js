const fs = require('fs');
const path = require('path');

class AgencyManager {
  constructor() {
    this.agencies = {};
    this.loadAllAgencies();
  }

  loadAllAgencies() {
    const agencyDir = path.join(__dirname, '..', 'config', 'agencies');
    
    if (!fs.existsSync(agencyDir)) {
      console.log('⚠️ 기관 설정 폴더가 없습니다');
      return;
    }

    const files = fs.readdirSync(agencyDir).filter(f => f.endsWith('.js'));
    
    files.forEach(file => {
      try {
        const agencyConfig = require(path.join(agencyDir, file));
        this.agencies[agencyConfig.code] = agencyConfig;
        console.log(`✅ 기관 로드: ${agencyConfig.name}`);
      } catch (err) {
        console.error(`❌ 기관 로드 실패 (${file}):`, err.message);
      }
    });
  }

  getAllAgencies() {
    return Object.values(this.agencies).map(a => ({
      code: a.code,
      name: a.name,
      evaluationMethod: a.evaluationMethod,
      scoringCriteria: a.scoringCriteria
    }));
  }

  getAgencyByCode(code) {
    return this.agencies[code] || null;
  }

  getAgencyByName(name) {
    return Object.values(this.agencies).find(a => a.name === name) || null;
  }

  getScoringCriteria(agencyCode) {
    const agency = this.agencies[agencyCode];
    return agency ? agency.scoringCriteria : null;
  }

  getBidCalculationRange(agencyCode) {
    const agency = this.agencies[agencyCode];
    if (!agency) return null;
    
    return {
      minDiscount: agency.bidCalculation.baseDiscount.min,
      maxDiscount: agency.bidCalculation.baseDiscount.max,
      profitMargin: agency.bidCalculation.profitMargin
    };
  }

  calculateAValue(basicAmount, agencyCode) {
    const agency = this.agencies[agencyCode];
    if (!agency) return null;

    const aValue = agency.aValue;
    return {
      nationalPension: basicAmount * aValue.nationalPension,
      healthInsurance: basicAmount * aValue.healthInsurance,
      employmentInsurance: basicAmount * aValue.employmentInsurance,
      industrialAccident: basicAmount * aValue.industrialAccident,
      safetyManagement: basicAmount * aValue.safetyManagement,
      total: basicAmount * Object.values(aValue).reduce((a, b) => a + b, 0)
    };
  }
}

module.exports = new AgencyManager();
