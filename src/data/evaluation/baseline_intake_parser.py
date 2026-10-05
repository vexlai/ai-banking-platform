"""Frozen conservative regex baseline v1. Input text only; never retrieves account data."""

import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation

FIELDS = (
    "intent",
    "transaction_id",
    "amount",
    "currency",
    "merchant",
    "date_hint",
    "transaction_type_hint",
    "channel_hint",
)
INTENTS = {"dispute_intake", "transaction_inquiry", "unsupported_action", "unknown"}
VERSION = "regex-intake-v1"
CURRENCIES = ("USD", "COP", "ARS", "MXN", "EUR", "BRL", "JPY", "BTC")


def normalize(text):
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", text.casefold())
        if not unicodedata.combining(c)
    )


def one(values):
    values = set(values)
    return next(iter(values)) if len(values) == 1 else None


def parse_amount(token):
    """No inferred currency; ambiguous separators, negatives and malformed numbers -> unknown."""
    if not re.fullmatch(r"\d+(?:[.,]\d{1,2})?", token):
        return None
    try:
        return format(Decimal(token.replace(",", ".")).quantize(Decimal(".01")), "f")
    except InvalidOperation:
        return None


def extract(text):
    if not isinstance(text, str):
        raise TypeError("user_utterance must be a string")
    folded = normalize(text)
    result = dict.fromkeys(FIELDS)
    if re.search(
        r"reembols|devuelv|devolv|cierra|cerrar|encerre|encerrar|marc\w*.{0,20}fraud",
        folded,
    ):
        result["intent"] = "unsupported_action"
    elif re.search(
        r"no reconozco|nao reconheco|desconozco|cargo no reconocido|cobro indebido|cobranca indevida|disput",
        folded,
    ):
        result["intent"] = "dispute_intake"
    elif re.search(
        r"consulta|consultar|detalle|detalhe|informacion|informacao", folded
    ):
        result["intent"] = "transaction_inquiry"
    else:
        result["intent"] = "unknown"
    result["transaction_id"] = one(re.findall(r"\bTX-[A-Z0-9]{12}\b", text.upper()))
    currencies = re.findall(r"\b(?:" + "|".join(CURRENCIES) + r")\b", text.upper())
    result["currency"] = one(currencies)
    tokens = []
    code = r"(?:" + "|".join(CURRENCIES) + r")"
    for pattern in [
        rf"\b{code}\s+(-?\d[\d.,]*)\b",
        rf"(?<![\w/-])(-?\d[\d.,]*)\s+{code}\b",
        r"\b(?:importe|monto|valor)\s*:\s*(-?\d[\d.,]*)(?![\d/-])",
    ]:
        tokens.extend(re.findall(pattern, text, re.I))
    parsed = [parse_amount(t) for t in tokens]
    result["amount"] = (
        one(parsed) if tokens and all(x is not None for x in parsed) else None
    )
    result["merchant"] = one(
        re.findall(
            r'(?:comercio|establecimiento|loja|merchant)\s*:?\s*"([^"\n]{1,100})"',
            text,
            re.I,
        )
    )
    dates = []
    for raw in re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text):
        try:
            dates.append(date.fromisoformat(raw).isoformat())
        except ValueError:
            dates.append(None)
    for d, m, y in re.findall(r"\b(\d{2})/(\d{2})/(\d{4})\b", text):
        try:
            dates.append(date(int(y), int(m), int(d)).isoformat())
        except ValueError:
            dates.append(None)
    if re.search(r"\bayer\b|\bontem\b", folded):
        dates.append("relative:yesterday")
    if re.search(r"\bhoy\b|\bhoje\b", folded):
        dates.append("relative:today")
    for n in re.findall(r"\b(?:hace|ha)\s+(\d+)\s+dias\b", folded):
        dates.append("relative:days_ago:" + n)
    result["date_hint"] = one(dates) if all(x is not None for x in dates) else None
    types = {
        "Purchase": r"\bcompra\b",
        "Withdrawal": r"\bretiro\b|\bsaque\b",
        "Transfer": r"\btransferencia\b",
        "Payment": r"\bpago\b|\bpagamento\b",
        "Deposit": r"\bdeposito\b",
        "Adjustment": r"\bajuste\b",
    }
    result["transaction_type_hint"] = one(
        k for k, p in types.items() if re.search(p, folded)
    )
    channels = {
        "ATM": r"\batm\b|\bcajero\b|\bcaixa eletronico\b",
        "App": r"\bapp\b|\baplicativo\b",
        "Web": r"\bweb\b",
        "POS": r"\bpos\b",
        "Branch": r"\bsucursal\b|\bagencia\b",
    }
    result["channel_hint"] = one(k for k, p in channels.items() if re.search(p, folded))
    return result


def schema_valid(value):
    if not isinstance(value, dict) or set(value) != set(FIELDS):
        return False
    if value["intent"] not in INTENTS:
        return False
    if any(v is not None and not isinstance(v, str) for v in value.values()):
        return False
    if value["amount"] is not None and not re.fullmatch(r"\d+\.\d{2}", value["amount"]):
        return False
    if value["currency"] is not None and not re.fullmatch(
        r"[A-Z]{3}", value["currency"]
    ):
        return False
    if value["transaction_id"] is not None and not re.fullmatch(
        r"TX-[A-Z0-9]{12}", value["transaction_id"]
    ):
        return False
    hint = value["date_hint"]
    if hint is not None:
        if re.fullmatch(r"relative:(today|yesterday|days_ago:\d+)", hint):
            pass
        else:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", hint):
                return False
            try:
                date.fromisoformat(hint)
            except ValueError:
                return False
    return value["transaction_type_hint"] in {
        None,
        "Purchase",
        "Withdrawal",
        "Transfer",
        "Payment",
        "Deposit",
        "Adjustment",
    } and value["channel_hint"] in {None, "ATM", "App", "Web", "POS", "Branch"}


def intake_flags(value):
    """Clue sufficiency only, not retrieval outcome or authorization."""
    missing = [f for f in FIELDS if value[f] is None]
    handoff = value["intent"] == "unsupported_action"
    has_search_clues = (
        value["amount"] is not None
        and value["currency"] is not None
        and value["date_hint"] is not None
    )
    clarify = not handoff and (
        value["intent"] == "unknown"
        or not (value["transaction_id"] or has_search_clues)
    )
    return {
        "missing_fields": missing,
        "should_clarify": clarify,
        "should_handoff": handoff,
    }
