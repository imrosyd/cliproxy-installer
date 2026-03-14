<#
.SYNOPSIS
    CLIProxy Dashboard Launcher for Windows
.DESCRIPTION
    Checks if CLIProxy server is running, starts if needed, then opens dashboard
#>

$DashboardUrl = "http://localhost:8317/dashboard.html"
$Port = 8317

Write-Host "  ══  CLIProxy • Dashboard  ══" -ForegroundColor Cyan
Write-Host "  URL: http://localhost:$Port/" -ForegroundColor DarkGray
Write-Host ""

# Check if server is running
$process = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1

if ($process) {
    $pid = (Get-Process -Id $process.OwningProcess).Id
    Write-Host "[OK] Server already running (PID: $pid)" -ForegroundColor Green
} else {
    Write-Host "[!] Server not running, starting now..." -ForegroundColor Yellow
    
    # Check if cp-start exists (as function or alias)
    if (Get-Command cp-start -ErrorAction SilentlyContinue) {
        Start-Job -ScriptBlock { cp-start } | Out-Null
        Write-Host "[i] Waiting for server to start..." -ForegroundColor Cyan
        
        # Wait up to 10 seconds
        $waited = 0
        while ($waited -lt 10) {
            Start-Sleep -Seconds 1
            $waited++
            
            $process = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($process) {
                $pid = (Get-Process -Id $process.OwningProcess).Id
                Write-Host "[OK] Server started successfully (PID: $pid)" -ForegroundColor Green
                break
            }
            
            if ($waited -eq 10) {
                Write-Host "[ERROR] Server failed to start. Please check logs." -ForegroundColor Red
                exit 1
            }
        }
    } else {
        Write-Host "[ERROR] cp-start command not found. Please install CLIProxy first." -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "[i] Opening dashboard: $DashboardUrl" -ForegroundColor Cyan
Write-Host ""

# Open in default browser
Start-Process $DashboardUrl

Write-Host "[OK] Dashboard opened." -ForegroundColor Green
