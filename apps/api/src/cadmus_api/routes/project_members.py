"""Thin HTTP adapters for the BH-170 project-membership use cases."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from cadmus.access import (
    AccessDeniedError,
    DuplicateMembershipError,
    InvalidRoleAssignmentError,
    ListMembersService,
    ManageMembersService,
    MembershipNotFoundError,
    ProjectMembership,
    Role,
)
from cadmus.identity import (
    AuthenticationError,
    AuthenticationService,
    IdentityUnitOfWorkFactory,
    User,
)
from cadmus.sources import DictionaryAccessError, GetDictionaryService
from fastapi import APIRouter, Cookie, Depends, HTTPException, Path, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

SESSION_COOKIE_NAME = "cadmus_session"


class AddMemberRequest(BaseModel):
    """One BH-170 invite-by-email submission."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=1, max_length=255)
    role: Role


class ChangeMemberRoleRequest(BaseModel):
    """A BH-170 role change for an existing member."""

    model_config = ConfigDict(extra="forbid")

    role: Role


class MemberResponse(BaseModel):
    """One project member (owner or invited collaborator)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: UUID
    email: str
    role: Role
    created_at: datetime
    updated_at: datetime


class MembersListResponse(BaseModel):
    """Every member of a project, plus the caller's own role."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    members: list[MemberResponse]
    my_role: Role


class ErrorResponse(BaseModel):
    """Stable, non-sensitive error contract for a single failure reason."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str


class FieldErrorsResponse(BaseModel):
    """Validation errors addressable by form field."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    errors: dict[str, str]


UNAUTHORIZED_RESPONSE: dict[int | str, dict[str, object]] = {
    status.HTTP_401_UNAUTHORIZED: {
        "model": ErrorResponse,
        "description": "The browser has no valid session",
    }
}
NOT_FOUND_RESPONSE: dict[int | str, dict[str, object]] = {
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorResponse,
        "description": "The dictionary is not accessible to the caller",
    }
}


def create_project_members_router(
    authentication_service: AuthenticationService,
    get_dictionary_service: GetDictionaryService,
    manage_members_service: ManageMembersService,
    list_members_service: ListMembersService,
    identity_unit_of_work_factory: IdentityUnitOfWorkFactory,
) -> APIRouter:
    """Create BH-170 project-membership routes bound to application use cases."""
    router = APIRouter(prefix="/dictionaries/{dictionary_id}/members", tags=["members"])

    def current_user(
        session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    ) -> User:
        if session_token is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "invalid_session", "message": "Потрібна авторизація."},
            )
        try:
            return authentication_service.authenticate(session_token)
        except AuthenticationError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": error.reason, "message": "Потрібна авторизація."},
            ) from error

    AuthenticatedUser = Annotated[User, Depends(current_user)]

    def _not_found() -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"code": "not_found", "message": "Словник не знайдено."},
        )

    def _email_for(user_id: UUID) -> str:
        with identity_unit_of_work_factory() as unit_of_work:
            user = unit_of_work.users.get_user(user_id)
        return user.email if user is not None else ""

    def _member_response(membership: ProjectMembership) -> MemberResponse:
        return MemberResponse(
            user_id=membership.user_id,
            email=_email_for(membership.user_id),
            role=membership.role,
            created_at=membership.created_at,
            updated_at=membership.updated_at,
        )

    @router.get(
        "",
        response_model=MembersListResponse,
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="List every member of a project, including the owner (BH-170)",
    )
    def list_members(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
    ) -> MembersListResponse | JSONResponse:
        try:
            dictionary = get_dictionary_service.get(dictionary_id, user.id)
        except DictionaryAccessError:
            return _not_found()
        try:
            memberships = list_members_service.list_members(
                dictionary_id, dictionary.owner_id, user.id
            )
        except AccessDeniedError:
            return _not_found()
        owner = MemberResponse(
            user_id=dictionary.owner_id,
            email=_email_for(dictionary.owner_id),
            role=Role.OWNER,
            created_at=dictionary.created_at,
            updated_at=dictionary.created_at,
        )
        my_role = Role.OWNER if dictionary.owner_id == user.id else None
        members = [owner] + [_member_response(membership) for membership in memberships]
        if my_role is None:
            my_role = next(
                (member.role for member in members if member.user_id == user.id),
                Role.VIEWER,
            )
        return MembersListResponse(members=members, my_role=my_role)

    @router.post(
        "",
        response_model=MemberResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            **UNAUTHORIZED_RESPONSE,
            **NOT_FOUND_RESPONSE,
            status.HTTP_409_CONFLICT: {
                "model": ErrorResponse,
                "description": "This user is already a member of the project",
            },
            status.HTTP_422_UNPROCESSABLE_CONTENT: {
                "model": FieldErrorsResponse,
                "description": "The email or role is invalid",
            },
        },
        summary="Invite a registered user to a project by email (BH-170)",
    )
    def add_member(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
        request: AddMemberRequest,
    ) -> MemberResponse | JSONResponse:
        try:
            dictionary = get_dictionary_service.get(dictionary_id, user.id)
        except DictionaryAccessError:
            return _not_found()
        with identity_unit_of_work_factory() as unit_of_work:
            target = unit_of_work.users.get_user_by_email(request.email.strip().lower())
        if target is None:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={
                    "errors": {"email": "Користувача з такою поштою не знайдено."}
                },
            )
        try:
            membership = manage_members_service.add_member(
                dictionary_id, dictionary.owner_id, user.id, target.id, request.role
            )
        except AccessDeniedError:
            return _not_found()
        except InvalidRoleAssignmentError:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={"errors": {"role": "Цю роль не можна призначити."}},
            )
        except DuplicateMembershipError:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "code": "duplicate_member",
                    "message": "Цей користувач вже є учасником проєкту.",
                },
            )
        return _member_response(membership)

    @router.patch(
        "/{user_id}",
        response_model=MemberResponse,
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="Change a project member's role (BH-170)",
    )
    def change_member_role(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
        user_id: Annotated[UUID, Path()],
        request: ChangeMemberRoleRequest,
    ) -> MemberResponse | JSONResponse:
        try:
            dictionary = get_dictionary_service.get(dictionary_id, user.id)
        except DictionaryAccessError:
            return _not_found()
        try:
            membership = manage_members_service.change_role(
                dictionary_id, dictionary.owner_id, user.id, user_id, request.role
            )
        except (AccessDeniedError, MembershipNotFoundError):
            return _not_found()
        except InvalidRoleAssignmentError:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={"errors": {"role": "Цю роль не можна призначити."}},
            )
        return _member_response(membership)

    @router.delete(
        "/{user_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        response_model=None,
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="Remove a project member (BH-170)",
    )
    def remove_member(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
        user_id: Annotated[UUID, Path()],
    ) -> Response | JSONResponse:
        try:
            dictionary = get_dictionary_service.get(dictionary_id, user.id)
        except DictionaryAccessError:
            return _not_found()
        try:
            manage_members_service.remove_member(
                dictionary_id, dictionary.owner_id, user.id, user_id
            )
        except (AccessDeniedError, MembershipNotFoundError):
            return _not_found()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
