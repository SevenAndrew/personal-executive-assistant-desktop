from __future__ import annotations

import os

import keyring

KEYCHAIN_SERVICE = "personal-executive-assistant.openai"
KEYCHAIN_ACCOUNT = "pea-app"


class MissingAPIKeyError(RuntimeError):
    pass


class APIKeyStorageError(RuntimeError):
    pass


def resolve_openai_api_key() -> str:
    environment_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if environment_key:
        return environment_key

    stored_key = keyring.get_password(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT)
    if stored_key and stored_key.strip():
        return stored_key.strip()
    raise MissingAPIKeyError(
        "No OpenAI API key is available. Save it through the application settings."
    )


def has_openai_api_key() -> bool:
    try:
        resolve_openai_api_key()
    except MissingAPIKeyError:
        return False
    return True


def store_openai_api_key(api_key: str) -> None:
    cleaned_key = api_key.strip()
    if len(cleaned_key) < 20:
        raise ValueError("The API key appears to be incomplete.")
    try:
        keyring.set_password(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT, cleaned_key)
    except keyring.errors.KeyringError as exc:
        raise APIKeyStorageError("The API key could not be stored in the macOS Keychain.") from exc
