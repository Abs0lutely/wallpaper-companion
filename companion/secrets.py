"""Reuse the OS credential store; never put API keys into exported JSON."""
import keyring

SERVICE = "WallpaperCompanion.TTS"


def read_secret(provider):
    return keyring.get_password(SERVICE, provider) or ""


def write_secret(provider, value):
    if value:
        keyring.set_password(SERVICE, provider, value)
    else:
        try:
            keyring.delete_password(SERVICE, provider)
        except keyring.errors.PasswordDeleteError:
            pass
