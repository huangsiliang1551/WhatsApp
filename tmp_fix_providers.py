"""Fix test helper classes that directly extend MessagingProvider to implement download_media."""
import re

files_to_fix = {
    r"E:\codex\WhatsApp\tests\test_whatsapp_webhooks.py": {
        "class_method_end": (
            r"    async def sync_media_asset\(self, payload: MediaAssetSyncRequest\) -> MediaAssetSyncResult:\n"
            r"        return MediaAssetSyncResult\(\n"
            r"            provider_name=self\.provider_name,\n"
            r"            phone_number_id=payload\.phone_number_id,\n"
            r"            waba_id=payload\.waba_id,\n"
            r"            sync_status=\"unsupported\",\n"
            r"            raw_response={\"asset_id\": payload\.asset_id},\n"
            r"        \)"
        ),
        "insertion": (
            "\n"
            "    async def download_media(\n"
            "        self,\n"
            "        *,\n"
            "        media_id: str,\n"
            "        access_token: str,\n"
            "        waba_id: str | None = None,\n"
            "        phone_number_id: str | None = None,\n"
            "    ) -> tuple[str, bytes, str]:\n"
            '        return f"{media_id}.bin", b"mock-media-content", "application/octet-stream"'
        ),
    },
    r"E:\codex\WhatsApp\tests\test_templates.py": {
        "class_method_end": (
            r"(class AcceptedWhatsAppLikeProvider\(MessagingProvider\):.*?"
            r"    async def sync_media_asset\(self, payload: MediaAssetSyncRequest\) -> MediaAssetSyncResult:\n"
            r"        existing_provider_media_id = payload\.resolved_existing_provider_media_id\n"
            r"        return MediaAssetSyncResult\(\n"
            r"            provider_name=self\.provider_name,\n"
            r"            phone_number_id=payload\.phone_number_id,\n"
            r"            waba_id=payload\.waba_id,\n"
            r"            provider_media_id=existing_provider_media_id,\n"
            r"            sync_status=\"reused\" if existing_provider_media_id else \"failed\",\n"
            r"            error_code=None if existing_provider_media_id else \"missing_media_id\",\n"
            r"            error_message=\(None if existing_provider_media_id else \"Accepted test provider expects an existing provider media id\.\"\),\n"
            r"            raw_response={\"asset_id\": payload\.asset_id},\n"
            r"        \))"
        ),
        "insertion": (
            "\n"
            "    async def download_media(\n"
            "        self,\n"
            "        *,\n"
            "        media_id: str,\n"
            "        access_token: str,\n"
            "        waba_id: str | None = None,\n"
            "        phone_number_id: str | None = None,\n"
            "    ) -> tuple[str, bytes, str]:\n"
            '        return f"{media_id}.bin", b"mock-media-content", "application/octet-stream"'
        ),
        "second_match": True,  # There's also FailingTemplateProvider
    },
}

# Fix test_whatsapp_webhooks.py first (just the FixedMessageIdWhatsAppProvider)
content = open(files_to_fix[r"E:\codex\WhatsApp\tests\test_whatsapp_webhooks.py"], 'r', encoding='utf-8').read()
search = files_to_fix[r"E:\codex\WhatsApp\tests\test_whatsapp_webhooks.py"]["class_method_end"]
insert = files_to_fix[r"E:\codex\WhatsApp\tests\test_whatsapp_webhooks.py"]["insertion"]
replacement = search + insert
new_content = re.sub(search, replacement, content, count=1)
open(r"E:\codex\WhatsApp\tests\test_whatsapp_webhooks.py", 'w', encoding='utf-8').write(new_content)
print("test_whatsapp_webhooks.py fixed" if new_content != content else "test_whatsapp_webhooks.py NOT fixed")

# Fix test_templates.py - AcceptedWhatsAppLikeProvider
content2 = open(files_to_fix[r"E:\codex\WhatsApp\tests\test_templates.py"], 'r', encoding='utf-8').read()
# First fix AcceptedWhatsAppLikeProvider
search2 = files_to_fix[r"E:\codex\WhatsApp\tests\test_templates.py"]["class_method_end"]
insert2 = files_to_fix[r"E:\codex\WhatsApp\tests\test_templates.py"]["insertion"]
replacement2 = search2[:-3] + insert2 + r"\1"  # capture group, add insert, then the rest
new_content2 = re.sub(search2, lambda m: m.group(0) + "\n" + insert2.lstrip('\n'), content2, count=1)
print("test_templates.py AcceptedWhatsAppLikeProvider fixed" if new_content2 != content2 else "NOT fixed - trying next approach")

# Also fix FailingTemplateProvider
search3 = (
    r"    async def sync_media_asset\(self, payload: MediaAssetSyncRequest\) -> MediaAssetSyncResult:\n"
    r"        del payload\n"
    r"        raise RuntimeError\(\"provider_sync_unavailable\"\)"
)
insert3 = (
    "\n"
    "    async def download_media(\n"
    "        self,\n"
    "        *,\n"
    "        media_id: str,\n"
    "        access_token: str,\n"
    "        waba_id: str | None = None,\n"
    "        phone_number_id: str | None = None,\n"
    "    ) -> tuple[str, bytes, str]:\n"
    '        del media_id, access_token, waba_id, phone_number_id\n'
    '        raise RuntimeError("provider_download_unavailable")'
)
replacement3 = search3 + insert3
new_content3 = re.sub(search3, replacement3, new_content2, count=1)
print("test_templates.py FailingTemplateProvider fixed" if new_content3 != new_content2 else "FailingTemplateProvider NOT fixed")

open(r"E:\codex\WhatsApp\tests\test_templates.py", 'w', encoding='utf-8').write(new_content3)
print("test_templates.py written")
