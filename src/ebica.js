import { load } from 'cheerio';

const AVAILABLE_MARKS = new Set(['○', '◯']);

export async function fetchAvailability({ url, targetDate, targetTimes }) {
  const response = await fetch(url, {
    headers: {
      'accept-language': 'ja,en-US;q=0.9,en;q=0.8',
      'cache-control': 'no-cache',
      pragma: 'no-cache',
      'user-agent':
        'Mozilla/5.0 (compatible; reservation-cancel-watch/1.0; +https://github.com/)',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch reservation page: ${response.status} ${response.statusText}`);
  }

  const html = await response.text();
  return parseAvailability(html, { targetDate, targetTimes, url });
}

export function parseAvailability(html, { targetDate, targetTimes, url }) {
  const $ = load(html);
  const yearMonthLabel = findYearMonthLabel($);
  if (!yearMonthLabel) {
    throw new Error('Could not find the calendar month label in the reservation page.');
  }

  const visibleDates = extractVisibleDates($, yearMonthLabel);
  const targetColumnIndex = visibleDates.findIndex((date) => date === targetDate);
  if (targetColumnIndex === -1) {
    throw new Error(
      `Target date ${targetDate} is not visible in the current calendar week (${visibleDates.join(', ')}).`,
    );
  }

  const rows = extractTimeRows($);
  const slots = targetTimes.map((time) => {
    const status = rows.get(time)?.[targetColumnIndex] || 'unknown';
    return {
      date: targetDate,
      time,
      status,
      available: AVAILABLE_MARKS.has(status),
    };
  });

  return {
    checkedAt: new Date().toISOString(),
    url,
    targetDate,
    targetTimes,
    visibleDates,
    slots,
    availableSlots: slots.filter((slot) => slot.available),
  };
}

function findYearMonthLabel($) {
  const labels = [];
  $('span, div').each((_, element) => {
    const text = normalizeText($(element).text());
    if (/^\d{4}年\d{1,2}月$/.test(text)) {
      labels.push(text);
    }
  });
  return labels[0] || null;
}

function extractVisibleDates($, yearMonthLabel) {
  const match = yearMonthLabel.match(/^(\d{4})年(\d{1,2})月$/);
  if (!match) {
    throw new Error(`Invalid calendar month label: ${yearMonthLabel}`);
  }

  let year = Number(match[1]);
  let month = Number(match[2]);
  let previousDay = null;

  const headerCells = $('table')
    .first()
    .find('thead th')
    .toArray()
    .map((element) => normalizeText($(element).text()))
    .filter((text) => /^\d{1,2}\s+[日月火水木金土]$/.test(text));

  if (headerCells.length === 0) {
    throw new Error('Could not find calendar date headers.');
  }

  return headerCells.map((text) => {
    const day = Number(text.match(/^(\d{1,2})/)?.[1]);
    if (previousDay !== null && day < previousDay) {
      month += 1;
      if (month > 12) {
        month = 1;
        year += 1;
      }
    }
    previousDay = day;
    return formatDate(year, month, day);
  });
}

function extractTimeRows($) {
  const bodyTable = $('table').eq(1);
  if (!bodyTable.length) {
    throw new Error('Could not find the reservation time table.');
  }

  const rows = new Map();
  bodyTable.find('tbody tr').each((_, row) => {
    const time = normalizeText($(row).find('th').first().text());
    if (!/^\d{2}:\d{2}$/.test(time)) {
      return;
    }

    const statuses = $(row)
      .find('td')
      .toArray()
      .map((cell) => normalizeStatus($(cell).text()));
    rows.set(time, statuses);
  });

  return rows;
}

function normalizeStatus(text) {
  const normalized = normalizeText(text);
  if (normalized.includes('○')) return '○';
  if (normalized.includes('◯')) return '◯';
  if (normalized.includes('×')) return '×';
  if (normalized.includes('-')) return '-';
  return normalized || 'unknown';
}

function normalizeText(text) {
  return text.replace(/\s+/g, ' ').trim();
}

function formatDate(year, month, day) {
  return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}
