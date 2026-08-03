[CmdletBinding()]
param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [string]$EnvFile = "",
    [string]$BackupRoot = "D:\DatabaseBackups\novelAi",
    [int]$RetentionDays = 30,
    [string]$MySqlDumpPath = ""
)

$ErrorActionPreference = "Stop"

function Write-BackupLog {
    param([string]$Message)

    $logDirectory = Join-Path $BackupRoot "logs"
    New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -LiteralPath (Join-Path $logDirectory "backup.log") -Value $line -Encoding UTF8
    Write-Host $line
}

function Get-EnvValue {
    param([string]$Path, [string]$Name)

    $line = Get-Content -LiteralPath $Path | Where-Object {
        $_ -match ("^\s*" + [regex]::Escape($Name) + "\s*=")
    } | Select-Object -First 1

    if (-not $line) {
        throw "Environment variable '$Name' was not found in $Path"
    }

    $value = ($line -split "=", 2)[1].Trim()
    if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
        ($value.StartsWith("'") -and $value.EndsWith("'"))) {
        $value = $value.Substring(1, $value.Length - 2)
    }
    return $value
}

function Find-MySqlTool {
    param([string]$ExplicitPath, [string]$ToolName)

    if ($ExplicitPath) {
        if (-not (Test-Path -LiteralPath $ExplicitPath -PathType Leaf)) {
            throw "$ToolName was not found at: $ExplicitPath"
        }
        return (Resolve-Path -LiteralPath $ExplicitPath).Path
    }

    $command = Get-Command $ToolName -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $roots = @($env:ProgramFiles, ${env:ProgramFiles(x86)}) | Where-Object { $_ }
    foreach ($root in $roots) {
        $matches = Get-ChildItem -Path (Join-Path $root "MySQL") -Filter $ToolName -File -Recurse -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending
        if ($matches) {
            return $matches[0].FullName
        }
    }

    throw "$ToolName was not found. Install MySQL client tools or pass -MySqlDumpPath explicitly."
}

function Escape-OptionValue {
    param([string]$Value)
    return $Value.Replace("\", "\\").Replace('"', '\"')
}

$temporaryConfig = $null
$sqlPath = $null

try {
    $envPath = if ($EnvFile) {
        $EnvFile
    } else {
        Join-Path $ProjectRoot ".env"
    }
    if (-not (Test-Path -LiteralPath $envPath -PathType Leaf)) {
        throw "Environment file was not found at: $envPath"
    }

    $databaseUrl = Get-EnvValue -Path $envPath -Name "DATABASE_URL"
    $uriValue = $databaseUrl -replace "^mysql\+[^:]+://", "mysql://"
    $uri = [Uri]$uriValue
    if (-not $uri.Host -or -not $uri.UserInfo) {
        throw "DATABASE_URL is not a valid MySQL connection URL."
    }

    $userInfo = $uri.UserInfo -split ":", 2
    $dbUser = [Uri]::UnescapeDataString($userInfo[0])
    $dbPassword = if ($userInfo.Count -gt 1) { [Uri]::UnescapeDataString($userInfo[1]) } else { "" }
    $dbName = [Uri]::UnescapeDataString($uri.AbsolutePath.TrimStart("/"))
    $dbPort = if ($uri.IsDefaultPort) { 3306 } else { $uri.Port }
    if (-not $dbName) {
        throw "DATABASE_URL does not contain a database name."
    }

    $dumpTool = Find-MySqlTool -ExplicitPath $MySqlDumpPath -ToolName "mysqldump.exe"
    $backupDirectory = Join-Path $BackupRoot "backups"
    New-Item -ItemType Directory -Path $backupDirectory -Force | Out-Null

    $timestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
    $safeDbName = $dbName -replace "[^A-Za-z0-9_.-]", "_"
    $sqlPath = Join-Path $backupDirectory ("{0}_{1}.sql" -f $safeDbName, $timestamp)
    $zipPath = "$sqlPath.zip"
    $temporaryConfig = Join-Path $env:TEMP ("mysql-backup-{0}.cnf" -f [Guid]::NewGuid())

    $configText = @"
[client]
host="$(Escape-OptionValue $uri.Host)"
port=$dbPort
user="$(Escape-OptionValue $dbUser)"
password="$(Escape-OptionValue $dbPassword)"
"@
    [IO.File]::WriteAllText($temporaryConfig, $configText, [Text.UTF8Encoding]::new($false))

    Write-BackupLog "Starting backup for database '$dbName'."
    $arguments = @(
        "--defaults-extra-file=$temporaryConfig"
        "--single-transaction"
        "--quick"
        "--routines"
        "--events"
        "--triggers"
        "--hex-blob"
        "--set-gtid-purged=OFF"
        "--result-file=$sqlPath"
        $dbName
    )
    & $dumpTool @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "mysqldump exited with code $LASTEXITCODE."
    }
    if (-not (Test-Path -LiteralPath $sqlPath) -or (Get-Item -LiteralPath $sqlPath).Length -eq 0) {
        throw "mysqldump did not create a valid output file."
    }

    Compress-Archive -LiteralPath $sqlPath -DestinationPath $zipPath -CompressionLevel Optimal -Force
    Remove-Item -LiteralPath $sqlPath -Force
    $sqlPath = $null

    $cutoff = (Get-Date).AddDays(-$RetentionDays)
    $expired = Get-ChildItem -LiteralPath $backupDirectory -Filter "*.sql.zip" -File |
        Where-Object { $_.LastWriteTime -lt $cutoff }
    foreach ($file in $expired) {
        Remove-Item -LiteralPath $file.FullName -Force
    }

    $sizeMb = [Math]::Round((Get-Item -LiteralPath $zipPath).Length / 1MB, 2)
    Write-BackupLog "Backup completed: $zipPath ($sizeMb MB). Removed $($expired.Count) expired backup(s)."
    exit 0
}
catch {
    try { Write-BackupLog "BACKUP FAILED: $($_.Exception.Message)" } catch { Write-Error $_ }
    exit 1
}
finally {
    if ($temporaryConfig -and (Test-Path -LiteralPath $temporaryConfig)) {
        Remove-Item -LiteralPath $temporaryConfig -Force -ErrorAction SilentlyContinue
    }
    if ($sqlPath -and (Test-Path -LiteralPath $sqlPath)) {
        Remove-Item -LiteralPath $sqlPath -Force -ErrorAction SilentlyContinue
    }
}
