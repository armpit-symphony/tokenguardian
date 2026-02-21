# Token Guardian Troubleshooting

This doc covers the most common real-world failure modes we hit during deployment.

## Quick health commands

From the repo directory:
```bash
source venv/bin/activate
python3 tokenguardian.py doctor
python3 tokenguardian.py status
python3 tokenguardian.py logs
python3 tokenguardian.py tail
```

## Common Issues

### Symptom: python3: can't open file '/home/sparky/tokenguardian.py'
**Cause:** you ran commands from the wrong directory.
**Fix:** 
```bash
cd /home/sparky/.openclaw/workspace/tokenguardian
python3 tokenguardian.py status
```

Optional convenience alias:
```bash
echo 'alias tg="python3 /home/sparky/.openclaw/workspace/tokenguardian/tokenguardian.py"' >> ~/.bashrc
source ~/.bashrc
tg status
```

### Symptom: No module named 'yaml' / prometheus_client / etc.
**Cause:** dependencies were installed in a different venv (ex: ~/tokenguardian/venv) than the one used to run Token Guardian (ex: workspace venv).
**Fix:** create/use a venv inside the directory you're running from:
```bash
cd /home/sparky/.openclaw/workspace/tokenguardian
python3 -m venv venv
source venv/bin/activate
pip install pyyaml prometheus-client psutil requests
python3 tokenguardian.py doctor
```

Once healthy, lock deps:
```bash
pip freeze > requirements.txt
```

### Symptom: start succeeds then it "keeps restarting"
**Likely causes:**
1. Running multiple managers at once (systemd + supervisor + manual runs).
2. Port conflict on metrics port (default 9090).
3. Crash loop (check daemon logs).

**Checklist:**
```bash
ps aux | egrep "tg_supervisor|tokenguardian.py start|tg_ingestor|tg-burnin-driver" | grep -v grep
sudo lsof -i :9090 || true
python3 tokenguardian.py logs | tail -n 200
```

### Symptom: Metrics server started on port 9090 fails / port in use
**Fix:** stop the conflicting service or change metrics port in config (~/.tokenguardian) if supported, then restart.
```bash
sudo lsof -i :9090
```

### Symptom: Driver halted / DRIVER_HALTED: driver previously halted
That is the burn-in driver, not the main Token Guardian daemon. Burn-in driver is a test harness. It writes a latched state in:
- driver.status
- driver.lock

**Reset latch:**
```bash
cd /home/sparky/.openclaw/workspace/tokenguardian
rm -f driver.status driver.lock
```

To disable burn-in driver entirely (recommended for production), see BURNIN_DRIVER.md.
