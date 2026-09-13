"""Thin, deterministic request boundary for the LaunchPad Codex entry skill.

The router authenticates a structured host event through an injected verifier,
parses only the protocol-owned public grammar, renders support diagnostics, and
prepares digest-pinned canonical input. It does not execute workflow prose or
own approvals, permits, scheduling, mutation state, receipts, or terminal state.
"""

from __future__ import annotations

import dataclasses
import difflib
import hashlib
import importlib.util
import json
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, NoReturn, Protocol, cast

SCRIPT_REAL_PATH: Final = Path(os.path.realpath(__file__))
SCRIPT_DIR: Final = SCRIPT_REAL_PATH.parent
PLUGIN_ROOT: Final = SCRIPT_DIR.parent
PROTOCOL_PATH: Final = SCRIPT_DIR / "plugin-codex-protocol.py"
RESOLVER_PATH: Final = SCRIPT_DIR / "plugin-codex-resolver.py"
SUPPORT_PATH: Final = SCRIPT_DIR / "plugin-codex-support.py"


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_PROTOCOL = _load_module("launchpad_codex_protocol_for_router", PROTOCOL_PATH)
_RESOLVER = _load_module("launchpad_codex_resolver_for_router", RESOLVER_PATH)
_SUPPORT = _load_module("launchpad_codex_support_for_router", SUPPORT_PATH)


class RouterError(ValueError):
    """Stable router failure classified by the adapter protocol."""

    def __init__(self, code: str, message: str, protocol: Any | None = None) -> None:
        super().__init__(message)
        contract = protocol or _PROTOCOL.load_protocol()
        self.code = code
        self.reporting_class = contract.reporting_class_for_error(code)


def _fail(code: str, message: str, protocol: Any) -> NoReturn:
    raise RouterError(code, message, protocol)


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


@dataclass(frozen=True)
class VerifiedInvocation:
    """Host-authenticated explicit skill invocation supplied by a verifier."""

    event_id: str
    selected_skill: str
    tokens: tuple[str, ...]
    provenance: str
    interaction_mode: str
    collision_free: bool


class InvocationVerifier(Protocol):
    """Non-model authority that authenticates one opaque host event."""

    def verify(self, event: object) -> VerifiedInvocation: ...


@dataclass(frozen=True)
class HostEnvironment:
    host: str
    operating_system: str
    capabilities: tuple[str, ...]
    tool_versions: Mapping[str, str]


@dataclass(frozen=True)
class ParsedRequest:
    action: str
    resource_id: str | None
    public_name: str | None
    arguments: tuple[str, ...]


@dataclass(frozen=True)
class RouterResponse:
    status: str
    action: str
    code: str | None
    reporting_class: str
    protocol_version: str
    payload: Mapping[str, object]


def response_as_dict(response: RouterResponse) -> dict[str, object]:
    return cast(dict[str, object], dataclasses.asdict(response))


def _validate_name(value: object, protocol: Any) -> str:
    if not isinstance(value, str) or protocol.name_pattern.fullmatch(value) is None:
        _fail(
            "INVOCATION_GRAMMAR_INVALID",
            "public name does not match the LaunchPad grammar",
            protocol,
        )
    if value in protocol.router["reserved_tokens"]:
        _fail(
            "INVOCATION_GRAMMAR_INVALID",
            "public name collides with a reserved router token",
            protocol,
        )
    return value


def parse_verified_invocation(
    invocation: VerifiedInvocation, protocol: Any | None = None
) -> ParsedRequest:
    """Parse an already authenticated immutable token sequence."""
    contract = protocol or _PROTOCOL.load_protocol()
    if not isinstance(invocation, VerifiedInvocation):
        _fail(
            "INVOCATION_PROVENANCE_UNAVAILABLE",
            "verifier did not return a typed invocation",
            contract,
        )
    if (
        invocation.provenance != "authenticated_user_explicit"
        or invocation.selected_skill != contract.router["entry_skill"]
    ):
        _fail(
            "INVOCATION_PROVENANCE_UNAVAILABLE",
            "host did not authenticate an explicit lp skill invocation",
            contract,
        )
    if not invocation.collision_free:
        _fail(
            "INVOCATION_COLLISION",
            "host did not prove collision-free lp selection",
            contract,
        )
    if invocation.interaction_mode not in {"interactive", "headless"}:
        _fail(
            "INTERACTION_ATTESTATION_UNAVAILABLE",
            "host did not attest the interaction mode",
            contract,
        )
    if (
        not isinstance(invocation.event_id, str)
        or not invocation.event_id
        or len(invocation.event_id) > contract.limits["diagnostic_field_characters"]
        or any(ord(char) < 32 or ord(char) == 127 for char in invocation.event_id)
    ):
        _fail(
            "INVOCATION_PROVENANCE_UNAVAILABLE",
            "authenticated event identity is invalid",
            contract,
        )
    tokens = invocation.tokens
    if not isinstance(tokens, tuple) or any(
        not isinstance(item, str) for item in tokens
    ):
        _fail(
            "ARGUMENT_TAIL_UNAVAILABLE",
            "host did not provide an immutable structured token sequence",
            contract,
        )
    if len(tokens) > contract.limits["router_tokens"]:
        _fail("LIMIT_EXCEEDED", "router token limit exceeded", contract)
    if len(_canonical_json(tokens)) > contract.limits["serialized_message_bytes"]:
        _fail("LIMIT_EXCEEDED", "router argument byte limit exceeded", contract)
    if not tokens:
        return ParsedRequest("help_index", None, None, ())

    first = tokens[0]
    if first == "help":
        if len(tokens) == 1:
            return ParsedRequest("help_index", None, None, ())
        if len(tokens) != 2:
            _fail(
                "INVOCATION_GRAMMAR_INVALID",
                "help accepts at most one command name",
                contract,
            )
        public_name = _validate_name(tokens[1], contract)
        return ParsedRequest(
            "help_command",
            f"{contract.router['command_prefix']}{public_name}",
            public_name,
            (),
        )
    if first == "skill":
        if len(tokens) == 1:
            return ParsedRequest("skill_index", None, None, ())
        resource_id = _validate_name(tokens[1], contract)
        if not resource_id.startswith(cast(str, contract.router["command_prefix"])):
            _fail(
                "INVOCATION_GRAMMAR_INVALID",
                "skill invocation requires an exact canonical lp identifier",
                contract,
            )
        return ParsedRequest(
            "skill",
            resource_id,
            resource_id,
            tuple(tokens[2:]),
        )
    public_name = _validate_name(first, contract)
    return ParsedRequest(
        "command",
        f"{contract.router['command_prefix']}{public_name}",
        public_name,
        tuple(tokens[1:]),
    )


def generate_dialect_preamble(protocol: Any, node: Any) -> str:
    """Generate a version-bound preamble without copying canonical Markdown."""
    required = set(node.capabilities.required)
    mappings = []
    for name, item in sorted(protocol.canonical_dialect.items()):
        if item["required_capability"] in required:
            mappings.append(
                {
                    "name": name,
                    "source_construct": item["source_construct"],
                    "typed_operation": item["typed_operation"],
                    "required_capability": item["required_capability"],
                }
            )
    payload = {
        "protocol_id": protocol.protocol_id,
        "protocol_version": protocol.protocol_version,
        "protocol_digest": protocol.digest,
        "resource": {
            "id": node.id,
            "kind": node.kind,
            "source_digest": node.source_digest,
            "metadata_digest": node.metadata_digest,
            "aggregate_digest": node.aggregate_digest,
        },
        "rules": {
            "arguments": "untrusted_structured_data",
            "canonical_markdown": "opaque_digest_pinned_instructions",
            "unknown_host_construct": "block",
        },
        "typed_mappings": mappings,
    }
    return "LAUNCHPAD_CODEX_DIALECT\n" + _canonical_json(payload).decode("utf-8")


class RouterSession:
    """Immutable router view refreshed only through an explicit session boundary."""

    def __init__(
        self,
        resolver: Any,
        support_bundle: Any,
        host: HostEnvironment,
        *,
        project_root: Path | None = None,
        allow_test_candidate: bool = False,
    ) -> None:
        self.resolver = resolver
        self.protocol = resolver.protocol
        self.support_bundle = support_bundle
        self.host = self._normalize_host(host)
        self.project_root = project_root
        self.allow_test_candidate = allow_test_candidate
        self._validate_support_bundle(support_bundle)
        self.catalog = resolver.catalog(project_root)

    def _normalize_host(self, host: HostEnvironment) -> HostEnvironment:
        maximum = self.protocol.limits["diagnostic_field_characters"]
        for value in (host.host, host.operating_system):
            if (
                not isinstance(value, str)
                or not value
                or len(value) > maximum
                or any(ord(char) < 32 or ord(char) == 127 for char in value)
            ):
                _fail("RECORD_INVALID", "host identity is invalid", self.protocol)
        if (
            not isinstance(host.capabilities, tuple)
            or host.capabilities != tuple(sorted(set(host.capabilities)))
            or set(host.capabilities) - self.protocol.capability_ids
        ):
            _fail("RECORD_INVALID", "host capabilities are invalid", self.protocol)
        if not isinstance(host.tool_versions, Mapping) or any(
            not isinstance(key, str)
            or not key
            or not isinstance(value, str)
            or len(key) > maximum
            or len(value) > maximum
            or any(ord(char) < 32 or ord(char) == 127 for char in key + value)
            for key, value in host.tool_versions.items()
        ):
            _fail("RECORD_INVALID", "host tool versions are invalid", self.protocol)
        return HostEnvironment(
            host=host.host,
            operating_system=host.operating_system,
            capabilities=host.capabilities,
            tool_versions=MappingProxyType(dict(sorted(host.tool_versions.items()))),
        )

    @classmethod
    def for_test(
        cls,
        plugin_root: Path,
        support_bundle: Any,
        host: HostEnvironment,
        *,
        project_root: Path | None = None,
    ) -> RouterSession:
        return cls(
            _RESOLVER.SecureResolver.for_test(plugin_root),
            support_bundle,
            host,
            project_root=project_root,
            allow_test_candidate=True,
        )

    @classmethod
    def installed(
        cls,
        host: HostEnvironment,
        *,
        project_root: Path | None = None,
    ) -> RouterSession:
        """Open release evidence only after the host verified the bootstrap chain."""
        resolver = _RESOLVER.SecureResolver()
        evidence = PLUGIN_ROOT / "codex" / "support-evidence.json"
        try:
            bundle = _SUPPORT.load_bundle(evidence)
        except (OSError, _SUPPORT.SupportError) as exc:
            raise RouterError(
                "SUPPORT_EVIDENCE_UNAVAILABLE",
                "release support evidence is unavailable",
                resolver.protocol,
            ) from exc
        return cls(resolver, bundle, host, project_root=project_root)

    def _validate_support_bundle(self, bundle: Any) -> None:
        runtime = bundle.runtime
        if (
            runtime.protocol_version != self.protocol.protocol_version
            or runtime.protocol_digest != self.protocol.digest
        ):
            _fail(
                "INTEGRITY_MISMATCH",
                "support evidence binds another protocol",
                self.protocol,
            )
        if runtime.stage != "release" and not (
            self.allow_test_candidate and runtime.stage == "test_candidate"
        ):
            _fail(
                "RECORD_STAGE_INVALID",
                "router requires release evidence outside disposable tests",
                self.protocol,
            )

    def refresh(self, support_bundle: Any | None = None) -> None:
        """Refresh the catalog and optionally replace evidence as one boundary."""
        if support_bundle is not None:
            self._validate_support_bundle(support_bundle)
            self.support_bundle = support_bundle
        self.resolver.refresh()
        self.catalog = self.resolver.catalog(self.project_root)

    def _bounded_message(self, value: str) -> str:
        cleaned = "".join(
            char if ord(char) >= 32 and ord(char) != 127 else "?" for char in value
        )
        return cleaned[: self.protocol.limits["diagnostic_field_characters"]]

    def _entry_diagnostics(self, resource_id: str, kind: str) -> dict[str, object]:
        try:
            diagnostic = _SUPPORT.build_entry_diagnostics(
                self.support_bundle,
                resource_id,
                host=self.host.host,
                operating_system=self.host.operating_system,
                capabilities=self.host.capabilities,
                tool_versions=self.host.tool_versions,
                contract=self.protocol,
            )
            result = cast(dict[str, object], dataclasses.asdict(diagnostic))
            if result["kind"] != kind:
                _fail(
                    "INTEGRITY_MISMATCH",
                    "catalog and support evidence disagree on resource kind",
                    self.protocol,
                )
            return result
        except _SUPPORT.SupportError:
            return {
                "resource_id": resource_id,
                "kind": kind,
                "base_support_state": "blocked",
                "effective_availability": "blocked",
                "reason_codes": ("SUPPORT_EVIDENCE_UNAVAILABLE",),
                "required_capabilities": (),
                "mutation": "none",
                "interaction": "none",
                "external_data_egress": False,
                "tool_profile": "inspect_only",
                "fallback": "inspect_only",
                "qualification_ids": (),
                "authoritative_cost_available": False,
                "estimated_input_tokens_ceiling": 0,
                "estimated_output_tokens_ceiling": 0,
                "maximum_child_starts": 0,
                "maximum_workers": 0,
                "maximum_wave_duration_seconds": 0,
                "maximum_run_duration_seconds": 0,
                "recovery": "Refresh or reinstall a verified LaunchPad package.",
                "reporting_class": "private_security",
            }

    def _help_index(self) -> RouterResponse:
        commands = [
            self._entry_diagnostics(item.resource_id, "command")
            for item in self.catalog.commands.values()
        ]
        skills = [
            self._entry_diagnostics(item.resource_id, "skill")
            for item in self.catalog.skills.values()
            if item.user_invocable
        ]
        return self._response(
            "ok",
            "help_index",
            None,
            {
                "usage": (
                    "$lp help",
                    "$lp help <command>",
                    "$lp <command> [arguments...]",
                    "$lp skill <canonical-id> [arguments...]",
                ),
                "release_stage": self.support_bundle.runtime.release_stage,
                "commands": commands,
                "skills": skills,
                "invalid_entries": tuple(
                    self._bounded_message(item) for item in self.catalog.invalid_entries
                ),
                "warnings": tuple(
                    self._bounded_message(item) for item in self.catalog.warnings
                ),
            },
        )

    def _help_command(self, request: ParsedRequest) -> RouterResponse:
        assert request.resource_id is not None
        try:
            source = self.resolver.resolve(
                "command",
                request.resource_id,
                project_root=self.project_root,
                internal=False,
            )
        except _RESOLVER.ResolverError as exc:
            public_names = [
                item.removeprefix(cast(str, self.protocol.router["command_prefix"]))
                for item in self.catalog.commands
            ]
            suggestions = tuple(
                difflib.get_close_matches(request.public_name or "", public_names, n=3)
            )
            return self._response(
                "error",
                "help_command",
                exc.code,
                {
                    "message": self._bounded_message(str(exc)),
                    "suggestions": suggestions,
                    "suggestions_execute": False,
                },
            )
        return self._response(
            "ok",
            "help_command",
            None,
            {"entry": self._entry_diagnostics(source.resource_id, "command")},
        )

    def _skill_index(self) -> RouterResponse:
        skills = [
            self._entry_diagnostics(item.resource_id, "skill")
            for item in self.catalog.skills.values()
            if item.user_invocable
        ]
        return self._response("ok", "skill_index", None, {"skills": skills})

    def _execute(self, request: ParsedRequest) -> RouterResponse:
        assert request.resource_id is not None
        kind = "skill" if request.action == "skill" else "command"
        try:
            source = self.resolver.resolve(
                kind,
                request.resource_id,
                project_root=self.project_root,
                internal=False,
            )
        except _RESOLVER.ResolverError as exc:
            return self._response(
                "error",
                request.action,
                exc.code,
                {"message": self._bounded_message(str(exc))},
            )
        diagnostic = self._entry_diagnostics(source.resource_id, kind)
        if (
            diagnostic["mutation"] != "none"
            or cast(int, diagnostic["maximum_child_starts"]) != 0
        ):
            return self._response(
                "blocked",
                request.action,
                "OPERATION_AUTHORIZATION_UNAVAILABLE",
                {"entry": diagnostic},
            )
        required_boundary = set(
            cast(
                Sequence[str],
                self.protocol.router["zero_mutation_required_capabilities"],
            )
        )
        if not required_boundary.issubset(self.host.capabilities):
            return self._response(
                "blocked",
                request.action,
                "CAPABILITY_BLOCKED",
                {"entry": diagnostic},
            )
        if diagnostic["effective_availability"] != "available":
            reasons = cast(Sequence[str], diagnostic["reason_codes"])
            return self._response(
                "blocked",
                request.action,
                reasons[0] if reasons else "CAPABILITY_BLOCKED",
                {"entry": diagnostic},
            )
        nodes = {item.id: item for item in self.support_bundle.runtime.nodes}
        node = nodes.get(source.resource_id)
        if node is None or node.source_digest != source.source_digest:
            return self._response(
                "blocked",
                request.action,
                "INTEGRITY_MISMATCH",
                {"entry": diagnostic},
            )
        try:
            canonical = self.resolver.read(source, expected_digest=node.source_digest)
        except _RESOLVER.ResolverError as exc:
            return self._response(
                "blocked",
                request.action,
                exc.code,
                {"entry": diagnostic},
            )
        return self._response(
            "ready",
            request.action,
            None,
            {
                "entry": diagnostic,
                "canonical_document": canonical.content,
                "canonical_source_digest": canonical.record.source_digest,
                "dialect_preamble": generate_dialect_preamble(self.protocol, node),
                "argument_tail": request.arguments,
                "argument_digest": _sha256(_canonical_json(request.arguments)),
            },
        )

    def _response(
        self,
        status: str,
        action: str,
        code: str | None,
        payload: Mapping[str, object],
    ) -> RouterResponse:
        classification = (
            self.protocol.reporting_class_for_error(code)
            if code is not None
            else "public_bug"
        )
        return RouterResponse(
            status=status,
            action=action,
            code=code,
            reporting_class=classification,
            protocol_version=self.protocol.protocol_version,
            payload=payload,
        )

    def route(self, event: object, verifier: InvocationVerifier) -> RouterResponse:
        """Authenticate, parse, and route one event without retaining run state."""
        try:
            verified = verifier.verify(event)
            request = parse_verified_invocation(verified, self.protocol)
        except RouterError as exc:
            return self._response(
                "blocked",
                "authenticate",
                exc.code,
                {
                    "message": (
                        "LaunchPad blocked this request at an authentication boundary."
                        if exc.reporting_class == "private_security"
                        else self._bounded_message(str(exc))
                    )
                },
            )
        try:
            if request.action == "help_index":
                return self._help_index()
            if request.action == "help_command":
                return self._help_command(request)
            if request.action == "skill_index":
                return self._skill_index()
            return self._execute(request)
        except (RouterError, _RESOLVER.ResolverError, _SUPPORT.SupportError) as exc:
            return self._response(
                "blocked",
                request.action,
                exc.code,
                {"message": "LaunchPad blocked an invalid or stale adapter record."},
            )


def render_response(response: RouterResponse) -> str:
    """Render a bounded user-facing view without executing response content."""
    if response.action == "help_index" and response.status == "ok":
        commands = cast(Sequence[Mapping[str, object]], response.payload["commands"])
        skills = cast(Sequence[Mapping[str, object]], response.payload["skills"])
        lines = [
            "LaunchPad for Codex",
            f"Protocol: {response.protocol_version}",
            "",
            "Commands:",
        ]
        lines.extend(
            f"- {item['resource_id']}: {item['effective_availability']}"
            for item in commands
        )
        lines.extend(("", "User-invocable skills:"))
        lines.extend(
            f"- {item['resource_id']}: {item['effective_availability']}"
            for item in skills
        )
        invalid = cast(Sequence[str], response.payload["invalid_entries"])
        if invalid:
            lines.extend(("", "Invalid entries:"))
            lines.extend(f"- {item}" for item in invalid)
        return "\n".join(lines)
    if response.action == "help_command" and response.status == "ok":
        entry = cast(Mapping[str, object], response.payload["entry"])
        return "\n".join(
            (
                str(entry["resource_id"]),
                f"Required adapter protocol: {response.protocol_version}",
                f"Base support: {entry['base_support_state']}",
                f"Current availability: {entry['effective_availability']}",
                f"Mutation: {entry['mutation']}",
                f"Interaction: {entry['interaction']}",
                f"External data egress: {str(entry['external_data_egress']).lower()}",
                f"Tool profile: {entry['tool_profile']}",
                f"Fallback: {entry['fallback']}",
                f"Requirements: {', '.join(cast(Sequence[str], entry['required_capabilities']))}",
                f"Qualifications: {', '.join(cast(Sequence[str], entry['qualification_ids'])) or 'none'}",
                f"Authoritative cost available: {str(entry['authoritative_cost_available']).lower()}",
                f"Estimated input token ceiling: {entry['estimated_input_tokens_ceiling']}",
                f"Estimated output token ceiling: {entry['estimated_output_tokens_ceiling']}",
                f"Maximum child starts: {entry['maximum_child_starts']}",
                f"Maximum workers: {entry['maximum_workers']}",
                f"Maximum wave duration seconds: {entry['maximum_wave_duration_seconds']}",
                f"Maximum run duration seconds: {entry['maximum_run_duration_seconds']}",
                f"Reason codes: {', '.join(cast(Sequence[str], entry['reason_codes'])) or 'none'}",
                f"Recovery: {entry['recovery']}",
            )
        )
    if response.status == "ready":
        entry = cast(Mapping[str, object], response.payload["entry"])
        return f"Prepared {entry['resource_id']} from its digest-pinned canonical definition."
    code = response.code or "UNKNOWN_ERROR"
    entry_value = response.payload.get("entry")
    if isinstance(entry_value, Mapping):
        entry = cast(Mapping[str, object], entry_value)
        resource_id = str(entry["resource_id"])
        equivalent = (
            f"/{resource_id}"
            if entry.get("kind") == "command"
            else f"canonical skill {resource_id}"
        )
        guidance = (
            "Use private security reporting."
            if response.reporting_class == "private_security"
            else "Use the public issue tracker."
        )
        return "\n".join(
            (
                f"{resource_id} is blocked.",
                f"Code: {code}",
                f"Required adapter protocol: {response.protocol_version}",
                f"Mutation: {entry['mutation']}",
                f"Fallback: {entry['fallback']}",
                f"Requirements: {', '.join(cast(Sequence[str], entry['required_capabilities']))}",
                f"Claude equivalent: {equivalent}",
                f"Recovery: {entry['recovery']}",
                f"Reporting: {guidance}",
            )
        )
    return f"LaunchPad request blocked: {code}"


__all__ = [
    "HostEnvironment",
    "InvocationVerifier",
    "ParsedRequest",
    "RouterError",
    "RouterResponse",
    "RouterSession",
    "VerifiedInvocation",
    "generate_dialect_preamble",
    "parse_verified_invocation",
    "render_response",
    "response_as_dict",
]
