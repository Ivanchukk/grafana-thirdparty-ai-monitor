"""Generate local credentials inside a Docker volume, never in source or the browser."""
from pathlib import Path
import os
import secrets

root = Path("/run/ai-secrets")
root.mkdir(parents=True, exist_ok=True)
for name in ("admin_password", "proxy_key"):
    path = root/name
    if not path.exists():
        path.write_text(secrets.token_urlsafe(32))
    # Generated development image runs as root; backend uses root as well.
    os.chmod(path, 0o600)
print("Local credentials ready in the ai-secrets volume.")
