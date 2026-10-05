"""System prompt, function tool definitions, and grounded reply templates.

Static orchestration resources only; the engine owns the behaviour that consumes them.
"""

from __future__ import annotations

from typing import Any

from contracts import Intent, SourceTool

SYSTEM_PROMPT = (
    "You are the AI banking service orchestrator. Every operational statement you make "
    "about balances, transactions, journeys, or cases must be grounded in evidence returned "
    "by the context tools; never guess a financial fact. PII must never appear in your text. "
    "You may not move money, execute transfers, or approve credit/eligibility. When the policy "
    "engine escalates, stop answering and defer to the structured human handoff."
)

TOOL_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "type": "function",
        "function": {
            "name": SourceTool.CUSTOMER_360.value,
            "description": "Compact customer profile: segment, country, products, and credit limit.",
            "parameters": {
                "type": "object",
                "properties": {"customer_id": {"type": "string"}},
                "required": ["customer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": SourceTool.RECENT_TRANSACTIONS.value,
            "description": "Recent transactions with normalized status and fraud scores.",
            "parameters": {
                "type": "object",
                "properties": {"customer_id": {"type": "string"}},
                "required": ["customer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": SourceTool.JOURNEY_SUMMARY.value,
            "description": "Digital journey summary for the active session: errors and abandoned forms.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "session_id": {"type": "string"},
                },
                "required": ["customer_id", "session_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": SourceTool.INTERACTION_HISTORY.value,
            "description": "Recent support interactions across all channels.",
            "parameters": {
                "type": "object",
                "properties": {"customer_id": {"type": "string"}},
                "required": ["customer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": SourceTool.SIMILAR_TRANSCRIPTS.value,
            "description": "Semantically similar past call transcripts.",
            "parameters": {
                "type": "object",
                "properties": {"customer_id": {"type": "string"}},
                "required": ["customer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": SourceTool.OPEN_CASES.value,
            "description": "Open cases with severity and SLA breach / repeat complaint flags.",
            "parameters": {
                "type": "object",
                "properties": {"customer_id": {"type": "string"}},
                "required": ["customer_id"],
            },
        },
    },
)

INTENT_KEYWORDS: tuple[tuple[Intent, tuple[str, ...]], ...] = (
    (
        Intent.FRAUD_REPORT,
        (
            "fraud",
            "unauthorized",
            "unrecognized",
            "stolen",
            "scam",
            "didn't make",
            "did not make",
        ),
    ),
    (Intent.CARD_ISSUE, ("card", "declined", "blocked", "replacement", "chip", "pin")),
    (
        Intent.COMPLAINT,
        (
            "complaint",
            "angry",
            "upset",
            "dissatisfied",
            "unacceptable",
            "manager",
            "escalate",
        ),
    ),
    (Intent.BALANCE_INQUIRY, ("balance", "available", "funds", "how much")),
    (
        Intent.TRANSACTION_STATUS,
        ("transaction", "transfer", "payment", "pending", "posted", "status"),
    ),
)

RESPOND_OPENERS: dict[Intent, str] = {
    Intent.BALANCE_INQUIRY: "I reviewed your account profile and recent activity",
    Intent.TRANSACTION_STATUS: "I checked your recent transactions",
    Intent.CARD_ISSUE: "I reviewed your card products and recent activity",
    Intent.FRAUD_REPORT: "I flagged the unrecognized activity",
    Intent.COMPLAINT: "I reviewed your recent interactions",
    Intent.UNKNOWN: "I reviewed your account context",
}

RESPOND_TEMPLATE = (
    "{opener} for {name}. This answer is grounded in {count} verified source(s) [{sources}]. "
    "{facts}"
)

FACTS_TEMPLATE = (
    "Profile: segment {segment}, country {country}, products {products}. "
    "Session {session_id}: {errors} error(s) and {abandoned} abandoned form(s) in the last "
    "{window_hours}h."
)

ESCALATION_REPLY = (
    "This case has been escalated to a human agent (handoff {handoff_id}) because the safety "
    "policy detected risk. I will not take any financial action; an agent will follow up."
)

CLARIFICATION_REPLY = (
    "I could not retrieve enough grounded context to answer safely. Please confirm your "
    "customer and session details so I can retry with verified evidence."
)

NOT_FOUND_REPLY = (
    "No active account record was found for Customer ID '{customer_id}'. "
    "Please verify your customer number."
)

EMPTY_TRANSACTIONS_REPLY = (
    "I checked your account records and confirmed there are no posted transactions in the "
    "last 30 days. This answer is grounded in {count} verified source(s) [{sources}]. {facts}"
)
