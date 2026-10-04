"""Fixed-algorithm demo JWT verifier implementing CaseService's credential port."""

import os
from datetime import datetime, timezone
from typing import Protocol

import jwt
from pydantic import ValidationError

from contracts.disputes import Principal
from src.cases.store import Rejected

SCOPES = frozenset({"dispute:read", "dispute:write"})


class IdentityAdapter(Protocol):
    def __call__(self, credential: str) -> Principal: ...


class DemoJWTIdentity:
    """Local issuer/verifier trust domain, not production IAM or a public token issuer.

    No token-provided algorithms, keys, URLs, customer overrides or network lookups.
    Key rotation invalidates all outstanding demo tokens; maximum lifetime one hour.
    """

    def __init__(self, *, key: str, issuer: str, audience: str):
        if len(key.encode()) < 32 or not issuer or not audience or len(issuer) > 128:
            raise ValueError("Explicit strong demo key, issuer and audience required")
        self._key, self.issuer, self.audience = key, issuer, audience

    def __call__(self, credential: str) -> Principal:
        try:
            if not isinstance(credential, str) or len(credential) > 8192:
                raise ValueError("Invalid credential")
            claims = jwt.decode(
                credential,
                self._key,
                algorithms=["HS256"],
                issuer=self.issuer,
                audience=self.audience,
                options={
                    "require": [
                        "sub",
                        "customer_id",
                        "iss",
                        "aud",
                        "iat",
                        "exp",
                        "scopes",
                    ],
                    "strict_aud": True,
                },
            )
            # Require exact claim types, not coercions or substring issuer matching.
            if claims["iss"] != self.issuer or claims["aud"] != self.audience:
                raise ValueError("Invalid trust domain")
            if any(type(claims[k]) is not int for k in ("iat", "exp")):
                raise ValueError("NumericDate must be integer")
            now = datetime.now(timezone.utc).timestamp()
            if (
                not claims["iat"] <= now < claims["exp"]
                or not 0 < claims["exp"] - claims["iat"] <= 3600
            ):
                raise ValueError("Invalid token lifetime")
            scopes = claims["scopes"]
            if (
                not isinstance(scopes, list)
                or not scopes
                or any(type(s) is not str or s not in SCOPES for s in scopes)
            ):
                raise ValueError("Invalid scopes")
            return Principal(
                subject=claims["sub"],
                customer_id=claims["customer_id"],
                provider=claims["iss"],
                scopes=frozenset(scopes),
                verified_at=datetime.fromtimestamp(claims["iat"], timezone.utc),
                expires_at=datetime.fromtimestamp(claims["exp"], timezone.utc),
            )
        except (
            jwt.PyJWTError,
            ValueError,
            TypeError,
            KeyError,
            OverflowError,
            ValidationError,
        ):
            raise Rejected("AUTH_DENIED") from None


def from_environment():
    try:
        return DemoJWTIdentity(
            key=os.environ["DISPUTE_JWT_SECRET"],
            issuer=os.environ["DISPUTE_JWT_ISSUER"],
            audience=os.environ["DISPUTE_JWT_AUDIENCE"],
        )
    except KeyError:
        raise ValueError("Missing signed demo identity configuration") from None
