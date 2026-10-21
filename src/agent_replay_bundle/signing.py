"""Export integrity signing for Agent Replay Bundle using HMAC-SHA256."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import datetime, timezone

from .models import AgentReplayBundle, SignatureMetadata, SignedReplayBundle


_HEX_DIGEST = re.compile(r"[0-9a-f]{64}")


def is_hex_digest(value: object) -> bool:
    """True only for a 64-character lowercase ASCII hex string (an HMAC-SHA256 hex digest).

    ``hmac.compare_digest`` raises on a non-ASCII ``str``, so a stored signature that is not exactly this shape is
    refused before any comparison.
    """
    return isinstance(value, str) and _HEX_DIGEST.fullmatch(value) is not None


def canonical_bundle_json(bundle: AgentReplayBundle) -> str:
    """Produce a canonical JSON string of the bundle for signing.

    The entire ``signature_metadata`` field is excluded from the canonical
    representation so that embedded signature state does not affect signing or
    verification. All keys are sorted and compact separators are used to
    guarantee a stable, reproducible encoding.

    Args:
        bundle: The bundle to serialize.

    Returns:
        A canonical JSON string suitable for hashing.
    """
    data = bundle.model_dump(mode="json")
    data.pop("signature_metadata", None)
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


_ENVELOPE_DOMAIN = b"agent-replay-bundle/export-signature/2\n"


def canonical_envelope_bytes(
    signed_bundle_id: str,
    signature_metadata: SignatureMetadata,
    bundle: AgentReplayBundle,
) -> bytes:
    """Canonical bytes covered by a new signature: the envelope, the signature metadata fields and the whole inner bundle.

    The inner bundle is dumped with its own embedded ``signature_metadata`` (the bundle-only form drops it). Of the outer
    ``signature_metadata`` every field except the signature value is covered. A fixed prefix keeps these bytes apart from the
    bundle-only form, so a signature of one is never a signature of the other.
    """
    covered = signature_metadata.model_dump(mode="json")
    covered.pop("signature", None)
    document = {
        "signed_bundle_id": signed_bundle_id,
        "signature_metadata": covered,
        "replay_bundle": bundle.model_dump(mode="json"),
    }
    return _ENVELOPE_DOMAIN + json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")


def sign_replay_bundle(
    bundle: AgentReplayBundle,
    secret: str,
    *,
    key_id: str | None = None,
) -> SignedReplayBundle:
    """Sign a replay bundle with HMAC-SHA256 and return a SignedReplayBundle.

    This is export integrity signing, not production key management.  The
    caller is responsible for handling the secret securely.

    Args:
        bundle: The bundle to sign.
        secret: The HMAC secret key.
        key_id: Optional identifier for the signing key.

    Returns:
        A SignedReplayBundle containing the bundle and its signature metadata.
    """
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sig_meta = SignatureMetadata(
        signed=True,
        signed_at=now_iso,
        signature_algorithm="HMAC-SHA256",
        signature=None,
        key_id=key_id,
    )

    import uuid

    signed_id = f"signed-{bundle.bundle_id}-{uuid.uuid4().hex[:8]}"
    sig_meta.signature = hmac.new(
        secret.encode("utf-8"),
        canonical_envelope_bytes(signed_id, sig_meta, bundle),
        hashlib.sha256,
    ).hexdigest()
    return SignedReplayBundle(
        signed_bundle_id=signed_id,
        replay_bundle=bundle,
        signature_metadata=sig_meta,
    )


def signature_coverage(signed_bundle: SignedReplayBundle, secret: str) -> str | None:
    """What a matching signature covers: ``"envelope_and_bundle"`` (current form), ``"bundle_only"`` (earlier form: the
    envelope and the signature metadata fields are not covered) or ``None`` when the signature does not match."""
    stored_sig = signed_bundle.signature_metadata.signature
    if not is_hex_digest(stored_sig):
        return None
    try:
        key = secret.encode("utf-8")
    except UnicodeEncodeError:  # e.g. a command-line secret holding undecodable bytes: no signature can match it
        return None
    forms = (
        ("envelope_and_bundle", canonical_envelope_bytes(
            signed_bundle.signed_bundle_id, signed_bundle.signature_metadata, signed_bundle.replay_bundle)),
        ("bundle_only", canonical_bundle_json(signed_bundle.replay_bundle).encode("utf-8")),
    )
    for name, message in forms:
        expected = hmac.new(key, message, hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected, stored_sig):  # both ASCII lowercase hex of equal length
            return name
    return None


def _same_scalar(raw: object, retained: object) -> bool:
    """Same JSON value and type; a bool is never an int, and an int equals a float of the same value."""
    if isinstance(raw, bool) or isinstance(retained, bool):
        return type(raw) is type(retained) and raw == retained
    if isinstance(raw, (int, float)) and isinstance(retained, (int, float)):
        return raw == retained
    return type(raw) is type(retained) and raw == retained


def unretained_members(raw: object, retained: object, _path: str = "$") -> list[str]:
    """Paths of the members of a parsed JSON document that the parsed models did not retain.

    ``raw`` is the JSON as parsed from the file; ``retained`` is ``model_dump(mode="json")`` of the model built from it.
    The HMAC covers only the retained form, so a member listed here (an unknown field the models silently dropped) is not
    authenticated. Member names, list lengths and scalar values are compared; a scalar that the models coerced (a signed
    ``false`` edited to ``"false"`` or ``0``) is listed with a ``[value]`` suffix, because the file then reads differently
    from what was signed. An integer and a float of equal value (``1`` and ``1.0``) count as equal. Free-form members
    (``payload``, ``metadata``) are retained whole, so they are listed only if they differ.
    """
    found: list[str] = []
    if isinstance(raw, dict) and isinstance(retained, dict):
        for key, value in raw.items():
            if key not in retained:
                found.append(f"{_path}.{key}")
            else:
                found.extend(unretained_members(value, retained[key], f"{_path}.{key}"))
    elif isinstance(raw, list) and isinstance(retained, list):
        if len(raw) != len(retained):
            found.append(f"{_path}[length]")
        else:
            for index, (a, b) in enumerate(zip(raw, retained)):
                found.extend(unretained_members(a, b, f"{_path}[{index}]"))
    elif not _same_scalar(raw, retained):
        found.append(f"{_path}[value]")
    return found


def verify_signed_replay_bundle(
    signed_bundle: SignedReplayBundle,
    secret: str,
    *,
    allow_unbound_envelope: bool = False,
) -> bool:
    """Verify the HMAC-SHA256 signature of a signed replay bundle.

    A signature written by this version covers the envelope and the signature metadata fields. A signature written before
    that (bundle only) is refused unless ``allow_unbound_envelope`` is True; ``signature_coverage`` says which form matched.

    Args:
        signed_bundle: The signed bundle to verify.
        secret: The HMAC secret key.
        allow_unbound_envelope: Accept a bundle-only signature (default False; the envelope and signature metadata of such a signature are
            not authenticated).

    Returns:
        True if the signature is valid, False otherwise.
    """
    coverage = signature_coverage(signed_bundle, secret)
    return coverage == "envelope_and_bundle" or (coverage == "bundle_only" and allow_unbound_envelope)
