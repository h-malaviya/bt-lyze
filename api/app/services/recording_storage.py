import asyncio
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath
from uuid import UUID, uuid4

from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.identity import ClientSecretCredential, DefaultAzureCredential
from azure.storage.blob import BlobSasPermissions, BlobServiceClient, generate_blob_sas

from api.app.config import Settings

AZURE_CLOCK_SKEW_MINUTES = 5


class AzureStorageConfigurationError(ValueError):
    pass


class AzureBlobNotFoundError(RuntimeError):
    pass


class AzureBlobSizeMismatchError(ValueError):
    pass


class AzureStorageOperationError(OSError):
    pass


@dataclass(frozen=True)
class AzureUploadGrant:
    upload_url: str
    expires_at: datetime


def candidate_recording_filename(candidate_name: str, original_filename: str) -> str:
    normalized_name = unicodedata.normalize("NFKD", candidate_name)
    candidate_slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized_name).strip("-")
    candidate_slug = candidate_slug[:160].lower() or "candidate-recording"
    suffix_match = re.search(r"\.[a-zA-Z0-9]{1,10}$", original_filename)
    suffix = suffix_match.group(0).lower() if suffix_match else ""
    return f"{candidate_slug}{suffix}"


def create_recording_path(
    panel_id: UUID,
    candidate_name: str,
    original_filename: str,
) -> str:
    filename = candidate_recording_filename(candidate_name, original_filename)
    return f"{panel_id}/{uuid4()}/{filename}"


def validate_recording_path(storage_path: str, panel_id: UUID) -> None:
    path = PurePosixPath(storage_path)
    parts = path.parts
    if (
        path.is_absolute()
        or "\\" in storage_path
        or ".." in parts
        or len(parts) != 3
        or parts[0] != str(panel_id)
    ):
        raise ValueError("Recording path does not belong to this panel")
    try:
        UUID(parts[1])
    except ValueError as exc:
        raise ValueError("Recording path is invalid") from exc


def _azure_blob_service(settings: Settings) -> BlobServiceClient:
    if not settings.azure_storage_container:
        raise AzureStorageConfigurationError("Azure Blob Storage is not configured")
    if settings.azure_storage_connection_string:
        return BlobServiceClient.from_connection_string(
            settings.azure_storage_connection_string
        )
    if not settings.azure_storage_account_name:
        raise AzureStorageConfigurationError("Azure Blob Storage is not configured")
    service_principal_values = (
        settings.azure_tenant_id,
        settings.azure_client_id,
        settings.azure_client_secret,
    )
    if all(service_principal_values):
        credential = ClientSecretCredential(
            tenant_id=settings.azure_tenant_id,
            client_id=settings.azure_client_id,
            client_secret=settings.azure_client_secret,
        )
    elif any(service_principal_values):
        raise AzureStorageConfigurationError(
            "Azure tenant, client ID, and client secret must be configured together"
        )
    else:
        credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
    account_url = (
        f"https://{settings.azure_storage_account_name}.blob.core.windows.net"
    )
    return BlobServiceClient(account_url=account_url, credential=credential)


def _azure_account_key(settings: Settings) -> tuple[str, str] | None:
    if not settings.azure_storage_connection_string:
        return None
    try:
        values = dict(
            part.split("=", 1)
            for part in settings.azure_storage_connection_string.split(";")
            if part
        )
        account_name = values["AccountName"]
        account_key = values["AccountKey"]
    except (KeyError, ValueError) as exc:
        raise AzureStorageConfigurationError(
            "Azure Storage connection string is invalid"
        ) from exc
    if not account_name or not account_key:
        raise AzureStorageConfigurationError(
            "Azure Storage connection string is invalid"
        )
    return account_name, account_key


async def _azure_sas_url(
    settings: Settings,
    storage_path: str,
    permission: BlobSasPermissions,
    ttl_seconds: int,
) -> tuple[str, datetime]:
    service = _azure_blob_service(settings)
    now = datetime.now(UTC)
    starts_at = now - timedelta(minutes=AZURE_CLOCK_SKEW_MINUTES)
    expires_at = now + timedelta(seconds=ttl_seconds)
    try:
        account_key = _azure_account_key(settings)
        if account_key:
            account_name, secret_key = account_key
            sas = generate_blob_sas(
                account_name=account_name,
                container_name=settings.azure_storage_container,
                blob_name=storage_path,
                account_key=secret_key,
                permission=permission,
                start=starts_at,
                expiry=expires_at,
                protocol="https",
            )
        else:
            delegation_key = await asyncio.to_thread(
                service.get_user_delegation_key,
                starts_at,
                expires_at,
            )
            sas = generate_blob_sas(
                account_name=settings.azure_storage_account_name,
                container_name=settings.azure_storage_container,
                blob_name=storage_path,
                user_delegation_key=delegation_key,
                permission=permission,
                start=starts_at,
                expiry=expires_at,
                protocol="https",
            )
    except AzureError as exc:
        raise AzureStorageOperationError("Azure could not issue a blob access URL") from exc
    blob_url = service.get_blob_client(
        container=settings.azure_storage_container,
        blob=storage_path,
    ).url
    return f"{blob_url}?{sas}", expires_at


async def create_azure_upload_grant(
    settings: Settings,
    storage_path: str,
) -> AzureUploadGrant:
    upload_url, expires_at = await _azure_sas_url(
        settings,
        storage_path,
        BlobSasPermissions(create=True, write=True),
        settings.azure_upload_sas_ttl_seconds,
    )
    return AzureUploadGrant(upload_url=upload_url, expires_at=expires_at)


async def create_azure_read_url(settings: Settings, storage_path: str) -> str:
    read_url, _ = await _azure_sas_url(
        settings,
        storage_path,
        BlobSasPermissions(read=True),
        settings.azure_read_sas_ttl_seconds,
    )
    return read_url


async def verify_azure_blob(
    settings: Settings,
    storage_path: str,
    expected_size_bytes: int,
) -> None:
    service = _azure_blob_service(settings)
    blob = service.get_blob_client(settings.azure_storage_container, storage_path)
    try:
        properties = await asyncio.to_thread(blob.get_blob_properties)
    except ResourceNotFoundError as exc:
        raise AzureBlobNotFoundError("Uploaded Azure recording could not be found") from exc
    except AzureError as exc:
        raise AzureStorageOperationError("Azure recording verification failed") from exc
    if properties.size != expected_size_bytes:
        raise AzureBlobSizeMismatchError(
            "Uploaded Azure recording size does not match the submitted file"
        )


async def delete_azure_blob(settings: Settings, storage_path: str) -> None:
    service = _azure_blob_service(settings)
    blob = service.get_blob_client(settings.azure_storage_container, storage_path)
    try:
        await asyncio.to_thread(blob.delete_blob, delete_snapshots="include")
    except ResourceNotFoundError:
        return
    except AzureError as exc:
        raise AzureStorageOperationError("Azure recording cleanup failed") from exc


async def verify_azure_container(settings: Settings) -> None:
    service = _azure_blob_service(settings)
    container = service.get_container_client(settings.azure_storage_container)
    try:
        await asyncio.to_thread(container.get_container_properties)
        if not settings.azure_storage_connection_string:
            now = datetime.now(UTC)
            await asyncio.to_thread(
                service.get_user_delegation_key,
                now - timedelta(minutes=AZURE_CLOCK_SKEW_MINUTES),
                now + timedelta(minutes=AZURE_CLOCK_SKEW_MINUTES),
            )
    except ResourceNotFoundError as exc:
        raise AzureStorageOperationError("Azure recording container was not found") from exc
    except AzureError as exc:
        raise AzureStorageOperationError(
            "Azure recording container or user delegation access is unavailable"
        ) from exc
