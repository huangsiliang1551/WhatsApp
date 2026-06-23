# Meta API 全面检测脚本
$base = "http://localhost:8000/api/meta/accounts"
$errors = @()
$passed = 0
$total = 0

function Test-API {
    param($method, $path, $body, $desc)
    $total = $script:total
    $script:total++
    $url = "$base$path"
    try {
        $headers = @{ "Content-Type" = "application/json" }
        if ($script:token) { $headers["Authorization"] = "Bearer $script:token" }
        $params = @{ Uri = $url; Method = $method; Headers = $headers; SkipHttpErrorCheck = $true }
        if ($body) { $params["Body"] = ($body | ConvertTo-Json -Compress) }
        $res = Invoke-WebRequest @params
        $status = $res.StatusCode
        $content = try { $res.Content | ConvertTo-Json -Compress } catch { $res.Content }
        if ($status -ge 200 -and $status -lt 400) {
            Write-Host "  [PASS] $desc ($status)" -ForegroundColor Green
            $script:passed++
            return $content
        } else {
            Write-Host "  [FAIL] $desc ($status) - $($res.Content)" -ForegroundColor Red
            $script:errors += "$desc => HTTP $status : $($res.Content)"
            return $null
        }
    } catch {
        Write-Host "  [FAIL] $desc - $($_.Exception.Message)" -ForegroundColor Red
        $script:errors += "$desc => ERROR: $($_.Exception.Message)"
        return $null
    }
}

# 1. Login
Write-Host "`n=== Step 1: Login as Admin ===" -ForegroundColor Cyan
$loginBody = @{ username = "admin"; password = "admin123" } | ConvertTo-Json
$loginRes = Invoke-WebRequest -Uri "http://localhost:8000/api/admin/login" -Method POST -Body $loginBody -ContentType "application/json" -SkipHttpErrorCheck
if ($loginRes.StatusCode -eq 200) {
    $data = $loginRes.Content | ConvertFrom-Json
    $script:token = $data.access_token
    Write-Host "  [PASS] Login OK, token length=$($script:token.Length)" -ForegroundColor Green
} else {
    Write-Host "  [FAIL] Login failed: $($loginRes.Content)" -ForegroundColor Red
    exit 1
}

# 2. List accounts (empty)
Write-Host "`n=== Step 2: List Accounts (expect empty) ===" -ForegroundColor Cyan
$res = Test-API GET "" $null "GET / (list accounts)"
if ($res) { Write-Host "    Result: $res" }

# 3. Create manual account
Write-Host "`n=== Step 3: Create Manual Account ===" -ForegroundColor Cyan
$createBody = @{
    account_id = "test-acc-metatest"
    display_name = "Test Account MetaTest"
    meta_business_portfolio_id = "pf-test-metatest-001"
    waba_id = "waba-test-metatest-001"
    access_token = "EAATestTokenDummy123"
    verify_token = "verify_dummy_123"
    app_secret = "app_secret_dummy"
    token_source = "system_user"
    phone_numbers = @(
        @{
            phone_number_id = "pn-test-metatest-001"
            display_phone_number = "+8613800138001"
            verified_name = "Test Phone 1"
            quality_rating = "GREEN"
            is_registered = $true
            is_active = $true
        },
        @{
            phone_number_id = "pn-test-metatest-002"
            display_phone_number = "+8613800138002"
            verified_name = "Test Phone 2"
            quality_rating = "UNKNOWN"
            is_registered = $false
            is_active = $true
        }
    )
}
$res = Test-API POST "/manual" $createBody "POST /manual (create account)"

# 4. List accounts (should have 1)
Write-Host "`n=== Step 4: List Accounts (expect 1) ===" -ForegroundColor Cyan
$res = Test-API GET "" $null "GET / (list accounts after create)"

# 5. List phone numbers
Write-Host "`n=== Step 5: List Phone Numbers (all) ===" -ForegroundColor Cyan
$res = Test-API GET "/phone-numbers" $null "GET /phone-numbers"

# 6. List phone numbers for account
Write-Host "`n=== Step 6: List Phone Numbers by Account ===" -ForegroundColor Cyan
$res = Test-API GET "/test-acc-metatest/phone-numbers" $null "GET /{account_id}/phone-numbers"

# 7. List phone numbers for WABA
Write-Host "`n=== Step 7: List Phone Numbers by WABA ===" -ForegroundColor Cyan
$res = Test-API GET "/test-acc-metatest/wabas/waba-test-metatest-001/phone-numbers" $null "GET /{account_id}/wabas/{waba_id}/phone-numbers"

# 8. Update account status (disable)
Write-Host "`n=== Step 8: Update Account Status (disable) ===" -ForegroundColor Cyan
$res = Test-API PATCH "/test-acc-metatest/status" @{ is_active = $false } "PATCH /{account_id}/status (disable)"

# 9. Update account status (enable)
Write-Host "`n=== Step 9: Update Account Status (enable) ===" -ForegroundColor Cyan
$res = Test-API PATCH "/test-acc-metatest/status" @{ is_active = $true } "PATCH /{account_id}/status (enable)"

# 10. Update WABA status (disable)
Write-Host "`n=== Step 10: Update WABA Status (disable) ===" -ForegroundColor Cyan
$res = Test-API PATCH "/test-acc-metatest/wabas/waba-test-metatest-001/status" @{ is_active = $false } "PATCH /{account_id}/wabas/{waba_id}/status (disable)"

# 11. Update WABA status (enable)
Write-Host "`n=== Step 11: Update WABA Status (enable) ===" -ForegroundColor Cyan
$res = Test-API PATCH "/test-acc-metatest/wabas/waba-test-metatest-001/status" @{ is_active = $true } "PATCH /{account_id}/wabas/{waba_id}/status (enable)"

# 12. Update phone number status (disable)
Write-Host "`n=== Step 12: Update Phone Status (disable) ===" -ForegroundColor Cyan
$res = Test-API PATCH "/test-acc-metatest/wabas/waba-test-metatest-001/phone-numbers/pn-test-metatest-001/status" @{ is_active = $false } "PATCH phone status (disable)"

# 13. Update phone number status (enable)
Write-Host "`n=== Step 13: Update Phone Status (enable) ===" -ForegroundColor Cyan
$res = Test-API PATCH "/test-acc-metatest/wabas/waba-test-metatest-001/phone-numbers/pn-test-metatest-001/status" @{ is_active = $true } "PATCH phone status (enable)"

# 14. Sync phone numbers
Write-Host "`n=== Step 14: Sync Phone Numbers ===" -ForegroundColor Cyan
$res = Test-API POST "/test-acc-metatest/wabas/waba-test-metatest-001/phone-numbers/sync" $null "POST sync phone numbers"

# 15. Subscribe webhook
Write-Host "`n=== Step 15: Subscribe Webhook ===" -ForegroundColor Cyan
$whBody = @{ callback_url = "https://example.com/webhook"; verify_token = "test_verify_123" }
$res = Test-API POST "/test-acc-metatest/wabas/waba-test-metatest-001/webhook-subscription" $whBody "POST webhook-subscription"

# 16. List webhook subscriptions (global)
Write-Host "`n=== Step 16: List Webhook Subscriptions ===" -ForegroundColor Cyan
$res = Test-API GET "/webhook-subscriptions" $null "GET /webhook-subscriptions"

# 17. Health check
Write-Host "`n=== Step 17: Health Check ===" -ForegroundColor Cyan
$res = Test-API POST "/test-acc-metatest/wabas/waba-test-metatest-001/health-check" $null "POST health-check"

# 18. Get global webhook config
Write-Host "`n=== Step 18: Get Global Webhook Config ===" -ForegroundColor Cyan
$res = Test-API GET "/global-webhook-config" $null "GET /global-webhook-config"

# 19. Update global webhook config
Write-Host "`n=== Step 19: Update Global Webhook Config ===" -ForegroundColor Cyan
$whCfg = @{ callback_url = "https://my-server.com/webhooks/whatsapp"; verify_token = "new_verify_token" }
$res = Test-API PUT "/global-webhook-config" $whCfg "PUT /global-webhook-config"

# 20. Get global webhook config again (verify update)
Write-Host "`n=== Step 20: Get Global Webhook Config (verify) ===" -ForegroundColor Cyan
$res = Test-API GET "/global-webhook-config" $null "GET /global-webhook-config (after update)"

# 21. List embedded signup sessions
Write-Host "`n=== Step 21: List Signup Sessions ===" -ForegroundColor Cyan
$res = Test-API GET "/embedded-signup/sessions" $null "GET /embedded-signup/sessions"

# 22. Create embedded signup session
Write-Host "`n=== Step 22: Create Signup Session ===" -ForegroundColor Cyan
$signupBody = @{ account_id = "test-acc-metatest"; redirect_uri = "https://example.com/callback" }
$res = Test-API POST "/embedded-signup/session" $signupBody "POST /embedded-signup/session"

# 23. Cleanup: Delete account
Write-Host "`n=== Step 23: Cleanup - Delete Account ===" -ForegroundColor Cyan
$res = Test-API DELETE "/test-acc-metatest/wabas/waba-test-metatest-001" $null "DELETE /{account_id}/wabas/{waba_id}"

# Summary
Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  检测报告" -ForegroundColor Cyan
Write-Host "============================================" 
Write-Host "  总计: $total 项" -ForegroundColor White
Write-Host "  通过: $passed 项" -ForegroundColor Green
Write-Host "  失败: $($errors.Count) 项" -ForegroundColor $(if ($errors.Count -gt 0) { "Red" } else { "Green" })
if ($errors.Count -gt 0) {
    Write-Host "`n  失败详情:" -ForegroundColor Yellow
    foreach ($e in $errors) { Write-Host "    - $e" -ForegroundColor Red }
}
Write-Host "============================================" -ForegroundColor Cyan
