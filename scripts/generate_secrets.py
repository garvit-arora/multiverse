"""Generate safe local development secrets and Ed25519 Passport signing keys."""
from __future__ import annotations

import base64
import secrets
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parent.parent
KEYS_DIR = ROOT / "infra" / "keys"


def generate_ed25519_keypair(priv_path: Path, pub_path: Path) -> None:
    if priv_path.exists() and pub_path.exists():
        print(f"Ed25519 keypair already exists at {priv_path}")
        return
    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    priv_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    priv_path.write_bytes(priv_bytes)
    pub_path.write_bytes(pub_bytes)
    print(f"Generated Ed25519 keypair: {priv_path}, {pub_path}")


def main() -> None:
    priv_path = KEYS_DIR / "passport_ed25519.pem"
    pub_path = KEYS_DIR / "passport_ed25519.pub.pem"
    generate_ed25519_keypair(priv_path, pub_path)

    env_path = ROOT / ".env"
    if not env_path.exists():
        example_path = ROOT / ".env.example"
        content = example_path.read_text(encoding="utf-8")
        session_secret = secrets.token_urlsafe(32)
        auth_secret = secrets.token_urlsafe(32)
        enc_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")
        mysql_pw = secrets.token_urlsafe(16)
        mysql_root = secrets.token_urlsafe(16)
        flagsmith_db_pw = secrets.token_urlsafe(16)
        flagsmith_secret = secrets.token_urlsafe(32)

        replacements = {
            "SESSION_SECRET=": f"SESSION_SECRET={session_secret}",
            "AUTH_SECRET=": f"AUTH_SECRET={auth_secret}",
            "CREDENTIAL_ENCRYPTION_KEY=": f"CREDENTIAL_ENCRYPTION_KEY={enc_key}",
            "MYSQL_PASSWORD=": f"MYSQL_PASSWORD={mysql_pw}",
            "MYSQL_ROOT_PASSWORD=": f"MYSQL_ROOT_PASSWORD={mysql_root}",
            "DATABASE_URL=mysql+pymysql://multiverse:CHANGE_ME@mysql:3306/multiverse": (
                f"DATABASE_URL=mysql+pymysql://multiverse:{mysql_pw}@mysql:3306/multiverse"
            ),
            "FLAGSMITH_DB_PASSWORD=": f"FLAGSMITH_DB_PASSWORD={flagsmith_db_pw}",
            "FLAGSMITH_SECRET_KEY=": f"FLAGSMITH_SECRET_KEY={flagsmith_secret}",
        }
        for k, v in replacements.items():
            content = content.replace(k, v, 1)
        env_path.write_text(content, encoding="utf-8")
        print(f"Created {env_path} with generated local development secrets.")
    else:
        print(f"{env_path} already exists; not overwriting.")


if __name__ == "__main__":
    main()
