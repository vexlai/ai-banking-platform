"""Secure HTTP adapter: no SQL, tools, state decisions, or orchestration here."""

import sqlite3
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError

from contracts.dispute_http import (
    AuditResponse,
    CaseResponse,
    ConfirmCommand,
    ErrorResponse,
    SearchCommand,
    VersionCommand,
)
from contracts.disputes import HandoffPackage, Intake
from src.cases.service import CaseService
from src.cases.store import Conflict, Rejected
from src.cases.tools import ToolFailure

bearer = HTTPBearer(auto_error=False)
# Only stable, inspected domain codes are exposed. Unknown exceptions fail closed.
ERROR_STATUS = {
    "AUTH_DENIED": 401,
    "CASE_NOT_ACCESSIBLE": 404,  # indistinguishable absent vs other customer's case
    "STALE_VERSION": 409,
    "IDEMPOTENCY_KEY_REUSED": 409,
    "INVALID_TRANSITION": 409,
    "TERMINAL_CASE": 409,
    "CONFIRMED_CLUES_AND_CURRENCY_REQUIRED": 422,
    "EXPLICIT_CONFIRMATION_REQUIRED": 422,
    "SELECTION_NOT_IN_CANDIDATES": 422,
    "INVALID_IDEMPOTENCY_KEY": 422,
    "EXPECTED_VERSION_REQUIRED": 422,
    "CLOCK_BEFORE_CASE": 503,
}


class DisputeRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def safe_handler(request: Request):
            # Server-owned correlation; never a credential or a domain idempotency key.
            request_id = uuid4().hex
            request.state.request_id = request_id
            headers = {"X-Request-ID": request_id, "Cache-Control": "no-store"}

            def error(status, code):
                if status == 401:
                    headers["WWW-Authenticate"] = "Bearer"
                return JSONResponse(
                    status_code=status,
                    content=ErrorResponse(
                        code=code, request_id=request_id
                    ).model_dump(),
                    headers=headers,
                )

            try:
                response = await handler(request)
            except (Rejected, Conflict) as exc:
                code = str(exc)
                return error(
                    ERROR_STATUS.get(code, 503),
                    code if code in ERROR_STATUS else "SERVICE_UNAVAILABLE",
                )
            except RequestValidationError:
                # FastAPI defaults can echo input values/credentials; never return them.
                return error(422, "INVALID_REQUEST")
            except (sqlite3.Error, OSError, ToolFailure):
                return error(503, "SERVICE_UNAVAILABLE")
            except ValidationError:
                # An invalid service OUTPUT is an internal failure, not user input.
                return error(500, "INTERNAL_ERROR")
            except Exception:  # noqa: BLE001 - transport containment, no exception details/PII returned
                return error(500, "INTERNAL_ERROR")
            response.headers.update(headers)
            return response

        return safe_handler


def credential(
    value: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> str:
    if value is None or value.scheme.lower() != "bearer":
        raise Rejected("AUTH_DENIED")
    # Opaque credential only; CaseService's injected verifier resolves Principal.
    return value.credentials


def service(request: Request) -> CaseService:
    configured = getattr(request.app.state, "case_service", None)
    if configured is None:
        raise Rejected("SERVICE_UNAVAILABLE")
    return configured


Credential = Annotated[str, Depends(credential)]
Service = Annotated[CaseService, Depends(service)]
Key = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)]

router = APIRouter(
    prefix="/v1/disputes",
    tags=["current-dispute-mvp"],
    route_class=DisputeRoute,
    responses={
        code: {"model": ErrorResponse} for code in (401, 404, 409, 422, 500, 503)
    },
)


@router.post("", response_model=CaseResponse, status_code=201)
def create(body: Intake, token: Credential, runtime: Service, key: Key):
    return CaseResponse.from_case(runtime.create(token, body, key=key))


@router.post("/{case_id}/search", response_model=CaseResponse)
def search(
    case_id: str, body: SearchCommand, token: Credential, runtime: Service, key: Key
):
    return CaseResponse.from_case(
        runtime.search(
            token, case_id, body.query, version=body.expected_version, key=key
        )
    )


@router.post("/{case_id}/confirm", response_model=CaseResponse)
def confirm(
    case_id: str, body: ConfirmCommand, token: Credential, runtime: Service, key: Key
):
    return CaseResponse.from_case(
        runtime.confirm(
            token, case_id, body.selection, version=body.expected_version, key=key
        )
    )


@router.post("/{case_id}/evidence", response_model=CaseResponse)
def collect(
    case_id: str, body: VersionCommand, token: Credential, runtime: Service, key: Key
):
    return CaseResponse.from_case(
        runtime.collect(token, case_id, version=body.expected_version, key=key)
    )


@router.post("/{case_id}/handoff", response_model=CaseResponse)
def handoff(
    case_id: str, body: VersionCommand, token: Credential, runtime: Service, key: Key
):
    return CaseResponse.from_case(
        runtime.handoff(token, case_id, version=body.expected_version, key=key)
    )


@router.get("/{case_id}", response_model=CaseResponse)
def get(case_id: str, token: Credential, runtime: Service):
    return CaseResponse.from_case(runtime.get(token, case_id))


@router.get("/{case_id}/audit", response_model=list[AuditResponse])
def audit(case_id: str, token: Credential, runtime: Service):
    return [
        AuditResponse.model_validate({k: row[k] for k in AuditResponse.model_fields})
        for row in runtime.audit(token, case_id)
    ]


@router.get("/{case_id}/handoff", response_model=HandoffPackage | None)
def get_handoff(case_id: str, token: Credential, runtime: Service):
    return runtime.get_handoff(token, case_id)
