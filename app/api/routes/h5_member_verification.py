from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import (
    get_current_h5_member_context,
    get_h5_member_verification_service,
)
from app.schemas.h5_member_verification import (
    H5MemberVerificationCreateRequest,
    H5MemberVerificationRequestResponse,
    H5MemberVerificationSummaryResponse,
)
from app.services.h5_member_auth_service import H5MemberContext
from app.services.h5_member_verification_service import H5MemberVerificationService

router = APIRouter(prefix="/api/h5", tags=["h5-member-verification"])


@router.get(
    "/member/verification",
    summary="Get verification summary",
    description="Get H5 member verification status summary.",
    tags=["h5-member-verification"],
)
async def get_h5_member_verification_summary(
    verification_service: H5MemberVerificationService = Depends(get_h5_member_verification_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> H5MemberVerificationSummaryResponse:
    return await verification_service.get_summary(context=context)


@router.get(
    "/member/verification/requests",
    summary="List verification requests",
    description="List H5 member verification requests.",
    tags=["h5-member-verification"],
)
async def list_h5_member_verification_requests(
    verification_service: H5MemberVerificationService = Depends(get_h5_member_verification_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> list[H5MemberVerificationRequestResponse]:
    return await verification_service.list_requests(context=context)


@router.post(
    "/member/verification/requests",
    summary="Create verification request",
    description="Submit a new H5 member verification request.",
    tags=["h5-member-verification"],
)
async def create_h5_member_verification_request(
    payload: H5MemberVerificationCreateRequest,
    verification_service: H5MemberVerificationService = Depends(get_h5_member_verification_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> H5MemberVerificationRequestResponse:
    try:
        return await verification_service.create_request(context=context, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/member/verification/requests/{request_id}",
    summary="Get verification request",
    description="Get a specific H5 member verification request.",
    tags=["h5-member-verification"],
)
async def get_h5_member_verification_request(
    request_id: str,
    verification_service: H5MemberVerificationService = Depends(get_h5_member_verification_service),
    context: H5MemberContext = Depends(get_current_h5_member_context),
) -> H5MemberVerificationRequestResponse:
    try:
        return await verification_service.get_request(context=context, request_id=request_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
