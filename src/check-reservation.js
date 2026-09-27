import { readConfig } from './config.js';
import { sendDiscordError, sendDiscordNotification } from './discord.js';
import { fetchAvailability } from './ebica.js';
import { availabilitySignature, readState, writeState } from './state.js';

const config = readConfig();

try {
  const result = await fetchAvailability({
    url: config.ebicaUrl,
    targetDate: config.targetDate,
    targetTimes: config.targetTimes,
  });

  printResult(result);

  const state = await readState(config.stateFile);
  const signature = availabilitySignature(result);
  const hasAvailability = result.availableSlots.length > 0;
  const shouldNotify =
    hasAvailability &&
    (config.notifyEveryCheck || state.lastNotifiedAvailabilitySignature !== signature);

  let notificationResult = { sent: false };
  if (shouldNotify) {
    notificationResult = await sendDiscordNotification({
      webhookUrl: config.discordWebhookUrl,
      dryRun: config.dryRun,
      payload: result,
    });
  }

  const nextState = {
    ...state,
    lastCheckedAt: result.checkedAt,
    lastResult: result,
  };

  if (!hasAvailability) {
    nextState.lastNotifiedAvailabilitySignature = null;
  } else if (notificationResult.sent) {
    nextState.lastNotifiedAvailabilitySignature = signature;
    nextState.lastNotifiedAt = result.checkedAt;
  }

  await writeState(config.stateFile, nextState);
} catch (error) {
  console.error(error);
  if (config.notifyErrors) {
    await sendDiscordError({
      webhookUrl: config.discordWebhookUrl,
      dryRun: config.dryRun,
      error,
      context: config,
    });
  }
  process.exitCode = 1;
}

function printResult(result) {
  console.log(`Checked at: ${result.checkedAt}`);
  console.log(`Visible calendar dates: ${result.visibleDates.join(', ')}`);
  for (const slot of result.slots) {
    console.log(`${slot.date} ${slot.time}: ${slot.status}`);
  }

  if (result.availableSlots.length > 0) {
    console.log(
      `Available target slots: ${result.availableSlots
        .map((slot) => `${slot.date} ${slot.time}`)
        .join(', ')}`,
    );
  } else {
    console.log('No target slots are available.');
  }
}
