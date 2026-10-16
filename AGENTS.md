# Current application

This folder now develops a GALLERIA and OZ Gaming PC deal monitor. The former
MC21585 single-product monitor and Snoopy watcher are historical. Read README.md.
The cafe source in src/ is historical. Its GitHub workflow must remain disabled.

Read C:\Users\amies\AI-ENVIRONMENT.md and the inventory it references before
deployment. S-monitor is the persistent target. Use deploy-pi.ps1 to stage only
the Python source and call the supported Pi toolkit. Service: galleria-stock.
Never deploy node_modules, remote attachments, local state or credentials in
the code archive. Send .env with pi env, never commit or print its contents.

main.py is the daemon entrypoint; deals.py scans both stores using deal_rules.json.
The accepted rules are RTX 5080 <= 320000 JPY; RTX 5070 Ti and RTX 5090 <= 280000
JPY, base desktop PC price including tax, excluding shipping and customization.
stock_monitor.py holds shared helpers and historical single-product logic.
Deal state lives in data/deals-status.json (shared/data on the Pi). Check
systemd active/enabled, actual successful stock reads on multiple 60-second
ticks, and notification results before claiming the monitor is operational.
