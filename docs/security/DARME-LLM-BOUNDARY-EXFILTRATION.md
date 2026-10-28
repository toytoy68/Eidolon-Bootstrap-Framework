# DARME — LLM boundary & exfiltration controls (draft v0.1)

Status: development specification; **not deployed**. Tracking: #3.

## Trust boundary
Core is the only orchestrator. LLM inference processes receive prompts and return untrusted text/structured proposals. No LLM output is executable authority. No model-provided path, hostname, command or permission can override Core policy.

## Enforcement requirements
1. Explicit allowlisted tool schemas, canonicalized arguments and authenticated user/session authorization at Core dispatch. Reject unknown tools, shell metacharacter tricks, encoded payloads and unsafe paths; avoid generic shell execution for model-generated content.
2. Enforce filesystem and network restrictions at OS/process boundary, not only application checks. Deny outbound traffic by default from inference and sandboxed tool workers; allow required internal endpoints explicitly. Separate Core control plane from untrusted workers.
3. DARME consumes actual process/network/file events and authorization decisions, correlates by immutable request ID, and detects mismatches. Reasoning traces are diagnostic only, never a security control.
4. On denied actions: no side effect; structured denial + audit record; no automatic privilege escalation or retries with different tools.
5. Keep auditable evidence: timestamp, principal, tool, canonical args digest (avoid secrets), policy revision, decision, execution outcome and sensor observation. Ensure tamper-resistant storage/rotation and distinguish missing telemetry from clean status.

## Validation matrix (offline, synthetic)
- LLM asks for unauthorized read, command, network POST/PUT, DNS tunnel, encoded destination, and prompt-injection induced tool use: denied, no side effect.
- Authorized read-only action works; legitimate internal model calls continue.
- Tool-worker network attempt blocked by OS even if application policy is bypassed.
- Sensor outage results in degraded/unknown alert, never green.
- Audit correlation survives restart and rejects fabricated reasoning claims.
- Re-run regression on Core, then separately on X399 Eidolon-OS after connectivity returns.

## Rollout
Inventory actual Core/DARME service permissions and tool dispatch first; add tests before enforcement. Stage behind a feature flag, run on isolated fixtures, inspect false positives, then enable only after explicit verified results. Do not assume current protections are sufficient without evidence.
