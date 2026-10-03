"""Deterministic application boundary. Credential verification is an injected host port."""

from datetime import datetime, timedelta, timezone
from functools import wraps
from uuid import uuid4

from pydantic import ValidationError

from contracts.disputes import (
    VERSION,
    Case,
    EvidenceBundle,
    HandoffPackage,
    Intake,
    Principal,
    Search,
    SearchResult,
    Selection,
    State,
    Transaction,
    aware,
)
from src.cases.state_machine import require_action
from src.cases.store import CaseStore, Conflict, Rejected, fingerprint
from src.cases.tools import MAX_CANDIDATES, TransactionTools, eligible
from src.evaluation.baseline_intake_parser import extract

LIMITATIONS = (
    "Event-time filtering is enforced; historical ingestion/revision availability is not certified.",
    "Recorded transaction status is snapshot evidence, not a fraud verdict.",
    "Customer selection is not observed complaint-to-transaction ground truth.",
    "No external policy, financial decision, or external human-queue acceptance is implied.",
)


def updated(case, **values):
    return Case.model_validate({**case.model_dump(), **values})


def audited_request(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except (Rejected, ValidationError) as error:
            reason = (
                "INVALID_CONTRACT" if isinstance(error, ValidationError) else str(error)
            )
            self.store.record_rejection(method.__name__, reason, aware(self.clock()))
            raise

    return call


class CaseService:
    """No HTTP/auth implementation: host must supply a genuine credential verifier.

    resolve_principal(opaque_credential) must validate issuer/signature/session revocation.
    This service ALSO enforces expiry, required scopes and customer isolation each call.
    A demo resolver is acceptable only in the explicitly synthetic offline demo.
    """

    def __init__(
        self,
        store: CaseStore,
        tools: TransactionTools,
        resolve_principal,
        clock=lambda: datetime.now(timezone.utc),
    ):
        self.store = store
        self.tools = tools
        self.resolve_principal = resolve_principal
        self.clock = clock

    def _principal(self, credential, scope):
        now = aware(self.clock())
        try:
            principal = self.resolve_principal(credential)
        except Exception:  # noqa: BLE001 - verifier outages must fail closed without exposing secrets
            raise Rejected("AUTH_DENIED") from None
        if not isinstance(principal, Principal):
            raise Rejected("AUTH_DENIED")
        if not principal.verified_at <= now < principal.expires_at:
            raise Rejected("AUTH_DENIED")
        if scope not in principal.scopes:
            raise Rejected("AUTH_DENIED")
        return principal, now

    @audited_request
    def create(self, credential, intake: Intake, *, key):
        intake = Intake.model_validate(intake)
        return self._command(credential, None, None, "CREATE", intake, key)

    @audited_request
    def search(self, credential, case_id, query: Search, *, version, key):
        query = Search.model_validate(query)
        if not query.confirmed or (query.amount is not None and query.currency is None):
            raise Rejected("CONFIRMED_CLUES_AND_CURRENCY_REQUIRED")
        return self._command(credential, case_id, version, "SEARCH", query, key)

    @audited_request
    def confirm(self, credential, case_id, selection: Selection, *, version, key):
        selection = Selection.model_validate(selection)
        if not selection.confirmed:
            raise Rejected("EXPLICIT_CONFIRMATION_REQUIRED")
        return self._command(credential, case_id, version, "CONFIRM", selection, key)

    @audited_request
    def collect(self, credential, case_id, *, version, key):
        return self._command(credential, case_id, version, "COLLECT", None, key)

    @audited_request
    def handoff(self, credential, case_id, *, version, key):
        return self._command(credential, case_id, version, "HANDOFF", None, key)

    @audited_request
    def get(self, credential, case_id):
        principal, _ = self._principal(credential, "dispute:read")
        with self.store.transaction() as db:
            return self.store.load(db, case_id, principal.customer_id)

    @audited_request
    def get_handoff(self, credential, case_id):
        principal, _ = self._principal(credential, "dispute:read")
        with self.store.transaction() as db:
            self.store.load(db, case_id, principal.customer_id)
            row = db.execute(
                "SELECT body FROM handoffs WHERE case_id=?", (case_id,)
            ).fetchone()
            return HandoffPackage.model_validate_json(row[0]) if row else None

    @audited_request
    def audit(self, credential, case_id):
        principal, _ = self._principal(credential, "dispute:read")
        with self.store.transaction() as db:
            self.store.load(db, case_id, principal.customer_id)
            cursor = db.execute(
                "SELECT * FROM audit WHERE case_id=? ORDER BY version", (case_id,)
            )
            return [
                dict(zip((c[0] for c in cursor.description), row, strict=True))
                for row in cursor
            ]

    def _command(self, credential, case_id, version, action, payload, key):
        principal, now = self._principal(credential, "dispute:write")
        if not isinstance(key, str) or not 1 <= len(key) <= 128:
            raise Rejected("INVALID_IDEMPOTENCY_KEY")
        if action != "CREATE" and (type(version) is not int or version < 1):
            raise Rejected("EXPECTED_VERSION_REQUIRED")
        digest = fingerprint(
            {
                "contract_version": VERSION,
                "case_id": case_id,
                "version": version,
                "action": action,
                "payload": payload.model_dump(mode="json") if payload else None,
            }
        )
        # One SQLite write transaction also serializes same-case commands. Tools MUST
        # be bounded local reads; no remote LLM/network calls inside this transaction.
        with self.store.transaction() as db:
            replay = self.store.replay(db, principal, key, digest)
            if replay is not None:
                return replay
            previous = None
            package = None
            if action == "CREATE":
                case = Case(
                    case_id=uuid4().hex,
                    customer_id=principal.customer_id,
                    created_by=principal.subject,
                    state=State.INTAKE_INCOMPLETE,
                    version=1,
                    as_of_time=now,
                    intake=payload,
                    extracted_clues=extract(payload.user_utterance),
                )
            else:
                previous = self.store.load(db, case_id, principal.customer_id)
                if previous.version != version:
                    raise Conflict("STALE_VERSION")
                if now < previous.as_of_time:
                    raise Rejected("CLOCK_BEFORE_CASE")
                require_action(previous.state, action)
                case = updated(previous, version=version + 1)
                if action == "SEARCH":
                    case = self._search(case, payload)
                elif action == "CONFIRM":
                    case = self._confirm(case, payload, principal)
                elif action == "COLLECT":
                    case = self._collect(case, now)
                elif action == "HANDOFF":
                    package = self._handoff(case, principal, now)
                    case = updated(
                        case,
                        state=State.HANDOFF_RECORDED,
                        handoff_id=package.handoff_id,
                    )
                else:
                    raise Rejected("UNKNOWN_COMMAND")
            self.store.persist(
                db, previous, case, principal, action, key, digest, now, package
            )
            return case

    def _search(self, case, query):
        # Clear old selection/results before each query. Never reuse stale evidence on failure.
        case = updated(
            case,
            search=query,
            candidates=(),
            candidates_truncated=False,
            selection=None,
            confirmed_by=None,
            evidence=None,
            issue=None,
        )
        try:
            result = SearchResult.model_validate(
                self.tools.search(case.customer_id, case.as_of_time, query)
            )
            items = result.candidates
            if (
                len(items) > MAX_CANDIDATES
                or len({t.transaction_id for t in items}) != len(items)
                or any(
                    not eligible(t, case.customer_id, case.as_of_time, query)
                    for t in items
                )
                or (result.truncated and len(items) != MAX_CANDIDATES)
            ):
                raise ValueError("Backend violated retrieval contract")
        except Exception:  # noqa: BLE001 - bounded tool failures become recorded insufficient evidence
            return updated(
                case, state=State.INSUFFICIENT_EVIDENCE, issue="TRANSACTION_TOOL_FAILED"
            )
        state = (
            State.MULTIPLE_CANDIDATES
            if result.truncated or len(items) > 1
            else State.AWAITING_CONFIRMATION
            if items
            else State.NO_CANDIDATE
        )
        return updated(
            case, state=state, candidates=items, candidates_truncated=result.truncated
        )

    def _owned(self, case, transaction_id):
        tx = self.tools.get(case.customer_id, transaction_id, case.as_of_time)
        if tx is None:
            return None
        tx = Transaction.model_validate(tx)
        if (
            tx.transaction_id != transaction_id
            or not eligible(tx, case.customer_id, case.as_of_time, case.search)
            or self.tools.product_owner(tx.product_id, case.as_of_time)
            != case.customer_id
        ):
            return None
        return tx

    def _confirm(self, case, selection, principal):
        old = next(
            (
                t
                for t in case.candidates
                if t.transaction_id == selection.transaction_id
            ),
            None,
        )
        if old is None:
            raise Rejected("SELECTION_NOT_IN_CANDIDATES")
        try:
            current = self._owned(case, selection.transaction_id)
            if current is None or current != old:
                return updated(
                    case,
                    state=State.INSUFFICIENT_EVIDENCE,
                    issue="OWNERSHIP_OR_EVIDENCE_CONFLICT",
                )
        except Exception:  # noqa: BLE001 - ownership verification must fail closed
            return updated(
                case, state=State.INSUFFICIENT_EVIDENCE, issue="OWNERSHIP_TOOL_FAILED"
            )
        return updated(
            case,
            state=State.OWNERSHIP_VERIFIED,
            selection=selection,
            confirmed_by=principal.subject,
            issue=None,
        )

    def _collect(self, case, now):
        try:
            tx = self._owned(case, case.selection.transaction_id)
            selected = next(
                t
                for t in case.candidates
                if t.transaction_id == case.selection.transaction_id
            )
            if tx is None or tx != selected:
                return updated(
                    case,
                    state=State.INSUFFICIENT_EVIDENCE,
                    evidence=None,
                    issue="OWNERSHIP_OR_EVIDENCE_CONFLICT",
                )
        except Exception:  # noqa: BLE001 - source failure cannot become verified evidence
            return updated(
                case,
                state=State.INSUFFICIENT_EVIDENCE,
                evidence=None,
                issue="TRANSACTION_TOOL_FAILED",
            )
        missing = [
            "external_banking_policy",
            "verified_dispute_verdict",
            "certified_historical_availability",
        ]
        history = None
        try:
            from contracts.disputes import HistoricalContext

            history = HistoricalContext.model_validate(
                self.tools.history(tx, case.as_of_time)
            )
            if (
                history.currency != tx.currency
                or history.window_end_exclusive != tx.transaction_date
                or history.window_start != tx.transaction_date - timedelta(days=30)
                or history.same_currency_count_prior_30d
                > history.transaction_count_prior_30d
                or (
                    (history.median_amount_same_currency_prior_30d is None)
                    != (history.same_currency_count_prior_30d == 0)
                )
            ):
                raise ValueError("Invalid historical context")
        except Exception:  # noqa: BLE001 - optional context failures remain explicit missing evidence
            history = None
            missing.append("historical_context_unavailable")
        if tx.merchant_name is None:
            missing.append("merchant")
        bundle = EvidenceBundle(
            transaction=tx,
            ownership_verified=True,
            historical_context=history,
            missing_evidence=tuple(missing),
            limitations=LIMITATIONS,
            as_of_time=case.as_of_time,
            collected_at=now,
        )
        return updated(case, state=State.ASSESSMENT_READY, evidence=bundle, issue=None)

    def _handoff(self, case, principal, now):
        # Always human/policy review. No reimbursement, denial, verdict or closure tool.
        evidence = case.evidence
        facts = (
            {"recorded_evidence": evidence.model_dump(mode="json")} if evidence else {}
        )
        refs = (evidence.transaction.source_ref,) if evidence else ()
        missing = (
            evidence.missing_evidence
            if evidence
            else (
                "confirmed_transaction_and_complete_evidence",
                "external_banking_policy",
            )
        )
        if evidence and evidence.historical_context:
            refs += (evidence.historical_context.source_ref,)
        questions = ["Human review and authoritative policy are required."]
        if case.selection is None:
            questions.append("Which transaction does the customer explicitly select?")
        if case.candidates_truncated:
            questions.append("Candidate list is truncated; refine the search.")
        if case.issue:
            questions.append(case.issue)
        return HandoffPackage(
            handoff_id=uuid4().hex,
            case_id=case.case_id,
            user_request=case.intake.user_utterance,
            authenticated_identity_reference=principal.subject,
            customer_id=case.customer_id,
            selected_transaction_or_candidates=(
                (case.selection.transaction_id,)
                if case.selection
                else tuple(t.transaction_id for t in case.candidates)
            ),
            verified_facts=facts,
            evidence_references=refs,
            actions_taken=(
                "Authenticated intake recorded",
                "Deterministic guards executed",
                "No financial action performed",
                "Local handoff recorded",
            ),
            missing_evidence=tuple(missing),
            unresolved_questions=tuple(questions),
            guard_results={
                "authorized_customer": True,
                "explicit_selection": case.selection is not None,
                "ownership_evidence_collected": evidence is not None,
                "policy_gate": "BLOCK_AUTOMATED_DECISION",
                "financial_action": False,
            },
            as_of_time=case.as_of_time,
            recorded_at=now,
        )
