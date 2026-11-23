import base64
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

kind = sys.argv[1]
status = sys.argv[2]
base_url = os.getenv("OO_URL", "").rstrip("/")
if not base_url:
    print("OO_URL no está configurado; se omite la transmisión a OpenObserve.")
    sys.exit(0)

payload = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "event": f"ci_{kind}",
    "status": status,
    "commit": os.getenv("GITHUB_SHA", "local"),
    "branch": os.getenv("GITHUB_REF_NAME", "local"),
    "actor": os.getenv("GITHUB_ACTOR", "local"),
    "run_id": os.getenv("GITHUB_RUN_ID", "local"),
    "repository": os.getenv("GITHUB_REPOSITORY", "local"),
}
credentials = f"{os.getenv('OO_USER', '')}:{os.getenv('OO_PASSWORD', '')}".encode()
request = urllib.request.Request(
    f"{base_url}/api/default/ci_pipeline/_json",
    data=json.dumps(payload).encode(),
    headers={"Authorization": "Basic " + base64.b64encode(credentials).decode(), "Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(request, timeout=10) as response:
        print(f"OpenObserve recibió {kind}: HTTP {response.status}")
except Exception as exc:
    print(f"No se pudo enviar el evento a OpenObserve: {exc}")
    if os.getenv("OO_REQUIRED", "false").lower() == "true":
        raise
