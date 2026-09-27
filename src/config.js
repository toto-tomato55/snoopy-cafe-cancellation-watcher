export function readConfig(env = process.env) {
  return {
    ebicaUrl:
      env.EBICA_URL ||
      'https://booking.ebica.jp/webrsv/plan/e014001307/22192/158405',
    targetDate: env.TARGET_DATE || '2026-10-03',
    targetTimes: parseList(env.TARGET_TIMES || '11:00,11:15,11:30,11:45,12:00'),
    discordWebhookUrl: env.DISCORD_WEBHOOK_URL || '',
    stateFile: env.STATE_FILE || '.state/last-status.json',
    dryRun: env.DRY_RUN === '1' || env.DRY_RUN === 'true',
    notifyEveryCheck:
      env.NOTIFY_EVERY_CHECK === '1' || env.NOTIFY_EVERY_CHECK === 'true',
    notifyErrors: env.NOTIFY_ERRORS === '1' || env.NOTIFY_ERRORS === 'true',
  };
}

function parseList(value) {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}
