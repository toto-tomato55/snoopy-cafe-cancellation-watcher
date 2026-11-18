# PC deal monitor verification: 2026-10-16

## Approved scope

- Stores: GALLERIA (Dospara) and OZ Gaming official catalogs.
- User rules: RTX 5080 <= 320,000 JPY; RTX 5070 Ti or above <= 280,000 JPY.
- Current configured GPUs: RTX 5070 Ti (280000), RTX 5080 (320000), RTX 5090 (280000).
- Prices are base PC prices including tax, excluding shipping/customization.
- Existing Discord webhook reused without entering Git or source archives.

## Local verification

- 23 unittests passed, including the historical monitor's regression tests.
- New cases cover exact price boundaries, different GPU/configuration, stock
  signals, changed detail prices, unavailable purchase controls, deduplication
  across restart, further price drops, restock, Discord failure retry, and source isolation.
- Live dry run completed in about 13 seconds: GALLERIA 3 pages / 60 rows;
  OZ 3 pages / 144 rows. No qualifying available products were found.
- Live detail parsing also succeeded on MC20240 (RTX 5080, 368880 JPY,
  available) and OZ 000000002696 (RTX 5070 Ti, 449800 JPY, available).
  These are validation samples above the user's price limits, not recommendations.

## Pi deployment

- Service: galleria-stock.service; source release 20261016T053255-fa4e0dcd.
- Active/running and enabled for boot were verified after deployment.
- Runtime settings updated through pi env; MONITOR_MODE=deals, interval 60,
  DEAL_STATE_FILE=data/deals-status.json.
- Historical single-product state remains separate and is not polled in deals mode.
- First live Pi scan completed at 14:33:52 JST in 18.66 seconds.
- Both sources were status=ok, with no unresolved products and no matches.
- startupNotified=true confirms Discord accepted the real startup/test message.
  This flag was preserved through the settings-update restart at 14:34:14 JST.

## Practical coverage

The scanner reads price-sorted listings through the relevant price cutoff,
not every product detail on every pass. Candidate detail pages are re-fetched
before notifications. Listed stock is not a reservation and can change before
purchase. Products missing from the official catalogs or hidden by stale store
caches cannot be discovered until published there.

## Catalog URL repair: 2026-10-21

- Pi logs and persisted state showed GALLERIA failing with `Unexpected product
  path`, while OZ continued successful 60-second scans. GALLERIA's last
  successful read before the incident was 2026-10-19 14:37:14 JST.
- The live TC30 GPU-filtered grid includes official mail-order-exclusive models
  at `/TC917/MC24683.html` (RTX 5070 Ti) and `/TC917/MC24688.html` (RTX 5090).
  The parser incorrectly required every product link to start with `/TC30/`.
  This failure is unrelated to the historical deleted MC21585 product.
- Product URLs now permit numeric TC category routes but still require HTTPS,
  the exact official hostname, and an MC product filename matching the grid ID.
  GPU, CPU, brand, price sorting and detail checks remain unchanged. Unexpected
  path errors now identify the offending path for diagnosis.
- All 25 unit tests passed, including alternate-category links, foreign hosts,
  mismatched IDs, invalid routes, and recovery-notification retries.
- Live local dry run: GALLERIA 3 pages / 60 rows, OZ 3 pages / 144 rows,
  no unresolved products, no errors and no qualifying available PCs.
- A direct live detail check of MC24683 succeeded: Core Ultra 7 265F,
  RTX 5070 Ti, 413980 JPY, available. This is an above-budget validation sample.
- GitHub's historical cafe workflow remains `disabled_manually`.
- Deployed through `deploy-pi.ps1` to Pi release
  `20261021T125927-05946fb4`, preserving runtime configuration and deal history.
  Service is active/running and boot-enabled; all 25 unit tests also passed on Pi.
- Both sources completed successful reads on successive 60-second ticks:
  GALLERIA at 22:00:43 and 22:01:44 JST; OZ at 22:00:30 and 22:01:29 JST.
  Each tick read 60 GALLERIA rows and 144 OZ rows; neither found a qualifying PC.
- The pre-existing GALLERIA `errorNotified=true` flag was cleared to false and
  failures reset from 3320 to zero only after the recovery message was accepted
  by Discord. No notification history or error counters were manually reset.

## Quiet outage notifications and catalog order repair: 2026-10-27

- User requested no repeated outage messages before recovery. After three
  consecutive failed reads, each store now sends one error notification per
  continuous outage, not hourly reminders. The existing persisted
  `errorNotified` flag also suppresses repeats after a restart or an error-text
  change. Discord failures remain retryable; recovery and deal alerts remain on.
- Pi was active/enabled but GALLERIA had 261 consecutive failed reads at
  21:48 JST; OZ was still reading successfully. The live GALLERIA grid's display
  prices genuinely run backwards (e.g. 394980 followed by 379980 JPY), making
  price-based early termination unsafe.
- GALLERIA now follows every page of each configured GPU filter, using 40-row
  pages and the existing 12-page-per-GPU safety limit. It no longer relies on
  display price ordering. GPU/identity checks, pagination checks, price limits,
  detail verification and OZ's sorted price-cutoff scan are retained.
- All 30 unit tests passed locally. Added cases cover late-page bargains after
  above-budget pages, reversed prices, page-limit failures, unchanged OZ order
  validation, one notification across days/restarts/error changes, per-store
  isolation, a fresh outage after recovery, and retry after Discord rejection.
- Live local scan succeeded with GALLERIA 7 pages / 259 rows and OZ 3 pages /
  144 rows, no matches, unresolved products or errors. A 100-row page trial
  timed out; the deployed scanner uses the verified 40-row page size instead.
- Deployed through `deploy-pi.ps1` to release
  `20261027T125552-a81ad1ed`, retaining credentials and persisted notification
  state. Service is active/running and boot-enabled; all 30 tests passed on Pi.
- First Pi read succeeded for OZ at 21:56:23 JST and GALLERIA at 21:57:29 JST.
  The GALLERIA recovery notification was accepted by Discord before clearing
  `errorNotified` and resetting failures from 268 to zero. No state was manually
  reset and no extra synthetic Discord test message was sent.
- The first full cycle took 70.42 seconds including recovery notification;
  the configured interval remains 60 seconds, but slow scans can extend it.
- A second Pi read also succeeded: OZ 21:57:32 and GALLERIA 21:58:31 JST,
  with unchanged counts and zero matches/errors. That cycle took 61.36 seconds.
- The historical cafe GitHub workflow remains `disabled_manually`.

## GALLERIA one-hour outage threshold: 2026-11-18

- User requested silence for brief GALLERIA failures. Its alert threshold is
  now one continuous hour from the first failed check, not three failed checks.
  A successful scan clears the timer. Unannounced outages also recover silently.
  An announced outage still produces one recovery message, and ongoing outages
  do not produce repeated alerts. OZ's three-failure threshold is unchanged.
- `failureStartedAt` is saved with the existing per-store state, so restarts and
  changing error text do not restart the clock. Old state without a start time
  begins timing on the next failure rather than guessing a historical duration.
  Existing delivered-alert flags remain intact. Failed Discord sends retry
  without recording a false delivery acknowledgement.
- All 34 local tests passed, including 3599/3600-second boundaries, silent
  short-outage recovery, successive separate outages, restart persistence,
  legacy-state handling and Discord rejection/retry. Tests use a fake clock and
  in-memory notifications; no synthetic Discord messages were sent.
- The live Pi source hash matched the local baseline before deployment.
  Both stores were reading successfully: GALLERIA 10 pages / 361 rows,
  OZ 2 pages / 96 rows, with no qualifying PCs. The 60-second interval is a
  target; observed full scans took about 76-81 seconds before this change.
- Deployed through `deploy-pi.ps1` to release
  `20261118T134515-43221e2b`, preserving runtime secrets and notification history.
  Active/running and boot-enabled were verified, and all 34 tests passed on Pi.
- The first post-deployment read succeeded for OZ at 22:46:31 JST and GALLERIA
  at 22:48:11 JST, with unchanged row counts and no qualifying PCs. Error-notice
  timestamps remained unchanged and both `errorNotified` flags were false;
  deployment did not emit new error, recovery or startup/test notifications.
- The next GALLERIA scan also succeeded at 22:49:37 JST (361 rows, zero
  matches/unresolved products), following OZ's next success at 22:48:13 JST.
  First post-deployment cycle took 103.21 seconds; subsequent GALLERIA reads
  were about 86 seconds apart. No polling/performance behavior was changed.
