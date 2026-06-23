import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Account, MediaAsset, MediaAssetProviderSync


def _create_account(session: Session, account_id: str) -> None:
    session.add(
        Account(
            account_id=account_id,
            display_name=f"Media sync {account_id}",
            provider_type="whatsapp",
        )
    )
    session.commit()


def _create_asset(session: Session, *, account_id: str, asset_id: str) -> None:
    session.add(
        MediaAsset(
            id=asset_id,
            account_id=account_id,
            name=f"{asset_id}.jpg",
            asset_type="image",
            mime_type="image/jpeg",
            file_size=1024,
            storage_url=f"https://cdn.example.com/{asset_id}.jpg",
            source="test",
            tags_json=[],
            is_active=True,
        )
    )
    session.commit()


def test_media_asset_provider_sync_rejects_duplicate_null_phone_scope(
    db_session_factory: sessionmaker[Session],
) -> None:
    session = db_session_factory()
    try:
        account_id = "media-sync-null-scope-account"
        asset_id = "media-sync-null-scope-asset"
        _create_account(session, account_id)
        _create_asset(session, account_id=account_id, asset_id=asset_id)

        session.add(
            MediaAssetProviderSync(
                account_id=account_id,
                asset_id=asset_id,
                provider_name="mock",
                phone_number_id=None,
                sync_status="synced",
            )
        )
        session.commit()
        session.add(
            MediaAssetProviderSync(
                account_id=account_id,
                asset_id=asset_id,
                provider_name="mock",
                phone_number_id=None,
                sync_status="synced",
            )
        )

        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.close()


def test_media_asset_provider_sync_allows_distinct_phone_scopes(
    db_session_factory: sessionmaker[Session],
) -> None:
    session = db_session_factory()
    try:
        account_id = "media-sync-phone-scope-account"
        asset_id = "media-sync-phone-scope-asset"
        _create_account(session, account_id)
        _create_asset(session, account_id=account_id, asset_id=asset_id)

        session.add_all(
            [
                MediaAssetProviderSync(
                    account_id=account_id,
                    asset_id=asset_id,
                    provider_name="mock",
                    phone_number_id="phone-a",
                    sync_status="synced",
                ),
                MediaAssetProviderSync(
                    account_id=account_id,
                    asset_id=asset_id,
                    provider_name="mock",
                    phone_number_id="phone-b",
                    sync_status="synced",
                ),
            ]
        )
        session.commit()

        rows = session.query(MediaAssetProviderSync).filter_by(asset_id=asset_id).all()
        assert {row.phone_number_id for row in rows} == {"phone-a", "phone-b"}
    finally:
        session.close()
