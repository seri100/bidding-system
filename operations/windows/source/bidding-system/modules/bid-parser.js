const axios = require('axios');
const cheerio = require('cheerio');

// 1. 공고 상세 URL에서 정보 추출
async function parseBidAnnouncement(announcementUrl) {
    try {
        const { data } = await axios.get(announcementUrl);
        const $ = cheerio.load(data);

        return {
            title: $('h1.announcement-title').text().trim(),
            agency: $('[data-agency]').text().trim(),
            estimatedPrice: parseInt($('[data-price]').text().replace(/[^0-9]/g, '')),
            deadline: new Date($('[data-deadline]').attr('datetime')),
            category: classifyCategory($('h1.announcement-title').text()),
            biddingItems: extractBiddingItems($),
            evaluationCriteria: extractEvaluationCriteria($),
            technicalRequirements: extractTechnicalRequirements($),
            qualifications: extractQualifications($),
            url: announcementUrl,
            parsedAt: new Date()
        };
    } catch (err) {
        console.error('공고 파싱 실패:', err.message);
        throw err;
    }
}

// 카테고리 분류
function classifyCategory(title) {
    if (title.includes('소방')) return '소방';
    if (title.includes('기계') || title.includes('설비')) return '기계설비';
    if (title.includes('전기')) return '전기';
    return '기타';
}

// 평가 기준 추출
function extractEvaluationCriteria($) {
    const criteria = [];
    $('table.evaluation-table tr').each((i, el) => {
        criteria.push({
            item: $(el).find('td:nth-child(1)').text().trim(),
            weight: parseFloat($(el).find('td:nth-child(2)').text()),
            maxScore: parseFloat($(el).find('td:nth-child(3)').text()),
        });
    });
    return criteria;
}

// 기술요건 추출
function extractTechnicalRequirements($) {
    return {
        constructionExperience: $('[data-experience]').text(),
        licenses: $('[data-licenses]').text().split(','),
        technicians: $('[data-technicians]').text().split(','),
        equipment: $('[data-equipment]').text().split(','),
    };
}

// 자격요건 추출
function extractQualifications($) {
    return {
        creditRating: $('[data-credit]').text(),
        debtRatio: parseFloat($('[data-debt]').text()),
        safetyManagement: parseFloat($('[data-safety]').text()),
    };
}

// 입찰 항목 추출
function extractBiddingItems($) {
    const items = [];
    $('table.bidding-items tr').each((i, el) => {
        items.push({
            itemName: $(el).find('td:nth-child(1)').text().trim(),
            quantity: parseFloat($(el).find('td:nth-child(2)').text()),
            unit: $(el).find('td:nth-child(3)').text().trim(),
            unitPrice: parseFloat($(el).find('td:nth-child(4)').text().replace(/[^0-9.]/g, '')),
        });
    });
    return items;
}

module.exports = { parseBidAnnouncement };
