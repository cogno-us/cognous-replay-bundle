"""Command-line interface for Agent Replay Bundle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load_bundle(path: str):
    """Load and return an AgentReplayBundle, printing errors and exiting on failure."""
    from .ingress import EXIT_INPUT_BOUNDS, InputBoundsError
    from .loader import load_replay_bundle

    try:
        return load_replay_bundle(path)
    except InputBoundsError as exc:
        print(f"Error: {exc.code}: {exc}", file=sys.stderr)
        sys.exit(EXIT_INPUT_BOUNDS)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate a replay bundle and print a compact report."""
    from .validator import validate_replay_bundle

    bundle = _load_bundle(args.path)
    report = validate_replay_bundle(bundle)

    status = "VALID" if report.valid else "INVALID"
    print(f"{status}  bundle_id={bundle.bundle_id}  issues={len(report.issues)}")

    errors = [i for i in report.issues if i.severity.value == "error"]
    warnings = [i for i in report.issues if i.severity.value == "warning"]

    for issue in errors:
        loc = f"  [{issue.path}]" if issue.path else ""
        print(f"  ERROR   {issue.code}: {issue.message}{loc}")
    for issue in warnings:
        loc = f"  [{issue.path}]" if issue.path else ""
        print(f"  WARNING {issue.code}: {issue.message}{loc}")

    return 0 if report.valid else 1


def cmd_summarize(args: argparse.Namespace) -> int:
    """Print a human-readable summary of a replay bundle."""
    bundle = _load_bundle(args.path)

    redacted = "yes" if (bundle.redaction_metadata and bundle.redaction_metadata.redacted) else "no"
    signed = "yes" if (bundle.signature_metadata and bundle.signature_metadata.signed) else "no"
    output_present = "present" if bundle.final_output is not None else "missing"

    print(f"bundle_id:          {bundle.bundle_id}")
    print(f"run_id:             {bundle.run_id}")
    print(f"status:             {bundle.status.value}")
    print(f"actor:              {bundle.frame.actor}")
    print(f"environment:        {bundle.frame.environment}")
    print(f"policy_version:     {bundle.frame.policy_version}")
    print(f"action_proposals:   {len(bundle.action_proposals)}")
    print(f"policy_decisions:   {len(bundle.policy_decisions)}")
    print(f"policy_traces:      {len(bundle.policy_traces)}")
    print(f"blocked_actions:    {len(bundle.blocked_actions)}")
    print(f"authority_records:  {len(bundle.authority_records)}")
    print(f"reliance_records:   {len(bundle.reliance_records)}")
    print(f"final_output:       {output_present}")
    print(f"redacted:           {redacted}")
    print(f"signed:             {signed}")

    return 0


def cmd_redact(args: argparse.Namespace) -> int:
    """Redact a replay bundle and write the result to a file."""
    from .loader import dump_replay_bundle
    from .redaction import redact_replay_bundle

    bundle = _load_bundle(args.path)
    redacted = redact_replay_bundle(
        bundle,
        redact_payloads=True,
        redact_targets=args.targets,
        redact_final_output=args.final_output,
        redact_reasons=args.reasons,
        replacement=args.replacement,
        redaction_policy=args.policy,
    )
    out_path = dump_replay_bundle(redacted, args.out)
    print(f"Redacted bundle written to {out_path}")
    return 0


def cmd_sign(args: argparse.Namespace) -> int:
    """Sign a replay bundle and write the signed bundle to a file."""
    from .signing import sign_replay_bundle

    bundle = _load_bundle(args.path)
    signed = sign_replay_bundle(bundle, args.secret, key_id=args.key_id)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(signed.model_dump(mode="json"), f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Signed bundle written to {out_path.resolve()}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify the signature on a signed replay bundle."""
    from pydantic import ValidationError

    from .ingress import (
        EXIT_INPUT_BOUNDS,
        DuplicateMemberError,
        InputBoundsError,
        load_json_bounded,
    )
    from .signing import verify_signed_replay_bundle
    from .models import SignedReplayBundle

    try:
        data = load_json_bounded(args.path, reject_duplicates=True)
    except FileNotFoundError:
        print(f"Error: File not found: {args.path}", file=sys.stderr)
        sys.exit(2)
    except InputBoundsError as exc:
        print(f"Error: {exc.code}: {exc}", file=sys.stderr)
        sys.exit(EXIT_INPUT_BOUNDS)
    except DuplicateMemberError as exc:
        print(f"Error: Invalid JSON: {exc}", file=sys.stderr)
        sys.exit(2)
    except ValueError as exc:
        print(f"Error: Invalid JSON: {exc}", file=sys.stderr)
        sys.exit(2)

    try:
        signed_bundle = SignedReplayBundle.model_validate(data)
    except ValidationError as exc:
        print(f"Error: Invalid signed bundle: {exc}", file=sys.stderr)
        sys.exit(2)

    if verify_signed_replay_bundle(signed_bundle, args.secret):
        print("Signature VALID")
        return 0
    else:
        print("Signature INVALID")
        return 1


def cmd_check_examples(args: argparse.Namespace) -> int:
    """Validate all example bundles."""
    from pydantic import ValidationError

    from .ingress import load_json_bounded
    from .loader import load_replay_bundle
    from .models import SignedReplayBundle
    from .reconstruction import ReconstructionBundle
    from .validator import validate_replay_bundle

    examples_dir = Path(__file__).parent.parent.parent / "examples"
    if not examples_dir.exists():
        # Try relative to cwd
        examples_dir = Path("examples")

    if not examples_dir.exists():
        print("Error: examples/ directory not found.", file=sys.stderr)
        sys.exit(2)

    all_ok = True

    for json_file in sorted(examples_dir.glob("*.json")):
        name = json_file.name

        try:
            raw = load_json_bounded(json_file)
        except ValueError as exc:
            print(f"  FAIL             {name}: {exc}")
            all_ok = False
            continue

        if raw.get("bundle_version") == "0.2.0":
            try:
                ReconstructionBundle.model_validate(raw)
                print(f"  OK (reconstruction) {name}")
            except ValidationError as exc:
                print(f"  FAIL             {name}: {exc}")
                all_ok = False
            continue

        if name == "signed_replay_bundle.json":
            # Load as SignedReplayBundle — structural check only
            try:
                SignedReplayBundle.model_validate(raw)
                print(f"  OK (structural)  {name}")
            except (json.JSONDecodeError, ValidationError) as exc:
                print(f"  FAIL             {name}: {exc}")
                all_ok = False
            continue

        try:
            bundle = load_replay_bundle(json_file)
        except ValueError as exc:
            print(f"  FAIL             {name}: {exc}")
            all_ok = False
            continue

        report = validate_replay_bundle(bundle)
        errors = [i for i in report.issues if i.severity.value == "error"]
        if errors:
            print(f"  FAIL             {name}: {len(errors)} error(s)")
            for e in errors:
                print(f"    ERROR {e.code}: {e.message}")
            all_ok = False
        else:
            print(f"  OK               {name}")

    return 0 if all_ok else 1


def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser(
        prog="arb",
        description="Agent Replay Bundle CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # validate
    p_validate = sub.add_parser("validate", help="Validate a replay bundle.")
    p_validate.add_argument("path", help="Path to the replay bundle JSON file.")

    # summarize
    p_summarize = sub.add_parser("summarize", help="Print a summary of a replay bundle.")
    p_summarize.add_argument("path", help="Path to the replay bundle JSON file.")

    # redact
    p_redact = sub.add_parser("redact", help="Redact a replay bundle.")
    p_redact.add_argument("path", help="Path to the replay bundle JSON file.")
    p_redact.add_argument("--out", required=True, help="Output path for the redacted bundle.")
    p_redact.add_argument("--targets", action="store_true", default=False, help="Redact action targets.")
    p_redact.add_argument("--final-output", dest="final_output", action="store_true", default=False, help="Redact the final output.")
    p_redact.add_argument("--reasons", action="store_true", default=False, help="Redact reason fields.")
    p_redact.add_argument("--replacement", default="[REDACTED]", help="Replacement string for redacted values.")
    p_redact.add_argument("--policy", default=None, help="Redaction policy name.")

    # sign
    p_sign = sub.add_parser("sign", help="Sign a replay bundle.")
    p_sign.add_argument("path", help="Path to the replay bundle JSON file.")
    p_sign.add_argument("--secret", required=True, help="HMAC secret key.")
    p_sign.add_argument("--out", required=True, help="Output path for the signed bundle.")
    p_sign.add_argument("--key-id", dest="key_id", default=None, help="Optional key identifier.")

    # verify
    p_verify = sub.add_parser("verify", help="Verify a signed replay bundle.")
    p_verify.add_argument("path", help="Path to the signed bundle JSON file.")
    p_verify.add_argument("--secret", required=True, help="HMAC secret key.")

    # check-examples
    sub.add_parser("check-examples", help="Validate all example bundles.")

    return parser


def main() -> None:
    """Entry point for the arb CLI."""
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "validate": cmd_validate,
        "summarize": cmd_summarize,
        "redact": cmd_redact,
        "sign": cmd_sign,
        "verify": cmd_verify,
        "check-examples": cmd_check_examples,
    }

    fn = dispatch.get(args.command)
    if fn is None:
        parser.print_help()
        sys.exit(2)

    sys.exit(fn(args))


if __name__ == "__main__":
    main()
