"""
Launcher for Windows Task Scheduler: run one project module with its output appended to a log.

    pythonw.exe deploy\run_task.py src.snapshot

pythonw.exe has no console, so nothing flashes on screen every 10 minutes, but it also has no
stdout/stderr. This script points both at logs/task_<module>.log *before* the module is imported,
so the console log handler and any crash traceback land in that file (the normal pipeline.log is
written as usual). Equivalent of the cron line `... >> logs/cron_snapshot.log 2>&1`.
"""
import runpy
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

module = sys.argv[1]
(ROOT / "logs").mkdir(exist_ok=True)
log = open(ROOT / "logs" / f"task_{module.split('.')[-1]}.log", "a", encoding="utf-8", buffering=1)
sys.stdout = sys.stderr = log
sys.path.insert(0, str(ROOT))
sys.argv = [module] + sys.argv[2:]

try:
    runpy.run_module(module, run_name="__main__", alter_sys=True)
except SystemExit as e:
    if e.code not in (None, 0):
        print(f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC  exit code {e.code}")
        raise
except BaseException:
    print(f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC  CRASH in {module}")
    traceback.print_exc()
    sys.exit(1)
