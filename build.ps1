# build.ps1 - Build both BrowserControl executables
# Usage: .\build.ps1          - Build without console (production)
#        .\build.ps1 -Debug   - Build with console for debugging

param(
    [switch]$Debug
)

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  BrowserControl Build Script" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
if ($Debug) {
    Write-Host "  🐛 DEBUG MODE (with console window)" -ForegroundColor Yellow
} else {
    Write-Host "  📦 PRODUCTION MODE (no console)" -ForegroundColor Green
}
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check if PyInstaller is installed
Write-Host "Checking PyInstaller..." -ForegroundColor Yellow
try {
    $pyiVersion = python -m PyInstaller --version 2>&1
    Write-Host "✅ PyInstaller found: $pyiVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ PyInstaller not found! Installing..." -ForegroundColor Red
    pip install pyinstaller==6.11.0
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to install PyInstaller!" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""

# Prepare spec files based on debug flag
if ($Debug) {
    Write-Host "Modifying .spec files for debug mode..." -ForegroundColor Yellow
    
    # Backup original spec files
    Copy-Item "BrowserControl.spec" "BrowserControl.spec.bak" -Force
    Copy-Item "backend\BrowserControlAPI.spec" "backend\BrowserControlAPI.spec.bak" -Force
    
    # Enable console in spec files
    (Get-Content "BrowserControl.spec") -replace "console=False", "console=True" | Set-Content "BrowserControl.spec"
    (Get-Content "backend\BrowserControlAPI.spec") -replace "console=False", "console=True" | Set-Content "backend\BrowserControlAPI.spec"
    
    Write-Host "✅ Console mode enabled" -ForegroundColor Green
}

Write-Host ""

# Clean previous builds
Write-Host "Cleaning previous builds..." -ForegroundColor Yellow
Remove-Item -Path "dist", "build" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "backend\dist", "backend\build" -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "✅ Cleaned build directories" -ForegroundColor Green
Write-Host ""

# Build main application
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Building main application..." -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Cyan
pyinstaller --clean BrowserControl.spec

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Main application build failed!" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Main application built successfully!" -ForegroundColor Green
Write-Host ""

# Build backend API
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Building backend API..." -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Cyan
Set-Location backend
pyinstaller --clean BrowserControlAPI.spec
Set-Location ..

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Backend API build failed!" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Backend API built successfully!" -ForegroundColor Green
Write-Host ""

# Copy backend executable to main dist folder
Write-Host "Copying backend executable to dist folder..." -ForegroundColor Yellow
Copy-Item "backend\dist\BrowserControlAPI.exe" "dist\" -Force
Write-Host "✅ Backend executable copied" -ForegroundColor Green
Write-Host ""

# Restore original spec files if in debug mode
if ($Debug) {
    Write-Host "Restoring original .spec files..." -ForegroundColor Yellow
    Move-Item "BrowserControl.spec.bak" "BrowserControl.spec" -Force
    Move-Item "backend\BrowserControlAPI.spec.bak" "backend\BrowserControlAPI.spec" -Force
    Write-Host "✅ Spec files restored" -ForegroundColor Green
    Write-Host ""
}

# Show results
Write-Host "============================================" -ForegroundColor Green
Write-Host "  ✅ Build Complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
if ($Debug) {
    Write-Host "⚠️  DEBUG BUILD - Console window will be visible" -ForegroundColor Yellow
    Write-Host ""
}
Write-Host "Executables are in the 'dist' folder:" -ForegroundColor White
Write-Host "  📦 dist\BrowserControl.exe" -ForegroundColor Cyan
Write-Host "  📦 dist\BrowserControlAPI.exe" -ForegroundColor Cyan
Write-Host ""

# Show file sizes
$mainSize = (Get-Item "dist\BrowserControl.exe").Length / 1MB
$backendSize = (Get-Item "dist\BrowserControlAPI.exe").Length / 1MB
Write-Host "File sizes:" -ForegroundColor White
Write-Host ("  BrowserControl.exe: {0:N2} MB" -f $mainSize) -ForegroundColor Gray
Write-Host ("  BrowserControlAPI.exe: {0:N2} MB" -f $backendSize) -ForegroundColor Gray
Write-Host ""
Write-Host "Total size: $([math]::Round($mainSize + $backendSize, 2)) MB" -ForegroundColor White
