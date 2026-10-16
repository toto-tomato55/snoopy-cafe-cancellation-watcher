# Current application

This folder now develops the GALLERIA MC21585 stock monitor, not the former
Snoopy cafe reservation watcher. Read README.md for the current scope.
The cafe source in src/ is historical. Its GitHub workflow must remain disabled.

Read C:\Users\amies\AI-ENVIRONMENT.md and the inventory it references before
deployment. S-monitor is the persistent target. Use deploy-pi.ps1 to stage only
the Python source and call the supported Pi toolkit. Service: galleria-stock.
Never deploy node_modules, remote attachments, local state or credentials in
the code archive. Send .env with pi env, never commit or print its contents.

main.py is the daemon entrypoint. stock_monitor.py contains parsing and state
transitions. State lives in data/status.json (shared/data on the Pi). Check
systemd active/enabled, actual successful stock reads on multiple 60-second
ticks, and notification results before claiming the monitor is operational.
