<#!
.SYNOPSIS
    CLIProxy Antigravity Manager for Windows
.DESCRIPTION
    Refreshes quota cache and prints a summary from dashboard.html
#>

$ConfigDir = "$env:USERPROFILE\.cliproxyapi"
$ScriptsDir = Join-Path $ConfigDir "scripts"
$ManagerPy = Join-Path $ScriptsDir "cp-antigravity.py"
$QuotaFetcher = Join-Path $ScriptsDir "quota-fetcher.py"
$DashboardUrl = "http://localhost:8317/dashboard.html"

function Get-PythonBinary {
    $py = Get-Command python -ErrorAction SilentlyContinue
    if ($py) { return $py.Source }
    $py3 = Get-Command python3 -ErrorAction SilentlyContinue
    if ($py3) { return $py3.Source }
    return $null
}

function Refresh-Quota($PythonBin) {
    if (-not (Test-Path $QuotaFetcher)) {
        Write-Host "[!] quota-fetcher.py tidak ditemukan." -ForegroundColor Yellow
        return
    }
    Write-Host "[i] Mengambil data quota terbaru..." -ForegroundColor Cyan
    & $PythonBin $QuotaFetcher 2>$null | Out-Null
    Write-Host "[OK] Quota diperbarui." -ForegroundColor Green
}

function Show-Quota($PythonBin) {
    if (-not (Test-Path $ManagerPy)) {
        Write-Host "[ERROR] Antigravity Manager belum terpasang." -ForegroundColor Red
        return
    }
    & $PythonBin $ManagerPy
}

$PythonBin = Get-PythonBinary
if (-not $PythonBin) {
    Write-Host "[ERROR] Python tidak ditemukan. Install Python untuk menggunakan Antigravity Manager." -ForegroundColor Red
    exit 1
}

while ($true) {
    Clear-Host
    Write-Host "  ══  CLIProxy • Antigravity Manager  ══" -ForegroundColor Cyan
    Write-Host "  Monitoring sisa quota Antigravity" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  1  Refresh + Tampilkan Quota" -ForegroundColor Green
    Write-Host "  2  Tampilkan Cache Terakhir" -ForegroundColor Green
    Write-Host "  3  Buka Dashboard" -ForegroundColor Green
    Write-Host ""
    Write-Host "  0  Kembali" -ForegroundColor Red
    Write-Host ""

    $choice = Read-Host "Select (0-3)"
    switch ($choice) {
        '1' {
            Refresh-Quota $PythonBin
            Show-Quota $PythonBin
            Read-Host "Press Enter to continue" | Out-Null
        }
        '2' {
            Show-Quota $PythonBin
            Read-Host "Press Enter to continue" | Out-Null
        }
        '3' {
            Start-Process $DashboardUrl
            Read-Host "Press Enter to continue" | Out-Null
        }
        '0' { break }
        Default {
            Write-Host "Pilihan tidak valid." -ForegroundColor Yellow
            Start-Sleep -Seconds 1
        }
    }
}
