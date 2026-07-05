# Tailscale 연동 설정 스크립트 (Windows)
# 사용법: powershell -ExecutionPolicy Bypass -File scripts\setup_tailscale.ps1

$ErrorActionPreference = "Stop"
$TailscaleExe = "C:\Program Files\Tailscale\tailscale.exe"
$Port = if ($env:SERVER_PORT) { $env:SERVER_PORT } else { "8765" }

Write-Host "=== My Agent Tailscale 설정 ===" -ForegroundColor Cyan

if (-not (Test-Path $TailscaleExe)) {
    Write-Host "Tailscale 미설치. 설치 중..." -ForegroundColor Yellow
    winget install Tailscale.Tailscale --accept-package-agreements --accept-source-agreements
}

Write-Host "`n[1/3] Tailscale 로그인" -ForegroundColor Green
Write-Host "브라우저가 열리면 Google/Microsoft 등으로 로그인하세요."
& $TailscaleExe up

$status = & $TailscaleExe status 2>&1 | Out-String
if ($status -match "NeedsLogin|Logged out") {
    Write-Host "`n아직 로그인이 완료되지 않았습니다." -ForegroundColor Red
    Write-Host "시스템 트레이의 Tailscale 아이콘에서 Log in을 완료한 뒤 다시 실행하세요."
    exit 1
}

Write-Host "`n[2/3] Tailscale IP 확인" -ForegroundColor Green
$tsIp = & $TailscaleExe ip -4
Write-Host "Tailscale IP: $tsIp"
Write-Host "모바일 앱 서버 주소: http://${tsIp}:${Port}"

$hostname = (& $TailscaleExe status --json | ConvertFrom-Json).Self.DNSName
if ($hostname) {
    Write-Host "MagicDNS (선택): http://$hostname`:$Port"
}

Write-Host "`n[3/3] Windows 방화벽 규칙 추가 (포트 $Port)" -ForegroundColor Green
$ruleName = "My Agent Chat Server ($Port)"
$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if (-not $existing) {
    New-NetFirewallRule -DisplayName $ruleName `
        -Direction Inbound `
        -Action Allow `
        -Protocol TCP `
        -LocalPort $Port `
        -Profile Any | Out-Null
    Write-Host "방화벽 규칙 추가됨: $ruleName"
} else {
    Write-Host "방화벽 규칙이 이미 존재합니다."
}

Write-Host "`n=== 다음 단계 ===" -ForegroundColor Cyan
Write-Host "1. 스마트폰에 Tailscale 앱 설치 (iOS/Android)"
Write-Host "2. PC와 같은 계정으로 로그인"
Write-Host "3. PC에서: python -m server.main"
Write-Host "4. 폰 브라우저/PWA 설정에 입력: http://${tsIp}:${Port}"
Write-Host "`n다른 Wi-Fi( LTE/5G 포함)에서도 위 주소로 접속 가능합니다."
