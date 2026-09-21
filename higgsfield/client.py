"""
Minimal Higgsfield pay-as-you-go API client.

Auth: Higgsfield's REST API authenticates with two header values:
    hf-api-key: <HIGGSFIELD_API_KEY>
    hf-secret:  <HIGGSFIELD_API_SECRET>
(Confirmed from the API launch docs. If your account only issues a single
key, put it in HIGGSFIELD_API_KEY and leave the secret blank.)

IMPORTANT — VERIFY BEFORE FIRST RUN
-----------------------------------
The exact endpoint PATHS and request/response JSON shapes below are the one
thing I could not confirm from inside the build environment (docs.higgsfield.ai
is network-blocked here). Open https://docs.higgsfield.ai, then sanity-check
the four ALL-CAPS constants in the CONFIG block against the quickstart. Once
those match, everything else works unchanged.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────── CONFIG — VERIFY THESE ───────────────────────────
BASE_URL = os.getenv("HIGGSFIELD_API_URL", "https://platform.higgsfield.ai").rstrip("/")

# Endpoint paths (relative to BASE_URL). Verify against docs.higgsfield.ai.
SUBMIT_PATH = "/v1/generations"          # POST: create a generation job
STATUS_PATH = "/v1/generations/{job_id}" # GET:  poll job status
BALANCE_PATH = "/v1/balance"             # GET:  current USD balance

# Where in the status JSON the cost / output / state live. Verify + adjust.
STATUS_FIELD = "status"                  # e.g. "queued" | "processing" | "completed" | "failed"
DONE_STATES = {"completed", "succeeded", "success", "done"}
FAIL_STATES = {"failed", "error", "canceled", "cancelled"}
COST_FIELD = "cost"                      # USD charged for the job
OUTPUT_FIELD = "results"                 # list of output URLs (or nested {url})
# ─────────────────────────────────────────────────────────────────────────────


class HiggsfieldError(RuntimeError):
    pass


@dataclass
class GenerationResult:
    job_id: str
    status: str
    cost_usd: float | None
    outputs: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


class HiggsfieldClient:
    def __init__(self, api_key: str | None = None, api_secret: str | None = None):
        self.api_key = api_key or os.getenv("HIGGSFIELD_API_KEY", "")
        self.api_secret = api_secret or os.getenv("HIGGSFIELD_API_SECRET", "")
        if not self.api_key:
            raise HiggsfieldError(
                "HIGGSFIELD_API_KEY is empty. Add it to .env "
                "(see README_HIGGSFIELD.md for how to get one)."
            )
        self.session = requests.Session()
        self.session.headers.update(
            {
                "hf-api-key": self.api_key,
                "hf-secret": self.api_secret,
                "Content-Type": "application/json",
            }
        )

    # ── low-level ────────────────────────────────────────────────────────────
    def _url(self, path: str) -> str:
        return f"{BASE_URL}{path}"

    def _raise(self, resp: requests.Response) -> dict[str, Any]:
        if not resp.ok:
            raise HiggsfieldError(f"{resp.status_code} {resp.request.method} "
                                  f"{resp.url}\n{resp.text[:500]}")
        return resp.json() if resp.text else {}

    # ── public ───────────────────────────────────────────────────────────────
    def balance(self) -> dict[str, Any]:
        """Current pay-as-you-go USD balance."""
        return self._raise(self.session.get(self._url(BALANCE_PATH), timeout=30))

    def submit(self, model: str, **params: Any) -> str:
        """Create a generation job; returns its job id."""
        payload = {"model": model, **params}
        data = self._raise(self.session.post(self._url(SUBMIT_PATH),
                                             json=payload, timeout=60))
        job_id = data.get("id") or data.get("job_id") or data.get("generation_id")
        if not job_id:
            raise HiggsfieldError(f"No job id in submit response: {data}")
        return job_id

    def poll(self, job_id: str, *, interval: float = 4.0,
             timeout: float = 900.0) -> GenerationResult:
        """Poll a job until it reaches a terminal state (or timeout)."""
        deadline = time.time() + timeout
        while True:
            data = self._raise(
                self.session.get(self._url(STATUS_PATH.format(job_id=job_id)),
                                 timeout=30)
            )
            state = str(data.get(STATUS_FIELD, "")).lower()
            if state in DONE_STATES or state in FAIL_STATES:
                return GenerationResult(
                    job_id=job_id,
                    status=state,
                    cost_usd=_extract_cost(data),
                    outputs=_extract_outputs(data),
                    raw=data,
                )
            if time.time() > deadline:
                raise HiggsfieldError(f"Job {job_id} timed out in state '{state}'")
            time.sleep(interval)

    def generate(self, model: str, *, poll: bool = True, **params: Any) -> GenerationResult:
        """Submit and (by default) wait for the result."""
        job_id = self.submit(model, **params)
        if not poll:
            return GenerationResult(job_id=job_id, status="submitted", cost_usd=None)
        return self.poll(job_id)


def _extract_cost(data: dict[str, Any]) -> float | None:
    val = data.get(COST_FIELD)
    if isinstance(val, dict):  # e.g. {"amount": 0.2, "currency": "USD"}
        val = val.get("amount")
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def _extract_outputs(data: dict[str, Any]) -> list[str]:
    out = data.get(OUTPUT_FIELD) or data.get("output") or []
    urls: list[str] = []
    if isinstance(out, str):
        return [out]
    for item in out if isinstance(out, list) else [out]:
        if isinstance(item, str):
            urls.append(item)
        elif isinstance(item, dict):
            u = item.get("url") or item.get("output_url") or item.get("uri")
            if u:
                urls.append(u)
    return urls
