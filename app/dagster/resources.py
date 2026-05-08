"""
app/dagster/resources.py
Dagster resources for the photo metadata pipeline.
"""
from __future__ import annotations

from dagster import ConfigurableResource, EnvVar
from sqlalchemy.orm import Session

from app.db.schema import create_tables, get_session as _get_session


class OllamaResource(ConfigurableResource):
    """Connection config for the Ollama inference server."""
    base_url: str = "https://samwise.library.ucdavis.edu/ollama"
    model: str = "qwen2.5vl:32b"
    token: str = ""          # populate via EnvVar("OLLAMA_TOKEN") in definitions.py
    timeout: int = 120

    def apply_to_config(self) -> None:
        """Push values into app.config so the existing VLM backend picks them up."""
        import app.config as cfg
        import app.models.local_vlm as vlm
        cfg.MODEL_BACKEND = "ollama"
        cfg.OLLAMA_BASE_URL = self.base_url
        cfg.OLLAMA_MODEL = self.model
        vlm.MODEL_BACKEND = "ollama"
        # Patch the infer function to include the bearer token
        import json, urllib.request, base64

        def _patched_infer(image_path: str, text_prompt: str) -> str:
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            payload = json.dumps({
                "model": self.model,
                "prompt": text_prompt,
                "images": [b64],
                "stream": False,
            }).encode()
            req = urllib.request.Request(
                f"{self.base_url}/api/generate",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.token}",
                },
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read())
            return data.get("response", "")

        vlm._ollama_infer = _patched_infer


class DatabaseResource(ConfigurableResource):
    """SQLite (or Postgres-ready) database resource."""
    database_url: str = ""   # empty = use default from app.config

    def get_session(self) -> Session:
        if self.database_url:
            import app.config as cfg
            cfg.DATABASE_URL = self.database_url
        create_tables()
        return _get_session()
