$file = "E:\codex\WhatsApp\tests\test_whatsapp_webhooks.py"
$content = [System.IO.File]::ReadAllText($file)

$oldLine = "        raw_response={`"asset_id`": payload.asset_id},`n        )`n`n"
$newInsert = "        raw_response={`"asset_id`": payload.asset_id},`n        )`n`n    async def download_media(`n        self,`n        *,`n        media_id: str,`n        access_token: str,`n        waba_id: str | None = None,`n        phone_number_id: str | None = None,`n    ) -> tuple[str, bytes, str]:`n        return f`"{media_id}.bin`", b`"mock-media-content`", `"application/octet-stream`"`n"

# Find and replace only the specific occurrence in FixedMessageIdWhatsAppProvider
$searchPattern = "    async def sync_media_asset(self, payload: MediaAssetSyncRequest) -> MediaAssetSyncResult:`n        return MediaAssetSyncResult(`n            provider_name=self.provider_name,`n            phone_number_id=payload.phone_number_id,`n            waba_id=payload.waba_id,`n            sync_status=`"unsupported`",`n            raw_response={`"asset_id`": payload.asset_id},`n        )"

$newContent = $content -replace [regex]::Escape($searchPattern), ($searchPattern + "`n`n    async def download_media(`n        self,`n        *,`n        media_id: str,`n        access_token: str,`n        waba_id: str | None = None,`n        phone_number_id: str | None = None,`n    ) -> tuple[str, bytes, str]:`n        return f`"`{media_id}`.bin`", b`"mock-media-content`", `"application/octet-stream`"")

[System.IO.File]::WriteAllText($file, $newContent)
Write-Host "Done"
