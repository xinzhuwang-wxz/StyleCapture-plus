from __future__ import annotations

from stylecapture_backend.features.account.application import AccountApplication
from stylecapture_backend.features.account.domain import AppleIdentityClaims
from stylecapture_backend.features.account.infrastructure.apple_identity import (
    AppleClientSecretSigner,
    HttpAppleProviderGrantRevoker,
)
from stylecapture_backend.features.account.infrastructure.repository import (
    AppleProviderGrantCipher,
    SqlAlchemyAccountRepository,
    SqlAlchemyAppleProviderGrantRepository,
)
from stylecapture_backend.features.account.interfaces.worker import (
    register_account_revocation_sweep_task,
)
from stylecapture_backend.platform.celery import build_celery
from stylecapture_backend.platform.config import BackendSettings
from stylecapture_backend.platform.database import build_session_factory


class MaintenanceOnlyAppleIdentity:
    async def verify(
        self,
        identity_token: str,
        authorization_code: str,
    ) -> AppleIdentityClaims:
        raise RuntimeError("account maintenance worker does not authenticate Apple users")


settings = BackendSettings()  # type: ignore[call-arg]
sessions = build_session_factory(
    settings.database_url.get_secret_value(),
    pooled=False,
)
apple_provider_grant_cipher = AppleProviderGrantCipher(
    settings.apple_provider_grant_encryption_key.get_secret_value()
)
account_repository = SqlAlchemyAccountRepository(
    sessions,
    apple_provider_grant_cipher=apple_provider_grant_cipher,
)
apple_provider_grants = SqlAlchemyAppleProviderGrantRepository(
    sessions,
    cipher=apple_provider_grant_cipher,
)

apple_provider_revoker = None
if (
    settings.apple_team_id is not None
    and settings.apple_key_id is not None
    and settings.apple_private_key_pem.get_secret_value()
):
    apple_client_id = settings.apple_client_ids[0]
    apple_client_secret = AppleClientSecretSigner(
        team_id=settings.apple_team_id,
        key_id=settings.apple_key_id,
        client_id=apple_client_id,
        private_key_pem=settings.apple_private_key_pem.get_secret_value(),
    )
    apple_provider_revoker = HttpAppleProviderGrantRevoker(
        client_id=apple_client_id,
        client_secret=apple_client_secret,
    )

accounts = AccountApplication(
    repository=account_repository,
    apple_identity=MaintenanceOnlyAppleIdentity(),
    allowed_audiences=frozenset(settings.apple_client_ids),
    token_secret=settings.session_signing_secret.get_secret_value(),
    apple_provider_grants=apple_provider_grants,
    apple_provider_revoker=apple_provider_revoker,
)

celery = build_celery(settings.redis_url.get_secret_value())
account_revocation_sweep_task = register_account_revocation_sweep_task(
    celery,
    accounts,
    max_retries=settings.worker_max_retries,
    queue=settings.maintenance_queue,
    schedule_seconds=settings.account_revocation_sweep_interval_seconds,
)
