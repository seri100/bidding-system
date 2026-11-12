param(
    [string[]]$SourceRoots = @((Join-Path $env:USERPROFILE 'bid-dashboard'), 'C:\bidding-system', (Join-Path $env:USERPROFILE 'bid_monitor')),
    [string]$BackupRoot = (Join-Path $env:USERPROFILE 'n_data-recovery-private'),
    [switch]$ExportD1
)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force $BackupRoot | Out-Null
& icacls $BackupRoot /inheritance:r /grant:r "$($env:USERDOMAIN)\$($env:USERNAME):(OI)(CI)F" | Out-Null
if ($LASTEXITCODE) { throw 'Private directory ACL failed' }
$openssl = (Get-Command openssl -ErrorAction SilentlyContinue).Source
if (!$openssl) { $openssl = 'C:\Program Files\Git\usr\bin\openssl.exe' }
if (!(Test-Path $openssl)) { throw 'OpenSSL is required; install it before backing up' }
$stamp = Get-Date -Format yyyyMMdd_HHmmss_fff
$name = 'pc-' + $stamp
$stage = Join-Path $BackupRoot $name
New-Item -ItemType Directory $stage | Out-Null
$files = New-Object System.Collections.Generic.List[object]
$excluded = '^(node_modules|\.git|\.wrangler|dist|logs|backup|archives|shortcut-backup|reports|uploads)$'
function Copy-Project([string]$root, [string]$dir) {
    foreach ($entry in Get-ChildItem -LiteralPath $dir -Force) {
        if ($entry.Name -match $excluded -or ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint)) { continue }
        if ($entry.PSIsContainer) { Copy-Project $root $entry.FullName; continue }
        if ($entry.Length -gt 20MB) { continue }
        $relative = (Split-Path $root -Leaf) + '/' + $entry.FullName.Substring($root.Length).TrimStart('\').Replace('\','/')
        $out = Join-Path $stage ('files/' + $relative)
        New-Item -ItemType Directory -Force (Split-Path $out) | Out-Null
        Copy-Item -LiteralPath $entry.FullName -Destination $out
        $files.Add(@{ source=$entry.FullName; path=('files/' + $relative); bytes=$entry.Length; sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $out).Hash.ToLowerInvariant() })
    }
}
foreach ($root in $SourceRoots) {
    if (!(Test-Path -LiteralPath $root -PathType Container)) { throw "Source missing: $root" }
    Copy-Project $root.TrimEnd('\') $root.TrimEnd('\')
}
foreach ($taskName in @('BidDashboard-Archive','bid_monitor')) {
    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
        Export-ScheduledTask -TaskName $taskName | Set-Content (Join-Path $stage ($taskName + '.xml')) -Encoding Unicode
    }
}
if ($ExportD1) {
    $dashboard = $SourceRoots | Where-Object { (Split-Path $_ -Leaf) -eq 'bid-dashboard' } | Select-Object -First 1
    if (!$dashboard) { throw 'Dashboard source is required for D1 export' }
    Push-Location $dashboard
    try {
        & npx wrangler d1 export webapp-production --remote "--output=$(Join-Path $stage 'dashboard-d1.sql')" *> (Join-Path $stage 'd1-export-private.log')
        if ($LASTEXITCODE) { throw 'D1 export failed; see private export log' }
    } finally { Pop-Location }
}
$manifest = @{ date=(Get-Date -Format o); roots=$SourceRoots; files=@($files.ToArray()); excluded=@('node_modules','git history','Cloudflare login tokens','large data >20MiB','archives','logs','external databases') }
[IO.File]::WriteAllText((Join-Path $stage 'manifest.json'), ($manifest | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
$plain = Join-Path $BackupRoot ($name + '.tar.gz')
& tar -czf $plain -C $BackupRoot $name
if ($LASTEXITCODE) { throw 'Archive creation failed' }
$key = Join-Path $BackupRoot 'backup.key'
if (!(Test-Path $key)) {
    $bytes = New-Object byte[] 32
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes); $rng.Dispose()
    [IO.File]::WriteAllText($key, ([BitConverter]::ToString($bytes).Replace('-','').ToLowerInvariant() + "`n"), [Text.UTF8Encoding]::new($false))
}
$encrypted = $plain + '.enc'
& $openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 -in $plain -out $encrypted -pass ('file:' + $key)
if ($LASTEXITCODE) { throw 'Encryption failed; private staging is retained' }
$mac = [Security.Cryptography.HMACSHA256]::new([Text.Encoding]::UTF8.GetBytes([IO.File]::ReadAllText($key).Trim()))
$digest = [BitConverter]::ToString($mac.ComputeHash([IO.File]::ReadAllBytes($encrypted))).Replace('-','').ToLowerInvariant()
$mac.Dispose()
[IO.File]::WriteAllText(($encrypted + '.hmac'), ($digest + "`n"), [Text.UTF8Encoding]::new($false))
[IO.File]::WriteAllText(($encrypted + '.sha256'), ((Get-FileHash $encrypted -Algorithm SHA256).Hash.ToLowerInvariant() + "`n"), [Text.UTF8Encoding]::new($false))
# Keep staging until verify_restore.py has authenticated and checked every file.
Write-Output "ENCRYPTED files=$($files.Count) archive=$encrypted"
Write-Output 'Verify in staging with verify_restore.py; keep backup.key separately. No application or task was started.'
