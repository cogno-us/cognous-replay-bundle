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
    canonical = canonical_bundle_json(bundle)
    digest = hmac.new(
        secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sig_meta = SignatureMetadata(
        signed=True,
        signed_at=now_iso,
        signature_algorithm="HMAC-SHA256",
        signature=digest,
        key_id=key_id,
    )

    import uuid

    signed_id = f"signed-{bundle.bundle_id}-{uuid.uuid4().hex[:8]}"
    return SignedReplayBundle(
        signed_bundle_id=signed_id,
        replay_bundle=bundle,
        signature_metadata=sig_meta,
    )


def verify_signed_replay_bundle(
    signed_bundle: SignedReplayBundle,
    secret: str,
) -> bool:
    """Verify the HMAC-SHA256 signature of a signed replay bundle.

    Args:
        signed_bundle: The signed bundle to verify.
        secret: The HMAC secret key.

    Returns:
        True if the signature is valid, False otherwise.
    """
    stored_sig = signed_bundle.signature_metadata.signature
    if not is_hex_digest(stored_sig):
        return False

    canonical = canonical_bundle_json(signed_bundle.replay_bundle)
    try:
        key = secret.encode("utf-8")
    except UnicodeEncodeError:  # e.g. a command-line secret holding undecodable bytes: no signature can match it
        return False
    expected = hmac.new(
        key,
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, stored_sig)  # both ASCII lowercase hex of equal length
