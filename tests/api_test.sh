#!/usr/bin/env bash
API_KEY="${API_KEY:-your-api-key}"

curl -s -X GET "http://127.0.0.1:8000/health"
echo
curl -s -X POST "http://127.0.0.1:8000/summarize" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text":"Dette er en testtekst","max_words":40,"language":"da"}'
echo
