// 회사 기술/재무/이력 점수 산정 (가중치: 40/30/30)
async function evaluateCompany(company, bidCriteria) {
    const technicalScore = evaluateTechnical(company, bidCriteria) * 0.4;
    const financialScore = evaluateFinancial(company) * 0.3;
    const historyScore = evaluateHistory(company) * 0.3;

    return {
        technicalScore,
        financialScore,
        historyScore,
        totalScore: technicalScore + financialScore + historyScore,
        details: {
            licenses: company.licenses || [],
            safetyRating: company.safetyRating || 0,
            pastProjects: company.pastProjects || [],
            creditRating: company.creditRating || 'N/A',
        }
    };
}

function evaluateTechnical(company, bidCriteria) {
    let score = 0;
    if (company.licenses && company.licenses.length > 0) score += 20;
    if (company.technicians && company.technicians.length > 0) score += 20;
    if (company.safetyRating && company.safetyRating > 80) score += 20;
    if (company.equipment && company.equipment.length > 0) score += 20;
    if (company.certifications && company.certifications.length > 0) score += 20;
    return Math.min(score, 100);
}

function evaluateFinancial(company) {
    let score = 50;
    if (company.debtRatio && company.debtRatio < 50) score += 30;
    else if (company.debtRatio && company.debtRatio < 100) score += 15;
    if (company.revenueGrowth && company.revenueGrowth > 10) score += 20;
    return Math.min(score, 100);
}

function evaluateHistory(company) {
    let score = 0;
    if (company.pastProjects) {
        score += Math.min(company.pastProjects.length * 5, 50);
    }
    if (company.successRate && company.successRate > 95) score += 30;
    else if (company.successRate && company.successRate > 85) score += 15;
    return Math.min(score, 100);
}

module.exports = { evaluateCompany };
