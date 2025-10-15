# test-api.ps1
# Simple script to test your FastAPI summarizer endpoints on Windows

$apiKey = "periodic-table-of-the-elements-118"
$baseUrl = "http://127.0.0.1:8000"

Write-Host "Testing Summarizer API..."
Write-Host "-----------------------------------"

# 1️⃣ Health check
Write-Host "`n➡️  GET /health"
try {
    $health = Invoke-WebRequest -Uri "$baseUrl/health" -Headers @{ "X-API-Key" = $apiKey } -UseBasicParsing
    Write-Host "✅ Health response:" $health.Content
} catch {
    Write-Host "❌ Failed to reach /health:" $_.Exception.Message
    exit 1
}

# 2️⃣ Summarize (English)
$body = @{
    text      = "FastAPI is a modern, high-performance web framework for building APIs with Python."
    max_words = 20
    language  = "en"
    tone      = "neutral"
} | ConvertTo-Json

Write-Host "`n➡️  POST /summarize (English)"
try {
    $summary = Invoke-WebRequest -Uri "$baseUrl/summarize" `
        -Headers @{ "X-API-Key" = $apiKey; "Content-Type" = "application/json" } `
        -Method POST -Body $body -UseBasicParsing
    Write-Host "✅ Summarize response:" $summary.Content
} catch {
    Write-Host "❌ Summarize failed:" $_.Exception.Message
}

Write-Host "`n-----------------------------------"
Write-Host "Done."
