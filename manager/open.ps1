$ErrorActionPreference = 'Stop'
$libraryUrl = 'http://127.0.0.1:8901'
$isReady = $false
try {
    $libraryResponse = Invoke-WebRequest -Uri "$libraryUrl/library" -TimeoutSec 2 -UseBasicParsing
    $libraryItems = $libraryResponse.Content | ConvertFrom-Json
    $isReady = $libraryItems[0].id -like 'episode-*'
} catch {}
if (-not $isReady) {
    $libraryPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (-not (Test-Path -LiteralPath $libraryPython)) {
        throw 'Codex Python 런타임을 찾지 못했습니다. Codex에 관리페이지 실행을 요청해주세요.'
    }
    Start-Process -FilePath $libraryPython -ArgumentList @('"' + (Join-Path $PSScriptRoot 'server.py') + '"') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
    for ($libraryAttempt = 0; $libraryAttempt -lt 15; $libraryAttempt++) {
        Start-Sleep -Milliseconds 200
        try {
            $libraryResponse = Invoke-WebRequest -Uri "$libraryUrl/library" -TimeoutSec 1 -UseBasicParsing
            if ($libraryResponse.StatusCode -eq 200) { $isReady = $true; break }
        } catch {}
    }
}
if (-not $isReady) { throw '관리페이지를 실행하지 못했습니다. Codex에 확인을 요청해주세요.' }
Start-Process $libraryUrl
