import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname } from 'node:path';

export async function readState(path) {
  try {
    return JSON.parse(await readFile(path, 'utf8'));
  } catch (error) {
    if (error.code === 'ENOENT') {
      return {};
    }
    throw error;
  }
}

export async function writeState(path, state) {
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, `${JSON.stringify(state, null, 2)}\n`, 'utf8');
}

export function availabilitySignature(result) {
  if (result.availableSlots.length === 0) {
    return 'none';
  }

  return result.availableSlots
    .map((slot) => `${slot.date}T${slot.time}`)
    .sort()
    .join('|');
}
