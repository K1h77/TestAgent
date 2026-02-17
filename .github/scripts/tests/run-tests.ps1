#!/usr/bin/env pwsh

$ErrorActionPreference = "Stop"

function Find-Bash {
  $candidates = @(
    "C:\Program Files\Git\bin\bash.exe",
    "C:\Program Files (x86)\Git\bin\bash.exe",
    "$env:ProgramFiles\Git\bin\bash.exe",
    "bash.exe"
  )
  
  foreach ($bash in $candidates) {
    if (Test-Path $bash) {
      return $bash
    }
  }
  
  try {
    $bash = (Get-Command bash.exe -ErrorAction SilentlyContinue).Source
    if ($bash) { return $bash }
  } catch { }
  
  return $null
}

function Find-Bats {
  param([string]$BashPath)
  
  & $BashPath -c 'command -v bats' 2>$null
  return $?
}

function Install-Bats {
  param([string]$BashPath)
  
  Write-Host "Installing bats-core via npm..." -ForegroundColor Cyan
  & npm install -g bats-core
  
  if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to install bats via npm" -ForegroundColor Red
    return $false
  }
  
  return $true
}

function Main {
  param([string]$TestName = "all")
  
  Write-Host "Pre-commit Test Runner" -ForegroundColor Blue
  Write-Host ""
  
  $bash = Find-Bash
  if (-not $bash) {
    Write-Host "bash not found" -ForegroundColor Red
    Write-Host ""
    Write-Host "Install one of these to run tests:" -ForegroundColor Yellow
    Write-Host "  1. Git for Windows: https://git-scm.com/download/win" -ForegroundColor Gray
    Write-Host "  2. WSL2 with Ubuntu: wsl --install Ubuntu" -ForegroundColor Gray
    Write-Host ""
    exit 1
  }
  
  Write-Host "Found bash: $bash" -ForegroundColor Green
  
  if (-not (Find-Bats $bash)) {
    Write-Host "bats-core not found" -ForegroundColor Yellow
    Write-Host "Installing bats-core..." -ForegroundColor Cyan
    
    if (-not (Install-Bats $bash)) {
      Write-Host ""
      Write-Host "Manual install:" -ForegroundColor Yellow
      Write-Host "  npm install -g bats-core" -ForegroundColor Gray
      exit 1
    }
  }
  
  Write-Host "bats-core ready" -ForegroundColor Green
  Write-Host ""
  Write-Host "Running tests..." -ForegroundColor Cyan
  Write-Host ""
  
  $scriptDir = $PSScriptRoot
  if (-not $scriptDir) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
  }
  
  $testScript = Join-Path $scriptDir "run-tests.sh"
  $testScript = $testScript -replace '\\', '/'
  $cwd = (Get-Location).Path -replace '\\', '/'
  
  & $bash -c "cd '$cwd' ; bash '$testScript' '$TestName'"
  $exitCode = $LASTEXITCODE
  
  if ($exitCode -eq 0) {
    Write-Host ""
    Write-Host "All tests passed!" -ForegroundColor Green
  } else {
    Write-Host ""
    Write-Host "Tests failed (exit code: $exitCode)" -ForegroundColor Red
  }
  
  exit $exitCode
}

Main $args[0]
