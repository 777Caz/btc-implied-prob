# Windows replacement for deploy/crontab.txt: registers three Task Scheduler jobs for this user.
#   btc-implied-prob\snapshot     every 10 minutes          python -m src.snapshot
#   btc-implied-prob\resolutions  daily 00:30 UTC           python -m src.resolutions
#   btc-implied-prob\paper_trade  daily 08:07 UTC           python -m src.paper_trade
#
# Run from the project root in an ADMIN PowerShell (registering S4U tasks needs elevation):
#     powershell -ExecutionPolicy Bypass -File deploy\register_tasks.ps1
# Remove both (admin):  Unregister-ScheduledTask -TaskPath "\btc-implied-prob\" -Confirm:$false
#
# "Run whether user is logged on or not" (LogonType S4U): runs as you with no password stored,
# also when logged out or after a reboot before you log in. S4U tasks run in a background session
# (never visible) and can't use network-share credentials; plain internet access is unaffected.

$ErrorActionPreference = "Stop"
$Root    = Split-Path -Parent $PSScriptRoot
$Pythonw = Join-Path $Root ".venv\Scripts\pythonw.exe"     # no console window
$Runner  = Join-Path $Root "deploy\run_task.py"
$Folder  = "\btc-implied-prob\"
if (-not (Test-Path $Pythonw)) { throw "venv not found: $Pythonw" }

function New-Action($module) {
    New-ScheduledTaskAction -Execute $Pythonw -Argument "`"$Runner`" $module" -WorkingDirectory $Root
}
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Limited

# ── Snapshot: every 10 min, starting at the next 10-minute boundary ─────────────────────────
$now   = Get-Date
$start = $now.Date.AddMinutes([math]::Ceiling(($now.TimeOfDay.TotalMinutes + 1) / 10) * 10)
$snapTrigger = New-ScheduledTaskTrigger -Once -At $start -RepetitionInterval (New-TimeSpan -Minutes 10)
$snapSettings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "snapshot" -TaskPath $Folder -Force `
    -Action (New-Action "src.snapshot") -Trigger $snapTrigger -Settings $snapSettings -Principal $principal `
    -Description "Deribit chain + Polymarket/Kalshi BTC markets snapshot (src.snapshot)" | Out-Null

# ── Resolutions: daily at 00:30 UTC (pinned to UTC, so it doesn't shift with UK summer time) ─
# Runs after the UTC day has closed, so each run finalises the previous day: every settlement of
# that day is in (Deribit 08:00 UTC, Polymarket 12:00 NY = 16-17 UTC, Kalshi 17:00 NY = 21-22 UTC).
# Idempotent and catches up on missed days. Also logs the snapshot gap/staleness check.
$resAt = [DateTime]::SpecifyKind($now.ToUniversalTime().Date.AddDays(1).AddHours(0.5), [DateTimeKind]::Utc)
$resTrigger = New-ScheduledTaskTrigger -Daily -At $resAt
$resSettings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "resolutions" -TaskPath $Folder -Force `
    -Action (New-Action "src.resolutions") -Trigger $resTrigger -Settings $resSettings -Principal $principal `
    -Description "Settlements / outcomes / Binance noon NY (src.resolutions)" | Out-Null

# ── Paper trading: daily 08:07 UTC, after the 08:00 snapshot (src/paper_trade.py; no orders) ─────
# Rebuilds the option q from the overnight Deribit trades, applies the Kalshi gap rule to the 08:00
# snapshot and logs the signals; the resolutions job settles them.
$ptAt = [DateTime]::SpecifyKind($now.ToUniversalTime().Date.AddDays(1).AddHours(8).AddMinutes(7), [DateTimeKind]::Utc)
$ptTrigger = New-ScheduledTaskTrigger -Daily -At $ptAt
$ptSettings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "paper_trade" -TaskPath $Folder -Force `
    -Action (New-Action "src.paper_trade") -Trigger $ptTrigger -Settings $ptSettings -Principal $principal `
    -Description "Kalshi gap-rule paper trading log, no orders (src.paper_trade)" | Out-Null

Get-ScheduledTask -TaskPath $Folder | ForEach-Object {
    $i = $_ | Get-ScheduledTaskInfo
    "{0,-12} {1,-6} next run {2}" -f $_.TaskName, $_.State, $i.NextRunTime
}
