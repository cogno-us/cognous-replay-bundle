"""Versioned reconstruction bundle models and integrity helpers.

Reconstruction is evidence-preserving import. It does not re-run models,
renew authorization, repeat effects, or independently verify delivery.
"""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from .signing import is_hex_digest, unretained_members


RECONSTRUCTION_BUNDLE_VERSION = "0.2.0"
CANONICAL_JSON_PROFILE = "json-sort-keys-compact-utf8-no-nan"
HMAC_VERIFICATION_CLAIM = (
    "Verifiable only by a party holding the shared secret; metadata is "
    "authenticated as bundle data, but key_id does not establish public key "
    "identity, issuer identity, or production key custody."
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


class ProducerProfile(BaseModel):
    profile_id: str
    producer: str
    repository: str
    revision: str
    format_name: str
    format_version: str | None = None
    schema_ref: str | None = None
    notes: str | None = None


class SourceRecord(BaseModel):
    record_id: str
    producer_profile_id: str
    record_type: str
    source_sequence: int
    source_path: str
    recorded_at: str | None = None
    identifiers: dict[str, str] = Field(default_factory=dict)
    evidence_class: Literal[
        "producer_reported", "locally_generated", "independently_checked"
    ] = "producer_reported"
    data: dict[str, Any]


class RecordLink(BaseModel):
    link_type: Literal["explicit", "shared_reference"]
    from_record_id: str
    to_record_id: str
    basis: str
    establishes_identity_equivalence: bool = False


class CommitmentRecord(BaseModel):
    label: str
    value: str
    algorithm: str
    canonicalization_profile: str
    source_record_id: str
    source_path: str
    verification_status: Literal[
        "not_checked", "checked_match", "checked_mismatch", "attributed_claim"
    ] = "not_checked"
    notes: str | None = None


class ImportFinding(BaseModel):
    code: str
    category: Literal[
        "unmapped_field",
        "missing_dependency",
        "unsupported_semantic",
        "redaction",
        "conversion_warning",
        "value_state",
    ]
    severity: Literal["info", "warning", "error"]
    path: str
    message: str
    value_state: Literal["absent", "unknown", "unavailable", "redacted"] | None = None


class ImportReport(BaseModel):
    adapter_profile: str
    source_revision: str
    complete: bool
    field_mappings: dict[str, str] = Field(default_factory=dict)
    findings: list[ImportFinding] = Field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(item.severity == "error" for item in self.findings)


class ReconstructionSemantics(BaseModel):
    record_reconstruction: bool = True
    policy_reevaluation: bool = False
    model_reexecution: bool = False
    external_effect_execution: bool = False
    destination_observation: Literal["not_performed", "producer_reported"] = "not_performed"
    independent_effect_verification: bool = False
    notes: str = (
        "Import reconstructs recorded events only. Authorization is not renewed and "
        "no external effect is performed."
    )


class DerivationMetadata(BaseModel):
    relationship: Literal["redacted_derivative"]
    source_bundle_id: str
    derived_at: str = Field(default_factory=_now_iso)


class IntegrityMetadata(BaseModel):
    kind: Literal["content-digest", "hmac"]
    algorithm: Literal["SHA-256", "HMAC-SHA256"]
    canonicalization_profile: str = CANONICAL_JSON_PROFILE
    value: str
    subject_bundle_id: str
    key_id: str | None = None
    verification_claim: str


class ReconstructionBundle(BaseModel):
    bundle_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    bundle_version: Literal["0.2.0"] = RECONSTRUCTION_BUNDLE_VERSION
    run_id: str | None = None
    status: Literal[
        "reconstruction_complete", "reconstruction_partial", "incomplete", "redacted"
    ] = "incomplete"
    generated_at: str = Field(default_factory=_now_iso)
    producer_profiles: list[ProducerProfile] = Field(default_factory=list)
    records: list[SourceRecord] = Field(default_factory=list)
    links: list[RecordLink] = Field(default_factory=list)
    commitments: list[CommitmentRecord] = Field(default_factory=list)
    import_reports: list[ImportReport] = Field(default_factory=list)
    semantics: ReconstructionSemantics = Field(default_factory=ReconstructionSemantics)
    derivation: DerivationMetadata | None = None
    integrity: list[IntegrityMetadata] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def _content_payload(bundle: ReconstructionBundle) -> dict[str, Any]:
    """Canonical content-digest payload; integrity metadata is excluded."""
    payload = bundle.model_dump(mode="json")
    payload["integrity"] = []
    return payload


def _hmac_payload(bundle: ReconstructionBundle) -> dict[str, Any]:
    """Canonical HMAC payload with only HMAC signature values blanked.

    All other integrity metadata is authenticated, including subject bundle,
    algorithm, canonicalization profile, key_id label and verification claim.
    key_id remains only an authenticated caller-supplied label.
    """
    payload = bundle.model_dump(mode="json")
    for item in payload.get("integrity", []):
        if item.get("kind") == "hmac":
            item["value"] = ""
    return payload


def content_digest(bundle: ReconstructionBundle) -> IntegrityMetadata:
    digest = hashlib.sha256(canonical_bytes(_content_payload(bundle))).hexdigest()
    return IntegrityMetadata(
        kind="content-digest",
        algorithm="SHA-256",
        value="sha256:" + digest,
        subject_bundle_id=bundle.bundle_id,
        verification_claim=(
            "Digest covers this reconstruction-bundle derivative under the declared "
            "canonicalization profile; it is not an issuer signature."
        ),
    )


def verify_content_digest(bundle: ReconstructionBundle, *, required: bool = True) -> bool:
    """True only if the bundle's ``content-digest`` entry matches the digest recomputed from its content.

    Fails closed: more than one ``content-digest`` entry, another algorithm or canonicalization profile, a
    ``subject_bundle_id`` other than this bundle, a value that is not the recomputed ``sha256:`` digest, and (when
    ``required``) no entry at all, each return False. With ``required=False`` a bundle that carries no ``content-digest``
    entry returns True (there is nothing to check); an entry that is present is always checked.

    This is an integrity check against accidental or unsigned change, not authentication: anyone who edits the content can
    also recompute the digest (use the HMAC for a shared-secret check).

    Limit: this takes a parsed model, which no longer holds members the model dropped, so the digest covers only the model
    dump. A caller verifying a file must use ``verify_content_digest_raw`` (or ``reconstruction_unretained_members``).
    """
    entries = [item for item in bundle.integrity if item.kind == "content-digest"]
    if not entries:
        return not required
    if len(entries) != 1:
        return False
    entry = entries[0]
    expected = content_digest(bundle)
    return (
        entry.algorithm == expected.algorithm
        and entry.canonicalization_profile == expected.canonicalization_profile
        and entry.subject_bundle_id == bundle.bundle_id
        and entry.value == expected.value
    )


def sign_reconstruction_bundle(
    bundle: ReconstructionBundle, secret: str, *, key_id: str | None = None
) -> ReconstructionBundle:
    """Return a copy with metadata-bound HMAC export integrity."""
    result = bundle.model_copy(deep=True)
    result.integrity = [
        item for item in result.integrity if item.kind != "hmac"
    ] + [
        IntegrityMetadata(
            kind="hmac",
            algorithm="HMAC-SHA256",
            canonicalization_profile=CANONICAL_JSON_PROFILE,
            value="",
            subject_bundle_id=result.bundle_id,
            key_id=key_id,
            verification_claim=HMAC_VERIFICATION_CLAIM,
        )
    ]
    signature = hmac.new(
        secret.encode("utf-8"),
        canonical_bytes(_hmac_payload(result)),
        hashlib.sha256,
    ).hexdigest()
    result.integrity[-1].value = signature
    return result


def verify_reconstruction_hmac(bundle: ReconstructionBundle, secret: str) -> bool:
    """Verify the HMAC of a parsed bundle. Limit: members the model dropped when the file was parsed are not authenticated
    and cannot be seen here; to verify a file use ``verify_reconstruction_hmac_raw`` (see docs/signing.md)."""
    signatures = [item for item in bundle.integrity if item.kind == "hmac"]
    if len(signatures) != 1:
        return False
    signature = signatures[0]
    if signature.algorithm != "HMAC-SHA256":
        return False
    if signature.canonicalization_profile != CANONICAL_JSON_PROFILE:
        return False
    if signature.subject_bundle_id != bundle.bundle_id:
        return False
    if signature.verification_claim != HMAC_VERIFICATION_CLAIM:
        return False
    try:
        key = secret.encode("utf-8")
    except UnicodeEncodeError:
        return False
    expected = hmac.new(
        key,
        canonical_bytes(_hmac_payload(bundle)),
        hashlib.sha256,
    ).hexdigest()
    if not is_hex_digest(signature.value):
        return False
    return hmac.compare_digest(signature.value, expected)


def reconstruction_unretained_members(raw: object, bundle: ReconstructionBundle) -> list[str]:
    """Paths in the raw JSON of a 0.2.0 reconstruction bundle that the model did not retain, or that it coerced.

    The digest and the HMAC are computed over ``bundle.model_dump``, so a member the model dropped (an unknown field at any
    depth) or a scalar it coerced (``false`` edited to ``"false"``) is not covered by either. See ``signing.unretained_members``.
    """
    return unretained_members(raw, bundle.model_dump(mode="json"))


def load_reconstruction_bundle_checked(raw: object) -> tuple[ReconstructionBundle, list[str]]:
    """Parse the raw JSON of a reconstruction bundle; return the model and the paths it did not retain (empty when clean).

    Raises ``pydantic.ValidationError`` when the document is not a valid 0.2.0 reconstruction bundle.
    """
    bundle = ReconstructionBundle.model_validate(raw)
    return bundle, reconstruction_unretained_members(raw, bundle)


def verify_reconstruction_hmac_raw(raw: object, secret: str) -> bool:
    """``verify_reconstruction_hmac`` for the raw JSON of a file: also False when the file carries members the model does
    not retain or scalars it coerced (neither is authenticated by the HMAC), and False when it is not a valid bundle."""
    from pydantic import ValidationError

    try:
        bundle, extra = load_reconstruction_bundle_checked(raw)
    except ValidationError:
        return False
    return not extra and verify_reconstruction_hmac(bundle, secret)


def verify_content_digest_raw(raw: object, *, required: bool = True) -> bool:
    """``verify_content_digest`` for the raw JSON of a file: also False when the file carries members the model does not
    retain or scalars it coerced (the digest does not cover them), and False when it is not a valid bundle."""
    from pydantic import ValidationError

    try:
        bundle, extra = load_reconstruction_bundle_checked(raw)
    except ValidationError:
        return False
    return not extra and verify_content_digest(bundle, required=required)


def redact_reconstruction_bundle(
    bundle: ReconstructionBundle,
    *,
    redact_paths: set[str],
    replacement: Any = "[REDACTED]",
) -> ReconstructionBundle:
    """Create a separately identified redacted derivative."""
    result = bundle.model_copy(deep=True)
    source_id = bundle.bundle_id
    result.bundle_id = str(uuid.uuid4())
    result.generated_at = _now_iso()
    result.status = "redacted"
    result.derivation = DerivationMetadata(
        relationship="redacted_derivative",
        source_bundle_id=source_id,
    )
    result.integrity = []

    redacted_ids: set[str] = set()
    for record in result.records:
        if record.source_path in redact_paths:
            record.data = {"redacted": True, "replacement": copy.deepcopy(replacement)}
            redacted_ids.add(record.record_id)
            for report in result.import_reports:
                report.findings.append(
                    ImportFinding(
                        code="R001",
                        category="redaction",
                        severity="info",
                        path=record.source_path,
                        message="Source record content replaced in redacted derivative.",
                        value_state="redacted",
                    )
                )
    if not redacted_ids:
        raise ValueError("no source records matched redact_paths")

    for commitment in result.commitments:
        if commitment.source_record_id in redacted_ids:
            commitment.verification_status = "attributed_claim"
            commitment.notes = (
                "Original source commitment retained as an attributed claim; "
                "it does not authenticate redacted derivative content."
            )
    result.integrity = [content_digest(result)]
    return result
