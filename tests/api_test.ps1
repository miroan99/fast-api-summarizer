# ===========================
# PowerShell API test script
# ===========================

# run i powershell with:  .\tests\api_test.ps1
#set persistent api_key for user: [Environment]::SetEnvironmentVariable("API_KEY", "my-super-secret-key", "User")
#Erase api_key: [Environment]::SetEnvironmentVariable("API_KEY", $null, "User")
#

$API_KEY = $env:API_KEY
if (-not $API_KEY) {
    Write-Host "⚠️  API_KEY not set. Run: `$env:API_KEY='your-api-key'"
    exit
}

Write-Host "Testing /health ..."
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/health"

Write-Host "Testing /summarize ..."
$payload = @{
    text = "Dette er en kort testtekst til summarizer."
    max_words = 40
    language = "da"
    tone = "neutral"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/summarize" `
  -Headers @{ "X-API-Key" = $API_KEY } `
  -ContentType "application/json" `
  -Body $payload | ConvertTo-Json -Depth 4

Write-Host "Testing /summarize-file ..."
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/summarize-file" `
  -Headers @{ "X-API-Key" = $API_KEY } `
  -Form @{
    file = Get-Item ".\docs\sample.pdf"
    max_words = "120"
    language = "da"
  } | ConvertTo-Json -Depth 4
