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
