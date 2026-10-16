$ErrorActionPreference = 'Stop'
$tool = 'C:\claude-tools\raspberrypi-5plus\bin\pi.cmd'
. 'C:\claude-tools\raspberrypi-5plus\scripts\common.ps1'
$configuration = Join-Path $PSScriptRoot '.env'
if (-not (Test-Path -LiteralPath $configuration)) { throw 'Create .env before deployment' }
$shared = "$($PiConfig.remoteRoot)/galleria-stock/shared"
$quotedShared = Quote-Bash $shared
# pi env restarts an existing service; seed configuration before the first install.
Invoke-PiCommand "set -e; mkdir -p $quotedShared; chmod 700 $quotedShared"
$scpOptions = @('-P', [string]$PiConfig.port, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8',
                '-o', 'StrictHostKeyChecking=accept-new', '-i', $PiConfig.identityFile)
& $ScpExe @scpOptions $configuration "$($PiConfig.user)@$($PiConfig.host):$shared/.env.pending"
if ($LASTEXITCODE -ne 0) { throw 'Configuration upload failed' }
Invoke-PiCommand "set -e; chmod 600 $quotedShared/.env.pending; mv -f $quotedShared/.env.pending $quotedShared/.env"
$stage = Join-Path ([IO.Path]::GetTempPath()) ('galleria-stock-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
try {
    # Transfer only service source, never screenshots, local data or credentials.
    foreach ($file in @('main.py', 'stock_monitor.py', 'requirements.txt', 'test_stock_monitor.py', 'README.md', 'AGENTS.md')) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot $file) -Destination $stage
    }
    & $tool deploy galleria-stock $stage
    if ($LASTEXITCODE -ne 0) { throw 'Pi deployment failed' }
} finally {
    $target = [IO.Path]::GetFullPath($stage)
    $parent = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
    if (-not $target.StartsWith($parent, [StringComparison]::OrdinalIgnoreCase) -or
        (Split-Path -Leaf $target) -notmatch '^galleria-stock-[a-f0-9]{32}$') {
        throw 'Unexpected staging path; cleanup skipped'
    }
    Remove-Item -LiteralPath $target -Recurse -Force
}
