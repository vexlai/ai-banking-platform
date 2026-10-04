"""Boundary model mirrors frozen eight-field schema; derived flags stay outside AI."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from src.evaluation.baseline_intake_parser import intake_flags, schema_valid


class StructuredIntake(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    intent: Literal[
        "dispute_intake", "transaction_inquiry", "unsupported_action", "unknown"
    ]
    transaction_id: str | None
    amount: str | None
    currency: str | None
    merchant: str | None
    date_hint: str | None
    transaction_type_hint: (
        Literal[
            "Purchase", "Withdrawal", "Transfer", "Payment", "Deposit", "Adjustment"
        ]
        | None
    )
    channel_hint: Literal["ATM", "App", "Web", "POS", "Branch"] | None

    @model_validator(mode="after")
    def semantic_schema(self):
        if not schema_valid(self.model_dump()):
            raise ValueError("FROZEN_SCHEMA_INVALID")
        if self.merchant is not None and not 1 <= len(self.merchant.strip()) <= 100:
            raise ValueError("MERCHANT_INVALID")
        if self.amount is not None and len(self.amount.replace(".", "")) > 24:
            raise ValueError("AMOUNT_OUT_OF_RANGE")
        return self

    def flags(self):
        return intake_flags(self.model_dump())
