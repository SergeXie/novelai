[CmdletBinding()]
param(
    [string]$TaskName = "novelAi-MySQL-Backup",
    [string]$DailyAt = "02:00",
    [string]$EnvFile = "",
    [string]$BackupRoot = "D:\DatabaseBackups\novelAi",
    [int]$RetentionDays = 30,
    [string]$MySqlDumpPath = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$backupScript = Join-Path $PSScriptRoot "backup-mysql.ps1"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run PowerShell as Administrator before installing the scheduled task."
}

try {
    $triggerTime = [DateTime]::ParseExact($DailyAt, "HH:mm", [Globalization.CultureInfo]::InvariantCulture)
}
catch {
    throw "DailyAt must use HH:mm format, for example 02:00."
}

$argumentParts = @(
    '-NoProfile'
    '-ExecutionPolicy Bypass'
    "-File `"$backupScript`""
    "-ProjectRoot `"$projectRoot`""
    "-BackupRoot `"$BackupRoot`""
    "-RetentionDays $RetentionDays"
)
if ($MySqlDumpPath) {
    $argumentParts += "-MySqlDumpPath `"$MySqlDumpPath`""
}
if ($EnvFile) {
    if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
        throw "Environment file was not found at: $EnvFile"
    }
    $resolvedEnvFile = (Resolve-Path -LiteralPath $EnvFile).Path
    $argumentParts += "-EnvFile `"$resolvedEnvFile`""
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument ($argumentParts -join " ")
$trigger = New-ScheduledTaskTrigger -Daily -At $triggerTime
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 4) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 10)
$taskPrincipal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

$task = New-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -Principal $taskPrincipal `
    -Description "Daily MySQL backup for novelAi"
Register-ScheduledTask -TaskName $TaskName -InputObject $task -Force | Out-Null

Write-Host "Scheduled task '$TaskName' installed."
Write-Host "Schedule: daily at $DailyAt"
Write-Host "Backup directory: $BackupRoot"
Write-Host "Test it now with: Start-ScheduledTask -TaskName '$TaskName'"
