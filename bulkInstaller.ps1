# Bulk Software Installer
# Reads apps.json and installs listed software using winget, choco, or scoop
# Logs all actions and errors

param(
    [Parameter(Position=0)]
    [ValidateSet('install', 'uninstall', 'update', 'dry-run')]
    [string]$Mode = 'install'
)

# Path to config file
$configPath = Join-Path $PSScriptRoot 'apps.json'

# Global variables for tracking results
$Global:Results = @{
    Installed = @()
    Uninstalled = @()
    Updated = @()
    Skipped = @()
    Failed = @()
    Total = 0
}

# Function to log messages
function Log-Result {
    param([string]$Message)
    $logPath = Join-Path $PSScriptRoot 'install.log'
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    "$timestamp`t$Message" | Out-File -FilePath $logPath -Append -Encoding utf8
}

# Function to ensure a package manager is installed
function Ensure-PackageManager {
    param(
        [string]$Manager
    )
    switch ($Manager) {
        'winget' {
            if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
                Write-Host 'winget not found. Please install App Installer from Microsoft Store.'
                exit 1
            }
        }
        'choco' {
            if (-not (Get-Command choco -ErrorAction SilentlyContinue)) {
                Write-Host 'Installing Chocolatey...'
                Set-ExecutionPolicy Bypass -Scope Process -Force
                [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
                Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
            }
        }
        'scoop' {
            if (-not (Get-Command scoop -ErrorAction SilentlyContinue)) {
                Write-Host 'Installing Scoop...'
                Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
                irm get.scoop.sh | iex
            }
        }
    }
}

# Function to check if app is installed
function Test-AppInstalled {
    param(
        [string]$AppName,
        [string]$Manager
    )
    switch ($Manager) {
        'winget' {
            $wingetCheck = winget list --name "$AppName" 2>$null
            return ($wingetCheck -and $wingetCheck -match $AppName)
        }
        'choco' {
            $chocoCheck = choco list --local-only | Select-String -Pattern "^$AppName "
            return [bool]$chocoCheck
        }
        'scoop' {
            $scoopCheck = scoop list | Select-String -Pattern "^$AppName "
            return [bool]$scoopCheck
        }
        default { return $false }
    }
}

# Function to install app
function Install-App {
    param(
        [string]$AppName,
        [string]$Manager,
        [string]$CustomArgs = ""
    )
    $success = $false
    $errorMsg = ""
    
    switch ($Manager) {
        'winget' {
            try {
                $cmd = "winget install --id `"$AppName`" --silent --accept-package-agreements --accept-source-agreements -e -h"
                if ($CustomArgs) { $cmd += " $CustomArgs" }
                if ($Mode -eq 'dry-run') {
                    Write-Host "[DRY RUN] Would run: $cmd"
                    $success = $true
                } else {
                    Invoke-Expression $cmd
                    $success = $true
                }
            } catch { $errorMsg = $_.Exception.Message }
        }
        'choco' {
            try {
                $cmd = "choco install `"$AppName`" -y --no-progress"
                if ($CustomArgs) { $cmd += " $CustomArgs" }
                if ($Mode -eq 'dry-run') {
                    Write-Host "[DRY RUN] Would run: $cmd"
                    $success = $true
                } else {
                    Invoke-Expression $cmd
                    $success = $true
                }
            } catch { $errorMsg = $_.Exception.Message }
        }
        'scoop' {
            try {
                $cmd = "scoop install `"$AppName`""
                if ($CustomArgs) { $cmd += " $CustomArgs" }
                if ($Mode -eq 'dry-run') {
                    Write-Host "[DRY RUN] Would run: $cmd"
                    $success = $true
                } else {
                    Invoke-Expression $cmd
                    $success = $true
                }
            } catch { $errorMsg = $_.Exception.Message }
        }
    }
    
    return @{ Success = $success; Error = $errorMsg }
}

# Function to uninstall app
function Uninstall-App {
    param(
        [string]$AppName,
        [string]$Manager,
        [string]$CustomArgs = ""
    )
    $success = $false
    $errorMsg = ""
    
    switch ($Manager) {
        'winget' {
            try {
                $cmd = "winget uninstall --id `"$AppName`" --silent"
                if ($CustomArgs) { $cmd += " $CustomArgs" }
                if ($Mode -eq 'dry-run') {
                    Write-Host "[DRY RUN] Would run: $cmd"
                    $success = $true
                } else {
                    Invoke-Expression $cmd
                    $success = $true
                }
            } catch { $errorMsg = $_.Exception.Message }
        }
        'choco' {
            try {
                $cmd = "choco uninstall `"$AppName`" -y"
                if ($CustomArgs) { $cmd += " $CustomArgs" }
                if ($Mode -eq 'dry-run') {
                    Write-Host "[DRY RUN] Would run: $cmd"
                    $success = $true
                } else {
                    Invoke-Expression $cmd
                    $success = $true
                }
            } catch { $errorMsg = $_.Exception.Message }
        }
        'scoop' {
            try {
                $cmd = "scoop uninstall `"$AppName`""
                if ($CustomArgs) { $cmd += " $CustomArgs" }
                if ($Mode -eq 'dry-run') {
                    Write-Host "[DRY RUN] Would run: $cmd"
                    $success = $true
                } else {
                    Invoke-Expression $cmd
                    $success = $true
                }
            } catch { $errorMsg = $_.Exception.Message }
        }
    }
    
    return @{ Success = $success; Error = $errorMsg }
}

# Function to update app
function Update-App {
    param(
        [string]$AppName,
        [string]$Manager,
        [string]$CustomArgs = ""
    )
    $success = $false
    $errorMsg = ""
    
    switch ($Manager) {
        'winget' {
            try {
                $cmd = "winget upgrade --id `"$AppName`" --silent --accept-package-agreements --accept-source-agreements"
                if ($CustomArgs) { $cmd += " $CustomArgs" }
                if ($Mode -eq 'dry-run') {
                    Write-Host "[DRY RUN] Would run: $cmd"
                    $success = $true
                } else {
                    Invoke-Expression $cmd
                    $success = $true
                }
            } catch { $errorMsg = $_.Exception.Message }
        }
        'choco' {
            try {
                $cmd = "choco upgrade `"$AppName`" -y"
                if ($CustomArgs) { $cmd += " $CustomArgs" }
                if ($Mode -eq 'dry-run') {
                    Write-Host "[DRY RUN] Would run: $cmd"
                    $success = $true
                } else {
                    Invoke-Expression $cmd
                    $success = $true
                }
            } catch { $errorMsg = $_.Exception.Message }
        }
        'scoop' {
            try {
                $cmd = "scoop update `"$AppName`""
                if ($CustomArgs) { $cmd += " $CustomArgs" }
                if ($Mode -eq 'dry-run') {
                    Write-Host "[DRY RUN] Would run: $cmd"
                    $success = $true
                } else {
                    Invoke-Expression $cmd
                    $success = $true
                }
            } catch { $errorMsg = $_.Exception.Message }
        }
    }
    
    return @{ Success = $success; Error = $errorMsg }
}

# Function to print summary report
function Show-Summary {
    Write-Host "`n=== BULK SOFTWARE INSTALLER SUMMARY ===" -ForegroundColor Cyan
    Write-Host "Mode: $Mode" -ForegroundColor Yellow
    Write-Host "Total apps processed: $($Global:Results.Total)" -ForegroundColor White
    
    if ($Global:Results.Installed.Count -gt 0) {
        Write-Host "`nSuccessfully installed/updated/uninstalled:" -ForegroundColor Green
        $Global:Results.Installed | ForEach-Object { Write-Host "  ✓ $_" -ForegroundColor Green }
    }
    
    if ($Global:Results.Skipped.Count -gt 0) {
        Write-Host "`nSkipped (already installed/not found):" -ForegroundColor Yellow
        $Global:Results.Skipped | ForEach-Object { Write-Host "  - $_" -ForegroundColor Yellow }
    }
    
    if ($Global:Results.Failed.Count -gt 0) {
        Write-Host "`nFailed:" -ForegroundColor Red
        $Global:Results.Failed | ForEach-Object { Write-Host "  ✗ $_" -ForegroundColor Red }
    }
    
    Write-Host "`nLog file: $(Join-Path $PSScriptRoot 'install.log')" -ForegroundColor Gray
}

# Main execution
Write-Host "Bulk Software Installer - Mode: $Mode" -ForegroundColor Cyan
Log-Result "=== Starting Bulk Software Installer in $Mode mode ==="

# Ensure all managers are available
Ensure-PackageManager 'winget'
Ensure-PackageManager 'choco'
Ensure-PackageManager 'scoop'

# Read config
if (-not (Test-Path $configPath)) {
    Write-Host "Config file not found: $configPath" -ForegroundColor Red
    Log-Result "ERROR: Config file not found: $configPath"
    exit 1
}

$apps = Get-Content $configPath | ConvertFrom-Json
$Global:Results.Total = $apps.Count

# Process each app
foreach ($app in $apps) {
    $appName = $app.name
    $manager = $app.manager
    $customArgs = $app.customArgs
    
    Write-Host "`nProcessing: $appName" -ForegroundColor White
    
    # Determine which managers to try
    $managersToTry = @()
    if ($manager) {
        $managersToTry += $manager
    } else {
        $managersToTry = @('winget', 'choco', 'scoop')
    }
    
    $processed = $false
    
    foreach ($tryManager in $managersToTry) {
        $installed = Test-AppInstalled -AppName $appName -Manager $tryManager
        
        switch ($Mode) {
            'install' {
                if ($installed) {
                    $msg = "$appName already installed via $tryManager"
                    Write-Host $msg -ForegroundColor Yellow
                    Log-Result $msg
                    $script:Results.Skipped += "$appName ($tryManager)"
                    $processed = $true
                    break
                } else {
                    Write-Host "Installing $appName with $tryManager..." -ForegroundColor Blue
                    $result = Install-App -AppName $appName -Manager $tryManager -CustomArgs $customArgs
                    if ($result.Success) {
                        $msg = "$appName installed with $tryManager"
                        Write-Host $msg -ForegroundColor Green
                        Log-Result $msg
                        $script:Results.Installed += "$appName ($tryManager)"
                        $processed = $true
                        break
                    } else {
                        Write-Host "Failed with $tryManager: $($result.Error)" -ForegroundColor Red
                    }
                }
            }
            'uninstall' {
                if (-not $installed) {
                    $msg = "$appName not installed via $tryManager"
                    Write-Host $msg -ForegroundColor Yellow
                    Log-Result $msg
                    $script:Results.Skipped += "$appName ($tryManager)"
                    $processed = $true
                    break
                } else {
                    Write-Host "Uninstalling $appName with $tryManager..." -ForegroundColor Blue
                    $result = Uninstall-App -AppName $appName -Manager $tryManager -CustomArgs $customArgs
                    if ($result.Success) {
                        $msg = "$appName uninstalled with $tryManager"
                        Write-Host $msg -ForegroundColor Green
                        Log-Result $msg
                        $script:Results.Installed += "$appName ($tryManager)"
                        $processed = $true
                        break
                    } else {
                        Write-Host "Failed with $tryManager: $($result.Error)" -ForegroundColor Red
                    }
                }
            }
            'update' {
                if (-not $installed) {
                    $msg = "$appName not installed via $tryManager"
                    Write-Host $msg -ForegroundColor Yellow
                    Log-Result $msg
                    $script:Results.Skipped += "$appName ($tryManager)"
                    $processed = $true
                    break
                } else {
                    Write-Host "Updating $appName with $tryManager..." -ForegroundColor Blue
                    $result = Update-App -AppName $appName -Manager $tryManager -CustomArgs $customArgs
                    if ($result.Success) {
                        $msg = "$appName updated with $tryManager"
                        Write-Host $msg -ForegroundColor Green
                        Log-Result $msg
                        $script:Results.Installed += "$appName ($tryManager)"
                        $processed = $true
                        break
                    } else {
                        Write-Host "Failed with $tryManager: $($result.Error)" -ForegroundColor Red
                    }
                }
            }
            'dry-run' {
                $msg = "Would process $appName with $tryManager"
                Write-Host $msg -ForegroundColor Cyan
                Log-Result $msg
                $script:Results.Installed += "$appName ($tryManager)"
                $processed = $true
                break
            }
        }
    }
    
    if (-not $processed) {
        $msg = "Failed to process $appName with any available manager"
        Write-Host $msg -ForegroundColor Red
        Log-Result $msg
        $script:Results.Failed += $appName
    }
}

# Show summary
Show-Summary
Log-Result "=== Bulk Software Installer completed ===" 