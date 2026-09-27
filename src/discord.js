export async function sendDiscordNotification({ webhookUrl, dryRun, payload }) {
  const body = {
    content: buildMessage(payload),
    allowed_mentions: { parse: [] },
  };

  if (dryRun || !webhookUrl) {
    console.log('[discord] notification skipped');
    console.log(JSON.stringify(body, null, 2));
    return { sent: false, reason: dryRun ? 'dry-run' : 'missing-webhook' };
  }

  const response = await fetch(webhookUrl, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const responseText = await response.text();
    throw new Error(`Discord webhook failed: ${response.status} ${response.statusText} ${responseText}`);
  }

  return { sent: true };
}

export async function sendDiscordError({ webhookUrl, dryRun, error, context }) {
  if (!webhookUrl || dryRun) {
    return { sent: false };
  }

  const response = await fetch(webhookUrl, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      content: [
        '予約キャンセル監視でエラーが出ました。',
        `対象: ${context.targetDate} ${context.targetTimes.join(', ')}`,
        `エラー: ${error.message}`,
      ].join('\n'),
      allowed_mentions: { parse: [] },
    }),
  });

  return { sent: response.ok };
}

function buildMessage(payload) {
  const times = payload.availableSlots.map((slot) => `${slot.time}`).join(', ');
  return [
    'PEANUTS Cafe SNOOPY MUSEUM TOKYO の予約に空きが出ました。',
    `対象日: ${payload.targetDate}`,
    `空き時間: ${times}`,
    `確認時刻: ${payload.checkedAt}`,
    `予約ページ: ${payload.url}`,
  ].join('\n');
}
