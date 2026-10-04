"""Consultative extraction of a case's immutable request, outside SQLite transactions."""

from fastapi import APIRouter, Request, Response

from api.routes.disputes import Credential, DisputeRoute, Service
from src.intake.extractor import ExtractionResult, record_metadata

router = APIRouter(
    prefix="/v1/disputes", tags=["current-dispute-mvp"], route_class=DisputeRoute
)


@router.post(
    "/{case_id}/intake-extraction",
    response_model=ExtractionResult,
    responses={502: {"model": ExtractionResult}},
)
def extract_intake(
    case_id: str,
    request: Request,
    response: Response,
    token: Credential,
    runtime: Service,
):
    case = runtime.get(token, case_id)  # authorize BEFORE sending text to provider
    extractor = request.app.state.intake_extractor
    outcome = extractor.extract(case.intake.user_utterance)  # text ONLY
    runtime.get(token, case_id)  # expiry/authorization may change during provider call
    record_metadata(
        outcome,
        request_id=request.state.request_id,
        case_id=case_id,
        language=case.intake.language,
    )
    if outcome.status == "model_error":
        response.status_code = 502
    return outcome  # no Search, confirmation, state mutation or write to runtime
