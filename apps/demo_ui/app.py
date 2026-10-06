"""Streamlit audit cockpit: chat with the orchestrator over HTTP or in-process.

Mode A (Docker Compose) is a thin HTTP client of the FastAPI gateway. Mode B
(Streamlit Community Cloud) has no gateway, so it runs the orchestrator in-process
and downloads the serving artifacts on boot.

This is the single sanctioned file under ``apps/`` allowed to import from ``src/``
(README section 4, Guardrail 1); every other ``apps/**`` module stays HTTP-only.

The cockpit runs strictly against live serving data (``USE_MOCKS=false``): customer
context comes from ``bank_serving.duckdb`` via ``src/tools/context_tools.py`` in
strict mode and semantic transcripts from ``transcripts.faiss`` via
``src/retrieval/vector_store.py``. It never imports ``src/tools/mocks.py``.
"""

from __future__ import annotations

import logging
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any

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
    EvidenceBundle,
    Handoff,
    HealthResponse,
    Status,
)
from src.data.download_serving import ensure_serving_artifacts
from src.tools.errors import CustomerNotFoundError, ServiceUnavailableError

load_dotenv(_REPO_ROOT / ".env")

REQUEST_TIMEOUT_SECONDS = 30
LATENCY_BUDGET_MS = 8000
DEFAULT_CUSTOMER_ID = "CLI-HPVTV49OA07S"
CUSTOM_OPTION = "Custom Customer ID..."
EMPTY_VALUE = "—"

SCENARIOS: tuple[dict[str, str], ...] = (
    {
        "label": "Balance Inquiry",
        "customer_id": "CLI-HPVTV49OA07S",
        "prompt": "What is my current account balance and available funds?",
    },
    {
        "label": "Fraud Escalation",
        "customer_id": "CLI-5FB9Z0SELMWR",
        "prompt": "I do not recognize a charge on my card",
    },
    {
        "label": "Transaction Dispute",
        "customer_id": "CLI-8T0W6XSOJ3DR",
        "prompt": "I want to dispute a transaction on my account",
    },
)
SAMPLE_CUSTOMER_IDS: tuple[str, ...] = tuple(s["customer_id"] for s in SCENARIOS)

_FRAUD_SCORE_PATTERN = re.compile(r"fraud_score=([0-9.]+)")
_SIMILARITY_PATTERN = re.compile(r"similarity=([0-9.]+)")

_BANNER_BY_STATUS = {
    "verified": (st.success, "Account Verified"),
    "not_found": (
        st.warning,
        "Account Unverified: Customer ID not found in database records.",
    ),
    "offline": (
        st.error,
        "System Offline: Banking data engine is currently unreachable.",
    ),
}

_DECISION_PILL: dict[Decision, tuple[str, str, str]] = {
    Decision.RESPOND: (
        "badge-respond",
        "STATE: RESPOND",
        "Answer verified using official banking records.",
    ),
    Decision.CLARIFY: (
        "badge-clarify",
        "STATE: CLARIFY",
        "Additional details required from customer before proceeding.",
    ),
    Decision.ESCALATE: (
        "badge-escalate",
        "STATE: ESCALATE",
        "Security policy triggered. Transferring context to a human banking agent.",
    ),
}

CSS = """
<style>
#MainMenu {visibility: hidden;}
header {visibility: hidden;}
footer {visibility: hidden;}
.block-container {padding-top: 2.2rem; padding-bottom: 2rem;}
.badge {display: inline-block; padding: 4px 12px; border-radius: 999px;
        font-size: 0.82rem; font-weight: 600; letter-spacing: 0.02em;}
.badge-respond {background: #DCFCE7; color: #166534; border: 1px solid #86EFAC;}
.badge-clarify {background: #FEF9C3; color: #854D0E; border: 1px solid #FDE047;}
.badge-escalate {background: #FEE2E2; color: #991B1B; border: 1px solid #FCA5A5;}
.c360-card {background: #0F172A; color: #E2E8F0; border-radius: 12px;
            padding: 18px 20px; margin-bottom: 12px; border: 1px solid #1E293B;}
.c360-title {color: #F8FAFC; font-size: 0.95rem; font-weight: 700;
             text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 10px;}
.c360-row {display: flex; justify-content: space-between; gap: 12px;
           padding: 7px 0; border-bottom: 1px solid rgba(148, 163, 184, 0.18);}
.c360-row:last-child {border-bottom: none;}
.c360-label {color: #94A3B8; font-size: 0.78rem; text-transform: uppercase;
             letter-spacing: 0.04em;}
.c360-value {font-weight: 600; text-align: right;}
</style>
"""

logger = logging.getLogger(__name__)


def _get_config(key: str, default: str = "") -> str:
    value = os.getenv(key)
    if value:
        return value
    try:
        if hasattr(st, "secrets") and key in st.secrets:
            return st.secrets[key]
    except Exception:  # noqa: BLE001 - Streamlit secrets are optional
        logger.debug("Streamlit secret unavailable: %s", key)
    return default


API_BASE_URL = _get_config("API_BASE_URL")


@st.cache_resource
def get_engine():
    ensure_serving_artifacts(
        duckdb_url=_get_config("SERVING_DUCKDB_URL"),
        faiss_url=_get_config("SERVING_FAISS_URL"),
        faiss_meta_url=_get_config("SERVING_FAISS_META_URL"),
    )
    use_mocks = _get_config("USE_MOCKS", "false").strip().lower() == "true"

    from src.orchestrator.engine import OrchestratorEngine
    from src.retrieval import vector_store

    return OrchestratorEngine(
        use_mocks=use_mocks,
        transcript_search=None if use_mocks else vector_store.search,
    )


def new_session_id() -> str:
    return f"SESS_{uuid.uuid4().hex[:8].upper()}"


def _auth_headers() -> dict[str, str]:
    api_key = os.getenv("API_KEY")
    return {"X-API-Key": api_key} if api_key else {}


def probe_health(base_url: str) -> HealthResponse | None:
    try:
        response = requests.get(
            f"{base_url.rstrip('/')}/health", timeout=REQUEST_TIMEOUT_SECONDS
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Health probe failed for %s: %s", base_url, exc)
        return None
    return HealthResponse.model_validate(response.json())


def _active_base_url() -> str:
    return (st.session_state.get("api_base_url", API_BASE_URL) or "").strip()


def execute_chat_query(customer_id: str, message: str) -> dict:
    base_url = _active_base_url()
    request = ChatRequest(
        customer_id=customer_id,
        session_id=st.session_state.get("session_id", "default_session"),
        message=message,
    )
    logger.info("Dispatching chat turn for customer: %s", customer_id)
    if base_url:
        response = requests.post(
            f"{base_url.rstrip('/')}/v1/chat",
            json=request.model_dump(),
            headers=_auth_headers(),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    else:
        payload = get_engine().process_turn(request).model_dump()

    turn = ChatResponse.model_validate(payload)
    logger.info("Chat turn resolved with decision: %s", turn.decision)
    logger.info("Chat turn latency_ms: %s", turn.latency_ms)
    return payload


def load_customer_context(customer_id: str) -> tuple[EvidenceBundle | None, str]:
    """Returns ``(bundle, status)`` where status is verified / not_found / offline."""
    if not customer_id:
        return None, "not_found"

    base_url = _active_base_url()
    if base_url:
        try:
            response = requests.get(
                f"{base_url.rstrip('/')}/v1/customers/{customer_id}/context",
                headers=_auth_headers(),
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            logger.warning("Context fetch failed for %s: %s", customer_id, exc)
            return None, "offline"
        if response.status_code == 404:
            return None, "not_found"
        if response.status_code >= 500:
            return None, "offline"
        try:
            response.raise_for_status()
            return EvidenceBundle.model_validate(response.json()), "verified"
        except (requests.HTTPError, ValueError) as exc:
            logger.warning("Invalid context payload for %s: %s", customer_id, exc)
            return None, "offline"

    from src.tools import context_tools

    try:
        return context_tools.get_context(customer_id), "verified"
    except CustomerNotFoundError:
        logger.warning("Context not found for customer: %s", customer_id)
        return None, "not_found"
    except ServiceUnavailableError as exc:
        logger.error("Serving data unavailable: %s", exc.reason)
        return None, "offline"
    except Exception as exc:  # noqa: BLE001 - never crash the panel on a context read
        logger.error("Unexpected context failure: %s", exc)
        return None, "offline"


def _ensure_context(customer_id: str) -> tuple[EvidenceBundle | None, str]:
    if not customer_id:
        return None, "not_found"
    if st.session_state.get("customer_context_id") == customer_id:
        return (
            st.session_state.get("customer_context"),
            st.session_state.get("customer_context_status", "offline"),
        )
    bundle, status = load_customer_context(customer_id)
    st.session_state.customer_context = bundle
    st.session_state.customer_context_id = customer_id
    st.session_state.customer_context_status = status
    return bundle, status


def _clear_conversation() -> None:
    st.session_state.session_id = new_session_id()
    st.session_state.messages = []
    st.session_state.last_response = None
    st.session_state.customer_context = None
    st.session_state.customer_context_id = None
    st.session_state.customer_context_status = "offline"


def _apply_scenario(scenario: dict[str, str]) -> None:
    _clear_conversation()
    st.session_state.customer_id = scenario["customer_id"]
    st.session_state.customer_select = scenario["customer_id"]
    st.session_state.pending_prompt = scenario["prompt"]


def _resolve_customer_selector() -> None:
    options = [*SAMPLE_CUSTOMER_IDS, CUSTOM_OPTION]
    if st.session_state.get("customer_select") not in options:
        current = st.session_state.get("customer_id", DEFAULT_CUSTOMER_ID)
        st.session_state.customer_select = (
            current if current in options else DEFAULT_CUSTOMER_ID
        )
    choice = st.selectbox(
        "Customer ID",
        options,
        key="customer_select",
        help="Live personas read from bank_serving.duckdb (customer_360_view).",
    )
    if choice == CUSTOM_OPTION:
        custom = st.text_input(
            "Custom Customer ID",
            key="custom_customer_id",
            placeholder="CLI-XXXXXXXXXXXX",
        )
        st.session_state.customer_id = custom.strip()
    else:
        st.session_state.customer_id = choice


def _render_sidebar() -> None:
    with st.sidebar:
        st.header("Connection")
        base_url = st.text_input(
            "API base URL",
            key="api_base_url",
            help="Leave blank to run in-process (Streamlit Community Cloud).",
        )
        if not base_url:
            st.info("In-process mode: the orchestrator runs inside this process.")
        else:
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
        st.header("Customer")
        _resolve_customer_selector()
        st.caption(
            "Live personas from `bank_serving.duckdb`: "
            + ", ".join(f"`{cid}`" for cid in SAMPLE_CUSTOMER_IDS)
        )
        st.divider()
        st.header("Session")
        st.text_input("Session id", key="session_id")
        st.button("New session", on_click=_reset_session)


def _render_scenario_bar() -> None:
    st.markdown("##### One-click Test Scenarios")
    columns = st.columns(len(SCENARIOS))
    for column, scenario in zip(columns, SCENARIOS, strict=True):
        column.button(
            f"{scenario['label']} ({scenario['customer_id']})",
            key=f"scenario_{scenario['customer_id']}",
            help=scenario["prompt"],
            on_click=_apply_scenario,
            args=(scenario,),
            use_container_width=True,
        )


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


def _fraud_band(score: float) -> tuple[str, str]:
    if score >= 0.80:
        return "High", "badge-escalate"
    if score >= 0.50:
        return "Medium", "badge-clarify"
    return "Low", "badge-respond"


def _profile_from_evidence(evidence: list[Evidence]) -> dict[str, Any]:
    profile: dict[str, Any] = {"full_name": None, "segment": None, "country": None}
    for item in evidence:
        if item.source.value == "customer_360_view":
            parts = [part.strip() for part in item.snippet.split("|")]
            if parts and parts[0]:
                profile["full_name"] = parts[0]
            for part in parts[1:]:
                key, _, value = part.partition("=")
                if key in {"segment", "country"}:
                    profile[key] = value.strip()
        elif item.source.value == "recent_transactions":
            match = _FRAUD_SCORE_PATTERN.search(item.snippet)
            if match:
                score = float(match.group(1))
                profile["fraud_score"] = max(
                    float(profile.get("fraud_score") or 0.0), score
                )
    return profile


def _customer_360_fields(
    customer_id: str,
    bundle: EvidenceBundle | None,
    response: ChatResponse | None,
) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "customer_id": customer_id or EMPTY_VALUE,
        "full_name": EMPTY_VALUE,
        "segment": EMPTY_VALUE,
        "country": EMPTY_VALUE,
        "credit_limit": EMPTY_VALUE,
        "fraud_score": None,
    }
    if bundle is not None:
        c360 = bundle.customer_360
        fields["customer_id"] = c360.customer_id
        fields["full_name"] = c360.full_name
        fields["segment"] = c360.segment
        fields["country"] = c360.country
        fields["credit_limit"] = f"{c360.credit_limit:,.2f} {c360.currency}"
        if bundle.recent_transactions:
            fields["fraud_score"] = max(
                txn.fraud_score for txn in bundle.recent_transactions
            )
    elif response is not None:
        profile = _profile_from_evidence(response.evidence)
        fields["full_name"] = profile.get("full_name") or fields["full_name"]
        fields["segment"] = profile.get("segment") or fields["segment"]
        fields["country"] = profile.get("country") or fields["country"]
        fields["fraud_score"] = profile.get("fraud_score")
    return fields


def render_customer_360(
    customer_id: str,
    bundle: EvidenceBundle | None,
    ctx_status: str,
    response: ChatResponse | None,
) -> None:
    st.markdown("##### Customer 360")
    banner, message = _BANNER_BY_STATUS[ctx_status]
    banner(message)

    fields = _customer_360_fields(customer_id, bundle, response)
    fraud = fields["fraud_score"]
    if fraud is None:
        fraud_html = f'<span class="c360-value">{EMPTY_VALUE}</span>'
    else:
        label, badge = _fraud_band(float(fraud))
        fraud_html = (
            f'<span class="c360-value">{float(fraud):.2f} '
            f'<span class="badge {badge}">{label}</span></span>'
        )

    rows = (
        ("Customer ID", fields["customer_id"]),
        ("Name", fields["full_name"]),
        ("Segment", fields["segment"]),
        ("Country", fields["country"]),
        ("Credit Limit", fields["credit_limit"]),
    )
    body = "".join(
        f'<div class="c360-row"><span class="c360-label">{label}</span>'
        f'<span class="c360-value">{value}</span></div>'
        for label, value in rows
    )
    body += (
        '<div class="c360-row"><span class="c360-label">Fraud Risk Score</span>'
        f"{fraud_html}</div>"
    )
    st.markdown(
        '<div class="c360-card"><div class="c360-title">Customer 360</div>'
        f"{body}</div>",
        unsafe_allow_html=True,
    )


def render_policy_pill(response: ChatResponse | None) -> None:
    st.markdown("##### Policy Decision")
    if response is None:
        st.caption("Awaiting the first turn to resolve a policy decision.")
        return
    css_class, badge_text, explanation = _DECISION_PILL[response.decision]
    st.markdown(
        f'<span class="badge {css_class}">{badge_text}</span>',
        unsafe_allow_html=True,
    )
    st.caption(explanation)
    if response.status is Status.NOT_FOUND:
        st.caption("Account Unverified: Customer ID not found in database records.")
    elif response.status is Status.SERVICE_ERROR:
        st.caption("System Offline: Banking data engine is currently unreachable.")


def _relational_records(evidence: list[Evidence]) -> list[dict[str, str]]:
    return [
        {
            "source": item.source.value,
            "source_id": item.source_id,
            "snippet": item.snippet,
        }
        for item in evidence
        if item.source.value != "similar_transcripts"
    ]


def _transcript_records(evidence: list[Evidence]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in evidence:
        if item.source.value != "similar_transcripts":
            continue
        match = _SIMILARITY_PATTERN.search(item.snippet)
        records.append(
            {
                "transcript_id": item.source_id,
                "similarity": float(match.group(1)) if match else None,
                "summary": item.snippet,
            }
        )
    return records


def render_evidence(response: ChatResponse | None) -> None:
    st.markdown("##### Grounding Evidence")
    if response is None:
        st.caption("Evidence appears here once a turn has been processed.")
        return

    relational = _relational_records(response.evidence)
    transcripts = _transcript_records(response.evidence)

    with st.expander(f"DuckDB Relational Evidence ({len(relational)})"):
        if relational:
            st.json(relational)
        else:
            st.caption("No relational records retrieved for this turn.")

    with st.expander(f"FAISS Transcript Retrieval ({len(transcripts)})"):
        if not transcripts:
            st.caption("No semantic transcript matches for this turn.")
        for record in transcripts:
            similarity = record["similarity"]
            badge = (
                f'<span class="badge badge-respond">score {similarity:.2f}</span>'
                if similarity is not None
                else '<span class="badge badge-clarify">score n/a</span>'
            )
            st.markdown(f"`{record['transcript_id']}` {badge}", unsafe_allow_html=True)
            st.caption(record["summary"])

    if response.handoff is not None:
        with st.expander("Human Handoff", expanded=True):
            _render_handoff(response.handoff)


def render_audit_panel(
    customer_id: str,
    bundle: EvidenceBundle | None,
    ctx_status: str,
    response: ChatResponse | None,
) -> None:
    render_customer_360(customer_id, bundle, ctx_status, response)
    render_policy_pill(response)
    render_evidence(response)


def _render_latency_badge(latency_ms: float) -> None:
    css_class = "badge-respond" if latency_ms <= LATENCY_BUDGET_MS else "badge-escalate"
    st.markdown(
        f'<span class="badge {css_class}">Latency: {latency_ms:.0f} ms</span>',
        unsafe_allow_html=True,
    )
    st.caption(f"P95 end-to-end target < {LATENCY_BUDGET_MS} ms")


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


def _submit_turn(customer_id: str, prompt: str) -> None:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.status("Executing orchestration pipeline…", expanded=True) as status:
            st.write("[duckdb] Querying customer 360 profile...")
            _ensure_context(customer_id)
            st.write("[duckdb] Fetching recent account activity...")
            st.write("[faiss] Searching transcript embeddings...")
            try:
                payload = execute_chat_query(customer_id, prompt)
            except requests.Timeout as exc:
                status.update(label="Request timed out", state="error")
                _render_failure(
                    exc, f"Request timed out after {REQUEST_TIMEOUT_SECONDS}s."
                )
                return
            except requests.ConnectionError as exc:
                status.update(label="Gateway unreachable", state="error")
                _render_failure(exc, f"Gateway at {_active_base_url()} is unreachable.")
                return
            except requests.HTTPError as exc:
                status.update(label="Gateway error", state="error")
                if exc.response is not None and exc.response.status_code == 503:
                    _render_failure(
                        exc, "Banking data engine offline (503 Service Unavailable)"
                    )
                else:
                    _render_failure(exc, _http_error_detail(exc))
                return
            except ValueError as exc:
                status.update(label="Invalid payload", state="error")
                _render_failure(exc, f"Gateway returned an unexpected payload: {exc}")
                return
            except Exception as exc:  # noqa: BLE001 - in-process engine failures
                status.update(label="Engine error", state="error")
                _render_failure(exc, f"Orchestrator engine failed: {exc}")
                return
            st.write("[policy] Evaluating guardrails & fraud risk...")
            response = ChatResponse.model_validate(payload)
            status.update(
                label="Pipeline execution complete",
                state="complete",
                expanded=False,
            )
        st.markdown(response.reply)
        _render_latency_badge(response.latency_ms)

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": response.reply,
            "latency_ms": response.latency_ms,
        }
    )
    st.session_state.last_response = response
    st.rerun()


def _reset_session() -> None:
    _clear_conversation()
    st.session_state.customer_id = DEFAULT_CUSTOMER_ID
    st.session_state.customer_select = DEFAULT_CUSTOMER_ID
    st.session_state.pop("pending_prompt", None)


def _active_customer() -> str:
    return st.session_state.get("customer_id", DEFAULT_CUSTOMER_ID)


def _init_session_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = new_session_id()
    if "last_response" not in st.session_state:
        st.session_state.last_response = None
    if "customer_id" not in st.session_state:
        st.session_state.customer_id = DEFAULT_CUSTOMER_ID
    if "customer_context" not in st.session_state:
        st.session_state.customer_context = None
    if "customer_context_id" not in st.session_state:
        st.session_state.customer_context_id = None
    if "customer_context_status" not in st.session_state:
        st.session_state.customer_context_status = "offline"
    if "api_base_url" not in st.session_state:
        st.session_state.api_base_url = API_BASE_URL


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    st.set_page_config(
        page_title="AI Banking Platform",
        page_icon="✨",
        layout="wide",
    )
    st.markdown(CSS, unsafe_allow_html=True)
    _init_session_state()

    _render_sidebar()

    st.title("AI Banking Platform")
    st.caption(
        "Evidence-grounded service orchestration with deterministic escalations."
    )

    _render_scenario_bar()

    customer_id = _active_customer()
    bundle, ctx_status = _ensure_context(customer_id)

    chat_col, audit_col = st.columns([3, 2], gap="large")
    with chat_col:
        st.subheader("Conversation")
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                if message.get("latency_ms") is not None:
                    _render_latency_badge(message["latency_ms"])
        typed = st.chat_input("Ask about a balance, transaction, or dispute…")
        pending = st.session_state.pop("pending_prompt", None)
        prompt = typed or pending
        if prompt and customer_id:
            _submit_turn(customer_id, prompt)
        elif prompt:
            st.warning("Provide a valid Customer ID before sending a message.")
    with audit_col:
        render_audit_panel(
            customer_id, bundle, ctx_status, st.session_state.last_response
        )


if __name__ == "__main__":
    main()
