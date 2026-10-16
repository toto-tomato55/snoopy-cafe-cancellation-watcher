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
