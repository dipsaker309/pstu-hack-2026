param(
    [string]$BackupDir = $env:BACKUP_DIR,
    [string]$DatabaseUrl = $env:DATABASE_URL
)

if ([string]::IsNullOrWhiteSpace($BackupDir)) {
    $BackupDir = ".\backups"
}

New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outputPath = Join-Path $BackupDir "money_movement-$timestamp.dump"

if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) {
    $databaseName = $env:PGDATABASE

    if ([string]::IsNullOrWhiteSpace($databaseName)) {
        $databaseName = "money_movement"
    }

    & pg_dump --format=custom --file=$outputPath --dbname=$databaseName
} else {
    & pg_dump --format=custom --file=$outputPath $DatabaseUrl
}

if ($LASTEXITCODE -ne 0) {
    throw "PostgreSQL backup failed."
}

Write-Host "Backup written to $outputPath"
