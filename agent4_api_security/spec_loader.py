"""
spec_loader.py
===============
Loads an OpenAPI/Swagger spec from a URL (live mode) or a bundled local
file (mock mode) and flattens it into a list of endpoint definitions the
rest of the agent can iterate over.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict

sys.path.append(str(Path(__file__).resolve().parent.parent))
from shared.config import config

MOCK_SPEC_PATH = Path(__file__).resolve().parent / "mock_data" / "sample_swagger.json"


def load_spec(swagger_url: str = None) -> dict:
    if swagger_url and swagger_url.startswith("http"):
        import requests

        resp = requests.get(swagger_url, timeout=15)
        resp.raise_for_status()
        return resp.json()

    print(f"[spec_loader] Using local spec file: {swagger_url or MOCK_SPEC_PATH}")
    path = Path(swagger_url) if swagger_url else MOCK_SPEC_PATH
    return json.loads(path.read_text())


def flatten_endpoints(spec: dict) -> List[Dict]:
    endpoints = []
    base_url = spec.get("servers", [{}])[0].get("url", "")

    for path, methods in spec.get("paths", {}).items():
        for method, details in methods.items():
            if method.lower() not in ("get", "post", "put", "delete", "patch"):
                continue
            body_schema = None
            content = details.get("requestBody", {}).get("content", {})
            if "application/json" in content:
                body_schema = content["application/json"].get("schema", {})

            endpoints.append({
                "path": path,
                "method": method.upper(),
                "base_url": base_url,
                "summary": details.get("summary", ""),
                "parameters": details.get("parameters", []),
                "body_schema": body_schema,
                "requires_auth": bool(details.get("security")),
                "expected_responses": list(details.get("responses", {}).keys()),
            })
    return endpoints
