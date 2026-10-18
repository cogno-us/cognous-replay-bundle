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
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


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
    return _ENVELOPE_DOMAIN + json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


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


def verify_signed_replay_bundle(
    signed_bundle: SignedReplayBundle,
    secret: str,
    *,
    allow_unbound_envelope: bool = True,
) -> bool:
    """Verify the HMAC-SHA256 signature of a signed replay bundle.

    A signature written by this version covers the envelope and the signature metadata fields. A signature written before
    that (bundle only) still verifies unless ``allow_unbound_envelope`` is False; ``signature_coverage`` says which form matched.

    Args:
        signed_bundle: The signed bundle to verify.
        secret: The HMAC secret key.
        allow_unbound_envelope: Accept a bundle-only signature (default True).

    Returns:
        True if the signature is valid, False otherwise.
    """
    coverage = signature_coverage(signed_bundle, secret)
    return coverage == "envelope_and_bundle" or (coverage == "bundle_only" and allow_unbound_envelope)
