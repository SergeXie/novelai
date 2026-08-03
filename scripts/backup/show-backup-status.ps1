[CmdletBinding()]
param(
    [string]$TaskName = "novelAi-MySQL-Backup",
    [string]$BackupRoot = "D:\DatabaseBackups\novelAi",
    [int]$RefreshSeconds = 5
)

$ErrorActionPreference = "SilentlyContinue"

while ($true) {
    Clear-Host
    Write-Host "==============================================" -ForegroundColor Cyan
    Write-Host "          novelAi MySQL Backup Monitor" -ForegroundColor Cyan
    Write-Host "==============================================" -ForegroundColor Cyan
    Write-Host "Updated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    Write-Host "Press Ctrl+C to close this window."
    Write-Host ""

    $task = Get-ScheduledTask -TaskName $TaskName
    $taskInfo = Get-ScheduledTaskInfo -TaskName $TaskName

    if (-not $task -or -not $taskInfo) {
        Write-Host "Scheduled task: NOT FOUND ($TaskName)" -ForegroundColor Red
    }
    else {
        $stateColor = if ($task.State -eq "Ready") { "Green" } elseif ($task.State -eq "Running") { "Yellow" } else { "Red" }
        Write-Host "Task name    : $TaskName"
        Write-Host "Task state   : $($task.State)" -ForegroundColor $stateColor
        Write-Host "Last run     : $($taskInfo.LastRunTime)"
        Write-Host "Next run     : $($taskInfo.NextRunTime)"

        if ($taskInfo.LastTaskResult -eq 0) {
            Write-Host "Last result  : SUCCESS (0)" -ForegroundColor Green
        }
        elseif ($taskInfo.LastTaskResult -eq 267009) {
            Write-Host "Last result  : RUNNING (267009)" -ForegroundColor Yellow
        }
        else {
            Write-Host "Last result  : FAILED/UNKNOWN ($($taskInfo.LastTaskResult))" -ForegroundColor Red
        }
    }

    Write-Host ""
    Write-Host "Latest backup" -ForegroundColor Cyan
    Write-Host "-------------"
    $backupDirectory = Join-Path $BackupRoot "backups"
    $latestBackup = Get-ChildItem -LiteralPath $backupDirectory -Filter "*.sql.zip" -File |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if ($latestBackup) {
        $sizeMb = [Math]::Round($latestBackup.Length / 1MB, 2)
        Write-Host "File          : $($latestBackup.Name)" -ForegroundColor Green
        Write-Host "Size          : $sizeMb MB"
        Write-Host "Created       : $($latestBackup.LastWriteTime)"
        Write-Host "Directory     : $backupDirectory"
    }
    else {
        Write-Host "No backup file found in: $backupDirectory" -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "Recent log" -ForegroundColor Cyan
    Write-Host "----------"
    $logPath = Join-Path (Join-Path $BackupRoot "logs") "backup.log"
    if (Test-Path -LiteralPath $logPath) {
        Get-Content -LiteralPath $logPath -Tail 8 | ForEach-Object { Write-Host $_ }
    }
    else {
        Write-Host "Log file not found: $logPath" -ForegroundColor Yellow
    }

    Start-Sleep -Seconds $RefreshSeconds
}
