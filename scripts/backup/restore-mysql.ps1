[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$BackupZip,
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [string]$EnvFile = "",
    [string]$MySqlPath = ""
)

$ErrorActionPreference = "Stop"

Write-Warning "This operation imports data into the database configured by DATABASE_URL."
$confirmation = Read-Host "Type RESTORE to continue"
if ($confirmation -cne "RESTORE") {
    Write-Host "Restore cancelled."
    exit 1
}

if (-not (Test-Path -LiteralPath $BackupZip -PathType Leaf)) {
    throw "Backup file was not found: $BackupZip"
}

function Get-EnvValue {
    param([string]$Path, [string]$Name)

    $line = Get-Content -LiteralPath $Path | Where-Object {
        $_ -match ("^\s*" + [regex]::Escape($Name) + "\s*=")
    } | Select-Object -First 1
    if (-not $line) { throw "Environment variable '$Name' was not found in $Path" }

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
    if ($command) { return $command.Source }

    $roots = @($env:ProgramFiles, ${env:ProgramFiles(x86)}) | Where-Object { $_ }
    foreach ($root in $roots) {
        $matches = Get-ChildItem -Path (Join-Path $root "MySQL") -Filter $ToolName -File -Recurse -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending
        if ($matches) { return $matches[0].FullName }
    }
    throw "$ToolName was not found. Install MySQL client tools or pass -MySqlPath explicitly."
}

function Escape-OptionValue {
    param([string]$Value)
    return $Value.Replace("\", "\\").Replace('"', '\"')
}

$temporaryDirectory = Join-Path $env:TEMP ("novelAi-restore-{0}" -f [Guid]::NewGuid())
$temporaryConfig = Join-Path $env:TEMP ("mysql-restore-{0}.cnf" -f [Guid]::NewGuid())
try {
    New-Item -ItemType Directory -Path $temporaryDirectory -Force | Out-Null
    Expand-Archive -LiteralPath $BackupZip -DestinationPath $temporaryDirectory -Force
    $sqlFile = Get-ChildItem -LiteralPath $temporaryDirectory -Filter "*.sql" -File | Select-Object -First 1
    if (-not $sqlFile) { throw "The ZIP archive does not contain an SQL file." }

    $envPath = if ($EnvFile) { $EnvFile } else { Join-Path $ProjectRoot ".env" }
    if (-not (Test-Path -LiteralPath $envPath -PathType Leaf)) {
        throw "Environment file was not found at: $envPath"
    }
    $databaseUrl = Get-EnvValue -Path $envPath -Name "DATABASE_URL"
    $uri = [Uri]($databaseUrl -replace "^mysql\+[^:]+://", "mysql://")
    $userInfo = $uri.UserInfo -split ":", 2
    $dbUser = [Uri]::UnescapeDataString($userInfo[0])
    $dbPassword = if ($userInfo.Count -gt 1) { [Uri]::UnescapeDataString($userInfo[1]) } else { "" }
    $dbName = [Uri]::UnescapeDataString($uri.AbsolutePath.TrimStart("/"))
    $dbPort = if ($uri.IsDefaultPort) { 3306 } else { $uri.Port }

    $mysqlTool = Find-MySqlTool -ExplicitPath $MySqlPath -ToolName "mysql.exe"
    $configText = @"
[client]
host="$(Escape-OptionValue $uri.Host)"
port=$dbPort
user="$(Escape-OptionValue $dbUser)"
password="$(Escape-OptionValue $dbPassword)"
"@
    [IO.File]::WriteAllText($temporaryConfig, $configText, [Text.UTF8Encoding]::new($false))

    Write-Host "Restoring '$($sqlFile.FullName)' into database '$dbName'..."
    $process = Start-Process -FilePath $mysqlTool `
        -ArgumentList @("--defaults-extra-file=$temporaryConfig", $dbName) `
        -RedirectStandardInput $sqlFile.FullName -NoNewWindow -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "mysql exited with code $($process.ExitCode)."
    }
    Write-Host "Restore completed."
}
finally {
    Remove-Item -LiteralPath $temporaryConfig -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $temporaryDirectory -Recurse -Force -ErrorAction SilentlyContinue
}
