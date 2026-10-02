"""Streamlit dashboard: chat over the FastAPI gateway with a live evidence side-panel.

The UI is a thin HTTP client of the B-05 gateway and never imports the orchestrator, so
the gateway health probe and the `USE_MOCKS=false` 501 boundary stay observable here.
"""

from __future__ import annotations

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

from src.telemetry.logger import get_logger
from src.tools.schemas import (
    ChatRequest,
    ChatResponse,
    Decision,
    Evidence,
    Handoff,
    HealthResponse,
)

DEFAULT_API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
REQUEST_TIMEOUT_SECONDS = 30
CUSTOMER_FIXTURES = ("CUST_001", "CUST_002", "CUST_003")
DEFAULT_MESSAGE = "I do not recognize a charge on my card"

logger = get_logger(__name__)


def new_session_id() -> str:
    return f"SESS_{uuid.uuid4().hex[:8].upper()}"


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
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    turn = ChatResponse.model_validate(response.json())
    logger.info(
        "Chat turn received decision=%s intent=%s latency_ms=%s",
        turn.decision,
        turn.intent,
        turn.latency_ms,
        extra={"session_id": turn.session_id, "trace_id": turn.trace_id},
    )
    return turn



def _group_by_source(evidence: list[Evidence]) -> dict[str, list[Evidence]]:
    grouped: dict[str, list[Evidence]] = {}
    for item in evidence:
        grouped.setdefault(item.source.value, []).append(item)
    return grouped


def _render_handoff(handoff: Handoff) -> None:
    st.markdown(f"**Handoff `{handoff.handoff_id}`** — risk_level={handoff.risk_level.value}")
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

    if response.decision is Decision.ESCALATE:
        st.error("Escalated to a human agent: the safety policy detected risk.")
    elif response.decision is Decision.CLARIFY:
        st.warning("Clarification required: not enough grounded context to answer.")
    else:
        st.success("Automated response grounded in retrieved evidence.")

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
    logger.error("Chat turn failed: %s", message, exc_info=True)
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
    st.session_state.customer_id = CUSTOMER_FIXTURES[0]


def main() -> None:
    st.set_page_config(page_title="AI Banking Platform", page_icon="🏦", layout="wide")

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = new_session_id()
    if "last_response" not in st.session_state:
        st.session_state.last_response = None

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
            st.success(f"Gateway OK — v{health.version}, mocks_enabled={health.mocks_enabled}")
        st.divider()
        st.header("Session")
        st.selectbox("Customer", CUSTOMER_FIXTURES, key="customer_id")
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

