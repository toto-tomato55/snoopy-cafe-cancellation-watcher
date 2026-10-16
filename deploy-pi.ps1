$ErrorActionPreference = 'Stop'
$tool = 'C:\claude-tools\raspberrypi-5plus\bin\pi.cmd'
# Preserve the configured service's runtime secrets; use pi env for changes.
$stage = Join-Path ([IO.Path]::GetTempPath()) ('galleria-stock-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
try {
    # Transfer only service source, never screenshots, local data or credentials.
    foreach ($file in @('main.py', 'stock_monitor.py', 'deals.py', 'deal_rules.json', 'requirements.txt', 'test_stock_monitor.py', 'test_deals.py', 'README.md', 'AGENTS.md')) {
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
