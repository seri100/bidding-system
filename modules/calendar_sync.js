const { google } = require('googleapis');

const CALENDAR_ID = 'primary';

function parseMessageToEvent(messageText) {
    const lines = messageText.split('\n');
    const event = {};

    lines.forEach(line => {
        const parts = line.split(':');
        if (parts.length < 2) return;
        
        const key = parts[0].trim();
        const value = parts.slice(1).join(':').trim();
        
        if (key === '공고명') event.title = value;
        else if (key === '입찰마감일시') event.deadline = value;
        else if (key === '공고번호') event.bidNo = value;
        else if (key === '공동도급지역') event.region = value;
        else if (key === '추정금액') event.budget = value;
        else if (key === '발주기관') event.agency = value;
        else if (key === '업종') event.category = value;
        else if (key === '낙찰방법') event.awardMethod = value;
        else if (key === '상세URL') event.detailUrl = value;
    });

    return event;
}

async function syncMessageToGcal(messageText, user, logger = null) {
    try {
        const event = parseMessageToEvent(messageText);

        if (!event.title || !event.deadline) {
            if (logger) logger.warn('[GCAL] 필수 필드 누락: 공고명 또는 입찰마감일시');
            return { success: false, error: 'Missing required fields' };
        }

        const [bidNo, bidOrd] = (event.bidNo || '').split('-');
        const eventKey = `${bidNo}-${bidOrd || '000'}`;

        const oauth2Client = new google.auth.OAuth2(
            process.env.GOOGLE_CLIENT_ID,
            process.env.GOOGLE_CLIENT_SECRET,
            process.env.GOOGLE_REDIRECT_URI
        );

        oauth2Client.setCredentials({
            access_token: user.accessToken,
            refresh_token: user.refreshToken
        });

        const calendar = google.calendar({ version: 'v3', auth: oauth2Client });

        const deadlineDate = new Date(event.deadline);
        const startTime = new Date(deadlineDate.getTime() - 60 * 60 * 1000);

        const gcalEvent = {
            summary: `[입찰] ${event.title}`,
            description: `공고번호: ${event.bidNo}\n지역: ${event.region}\n예산: ${event.budget}\n발주기관: ${event.agency}\n업종: ${event.category}\n낙찰방법: ${event.awardMethod}\n상세URL: ${event.detailUrl}`,
            start: {
                dateTime: startTime.toISOString(),
                timeZone: 'Asia/Seoul'
            },
            end: {
                dateTime: deadlineDate.toISOString(),
                timeZone: 'Asia/Seoul'
            },
            location: event.region,
            reminders: {
                useDefault: false,
                overrides: [
                    { method: 'notification', minutes: 60 },
                    { method: 'notification', minutes: 10 }
                ]
            }
        };

        const response = await calendar.events.insert({
            calendarId: CALENDAR_ID,
            resource: gcalEvent
        });

        if (logger) logger.info(`[GCAL] 이벤트 생성 성공: ${event.title}`);

        return {
            success: true,
            eventId: response.data.id,
            eventKey: eventKey
        };

    } catch (err) {
        if (logger) logger.error(`[GCAL][ERROR] ${err.message}`);
        return { success: false, error: err.message };
    }
}

async function syncGoogleCalendar(announcementData, user, logger = null) {
    const [bidNo, bidOrd] = (announcementData.bidNo || '').split('-');
    
    const message = `[입찰마감]
공고명 : ${announcementData.title || ''}
입찰마감일시 : ${announcementData.deadline || ''}
공동도급지역 : ${announcementData.region || ''}
추정금액 : ${announcementData.budget || ''}
공고번호 : ${bidNo || ''} - ${bidOrd || '000'}

발주기관 : ${announcementData.agency || ''}
업종 : ${announcementData.category || ''}
낙찰방법 : ${announcementData.awardMethod || ''}
상세URL : ${announcementData.detailUrl || ''}
`;

    return syncMessageToGcal(message, user, logger);
}

module.exports = {
    parseMessageToEvent,
    syncMessageToGcal,
    syncGoogleCalendar
};
