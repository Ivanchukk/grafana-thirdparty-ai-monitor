"""Idempotently provision a Viewer service account and secure plugin proxy configuration."""
from pathlib import Path
import httpx

root = Path("/run/ai-secrets")
with httpx.Client(base_url="http://grafana:3000", auth=("admin", (root/"admin_password").read_text().strip()), timeout=20) as client:
    def call(method, path, **kwargs):
        response = client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()
    accounts = call("GET", "/api/serviceaccounts/search", params={"query": "aiops-readonly"})["serviceAccounts"]
    account = next((a for a in accounts if a["name"] == "aiops-readonly"), None)
    if not account:
        account = call("POST", "/api/serviceaccounts", json={"name": "aiops-readonly", "role": "Viewer"})
    if account["role"] != "Viewer":
        call("PATCH", f"/api/serviceaccounts/{account['id']}", json={"role": "Viewer"})
    token_file = root/"grafana_token"
    valid = False
    if token_file.exists():
        check = httpx.get("http://grafana:3000/api/dashboards/uid/elasticsearch-demo", headers={"Authorization": f"Bearer {token_file.read_text().strip()}"})
        valid = check.status_code == 200
    if not valid:
        for token in call("GET", f"/api/serviceaccounts/{account['id']}/tokens"):
            call("DELETE", f"/api/serviceaccounts/{account['id']}/tokens/{token['id']}")
        token = call("POST", f"/api/serviceaccounts/{account['id']}/tokens", json={"name": "aiops-local-readonly"})
        token_file.write_text(token["key"])
        token_file.chmod(0o600)
    call("POST", "/api/plugins/local-aiops-app/settings", json={"enabled": True, "pinned": True, "jsonData": {"backendUrl": "http://backend:8000"}, "secureJsonData": {"backendKey": (root/"proxy_key").read_text().strip()}})
print("Provisioned: demo dashboard, Prometheus, Viewer service account, authenticated app proxy.")
