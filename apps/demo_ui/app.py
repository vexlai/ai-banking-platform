"""Streamlit dashboard: chat over the FastAPI gateway with a live evidence side-panel.

The UI is a thin HTTP client of the B-05 gateway and never imports `src/`, so the
gateway health probe and the `USE_MOCKS=false` 503 boundary stay observable here.
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
from pathlib import Path

# Streamlit only puts the script's own folder on sys.path, so extend it with the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import requests
import streamlit as st
from dotenv import load_dotenv

from contracts import (
    ChatRequest,
    ChatResponse,
    Decision,
    Evidence,
    Handoff,
    HealthResponse,
    Status,
)

load_dotenv(_REPO_ROOT / ".env")

DEFAULT_API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
REQUEST_TIMEOUT_SECONDS = 30
DEFAULT_CUSTOMER_ID = "CLI-EDFKD0MZS5W0"
CUSTOMER_SAMPLES = ("CLI-EDFKD0MZS5W0", "CLI-MOJMZ6YAM8EO", "CLI-9U8NP5E4FAGO")
DEFAULT_MESSAGE = "I do not recognize a charge on my card"

logger = logging.getLogger(__name__)


def new_session_id() -> str:
    return f"SESS_{uuid.uuid4().hex[:8].upper()}"


def _auth_headers() -> dict[str, str]:
    """Forwards the shared gateway key when configured (see `api/security.py`)."""
    api_key = os.getenv("API_KEY")
    return {"X-API-Key": api_key} if api_key else {}


def probe_health(base_url: str) -> HealthResponse | None:
    """Returns the gateway health payload, or None when the gateway is unreachable."""
    try:
        response = requests.get(
            f"{base_url.rstrip('/')}/health", timeout=REQUEST_TIMEOUT_SECONDS
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Health probe failed for %s: %s", base_url, exc)
        return None
    return HealthResponse.model_validate(response.json())


def send_turn(base_url: str, request: ChatRequest) -> ChatResponse:
    """Posts one chat turn and validates the reply against the shared contract."""
    logger.info(
        "Sending chat turn for customer: %s",
        request.customer_id,
        extra={"session_id": request.session_id},
    )
    response = requests.post(
        f"{base_url.rstrip('/')}/v1/chat",
        json=request.model_dump(),
        headers=_auth_headers(),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    turn = ChatResponse.model_validate(response.json())
    logger.info(
        "Chat turn received decision=%s intent=%s llm_used=%s latency_ms=%s",
        turn.decision,
        turn.intent,
        turn.llm_used,
        turn.latency_ms,
        extra={
            "session_id": turn.session_id,
            "trace_id": turn.trace_id,
            "llm_model": turn.llm_model,
        },
    )
    return turn


def _group_by_source(evidence: list[Evidence]) -> dict[str, list[Evidence]]:
    grouped: dict[str, list[Evidence]] = {}
    for item in evidence:
        grouped.setdefault(item.source.value, []).append(item)
    return grouped


def _render_handoff(handoff: Handoff) -> None:
    st.markdown(
        f"**Handoff `{handoff.handoff_id}`** — risk_level={handoff.risk_level.value}"
    )
    st.markdown("Reason")
    st.write(handoff.reason)
    st.markdown("Verified facts")
    for fact in handoff.verified_facts:
        st.markdown(f"- {fact}")
    st.markdown("Recommended actions")
    for action in handoff.recommended_actions:
        st.markdown(f"- {action}")
    st.caption(f"created_at={handoff.created_at.isoformat()}")


def render_evidence_panel(response: ChatResponse | None) -> None:
    st.subheader("Evidence")
    if response is None:
        st.info("No turn yet. Send a message to populate the evidence panel.")
        return

    if response.status is Status.NOT_FOUND:
        st.error("Customer record not found. Please verify the Customer ID.")
    elif response.status is Status.SERVICE_ERROR:
        st.error("Banking data engine offline (503 Service Unavailable)")
    elif response.decision is Decision.ESCALATE:
        st.error("Escalated to a human agent: the safety policy detected risk.")
    elif response.decision is Decision.CLARIFY:
        st.warning("Clarification required: not enough grounded context to answer.")
    elif not response.evidence:
        st.info("No recent transaction history found for this account.")
    else:
        st.success("Automated response grounded in retrieved evidence.")

    source_label = "Verified" if response.evidence else "0 records"
    st.caption(f"Data Source: Live DuckDB ({source_label})")
    model_label = (
        f"Active ({response.llm_model})"
        if response.llm_used and response.llm_model
        else "Active"
        if response.llm_used
        else "Fallback (deterministic)"
    )
    st.caption(f"Model Path: {model_label}")
    metrics = st.columns(3)
    metrics[0].metric("Intent", response.intent.value)
    metrics[1].metric("Latency", f"{response.latency_ms} ms")
    metrics[2].metric("Sources", len(response.evidence))
    st.caption(
        f"trace_id={response.trace_id} | session_id={response.session_id} "
        f"| redacted={response.redacted}"
    )

    if response.handoff is not None:
        with st.expander("Handoff", expanded=True):
            _render_handoff(response.handoff)

    for source, items in _group_by_source(response.evidence).items():
        with st.expander(f"{source} ({len(items)})", expanded=True):
            for item in items:
                st.markdown(f"`{item.source_id}`")
                st.caption(item.snippet)
    st.caption(f"response created_at={response.created_at.isoformat()}")


def _http_error_detail(exc: requests.HTTPError) -> str:
    response = exc.response
    if response is None:
        return str(exc)
    try:
        detail = response.json().get("detail")
    except ValueError:
        detail = None
    return str(detail or response.text or exc)


def _render_failure(exc: Exception, message: str) -> None:
    logger.error("Chat turn failed: %s", message, exc_info=exc)
    st.error(message)
    st.session_state.messages.append({"role": "assistant", "content": message})


def _submit_turn(base_url: str, customer_id: str, prompt: str) -> None:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    request = ChatRequest(
        customer_id=customer_id,
        session_id=st.session_state.session_id,
        message=prompt,
    )
    with st.chat_message("assistant"):
        try:
            with st.spinner("Retrieving evidence and applying policy..."):
                response = send_turn(base_url, request)
        except requests.Timeout as exc:
            _render_failure(exc, f"Gateway timed out after {REQUEST_TIMEOUT_SECONDS}s.")
            return
        except requests.ConnectionError as exc:
            _render_failure(exc, f"Gateway at {base_url} is unreachable.")
            return
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 503:
                _render_failure(
                    exc, "Banking data engine offline (503 Service Unavailable)"
                )
            else:
                _render_failure(exc, _http_error_detail(exc))
            return
        except ValueError as exc:
            _render_failure(exc, f"Gateway returned an unexpected payload: {exc}")
            return
        st.markdown(response.reply)

    st.session_state.messages.append({"role": "assistant", "content": response.reply})
    st.session_state.last_response = response
    st.rerun()


def _reset_session() -> None:
    """Runs as an `on_click` callback, i.e. before the widget keys are re-instantiated."""
    st.session_state.messages = []
    st.session_state.last_response = None
    st.session_state.session_id = new_session_id()
    st.session_state.customer_id = DEFAULT_CUSTOMER_ID


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    st.set_page_config(page_title="AI Banking Platform", page_icon="✨", layout="wide")

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = new_session_id()
    if "last_response" not in st.session_state:
        st.session_state.last_response = None
    if "customer_id" not in st.session_state:
        st.session_state.customer_id = DEFAULT_CUSTOMER_ID

    st.title("AI Banking Platform — Service Copilot")
    st.caption("Evidence-grounded answers with deterministic escalations.")

    with st.sidebar:
        st.header("Connection")
        base_url = st.text_input("API base URL", value=DEFAULT_API_BASE_URL)
        health = probe_health(base_url)
        if health is None:
            st.error(
                f"Gateway unreachable at {base_url}. "
                "Start it with `uvicorn api.main:app --port 8000`."
            )
        else:
            llm_status = health.llm_model if health.llm_enabled else "off"
            st.success(
                f"Gateway OK — v{health.version}, "
                f"mocks_enabled={health.mocks_enabled}, llm={llm_status}"
            )
        st.divider()
        st.header("Session")
        st.text_input(
            "Customer ID",
            key="customer_id",
            help="Enter any valid customer ID from bank_serving.duckdb",
        )
        st.caption("Sample IDs: " + ", ".join(f"`{cid}`" for cid in CUSTOMER_SAMPLES))
        st.text_input("Session id", key="session_id")
        st.button("New session", on_click=_reset_session)

    chat_col, panel_col = st.columns([2, 1], gap="large")
    with chat_col:
        st.subheader("Conversation")
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    with panel_col:
        render_evidence_panel(st.session_state.last_response)

    prompt = st.chat_input(DEFAULT_MESSAGE)
    if prompt:
        _submit_turn(base_url, st.session_state.customer_id, prompt)


if __name__ == "__main__":
    main()
