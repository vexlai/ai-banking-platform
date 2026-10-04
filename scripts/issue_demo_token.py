"""Operator-only local token issuance; no HTTP endpoint, never print credentials."""

import argparse
import os
import sys
import time
from pathlib import Path

import jwt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.identity.demo_jwt import SCOPES, from_environment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--subject", required=True)
    parser.add_argument("--customer", required=True)
    parser.add_argument("--scope", action="append", choices=sorted(SCOPES))
    parser.add_argument("--lifetime", type=int, default=900)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if (
        not output.is_relative_to((ROOT / ".tmp").resolve())
        or not 1 <= args.lifetime <= 3600
    ):
        parser.error("Use an ignored .tmp output and lifetime 1–3600 seconds")
    verifier = from_environment()
    now = int(time.time())
    value = jwt.encode(
        {
            "sub": args.subject,
            "customer_id": args.customer,
            "iss": verifier.issuer,
            "aud": verifier.audience,
            "iat": now,
            "exp": now + args.lifetime,
            "scopes": args.scope or sorted(SCOPES),
        },
        os.environ["DISPUTE_JWT_SECRET"],
        algorithm="HS256",
    )
    verifier(value)  # validate exactly what runtime will receive before publication
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(value + "\n")
    print(
        "Demo credential written privately; do not commit or paste it into logs/chat."
    )


if __name__ == "__main__":
    main()
