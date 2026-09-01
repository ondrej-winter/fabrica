# Fetch Web Content Tool Implementation Plan

## Status

- **Plan status:** Ready.
- **Last reviewed:** September 1, 2026.
- **Created:** September 1, 2026.
- **Canonical specification:** `docs/specs/tools-fetch-web-content-tool-spec.md`.
- **Scope:** Implement the accepted, read-only `fetch_web_content` public HTTPS
  retrieval tool without changing its accepted Version 1 contract.

## Objective

Deliver a model-callable `fetch_web_content` tool that retrieves known public
HTTPS URLs through a bounded, SSRF-safe, deterministic retrieval boundary. The
runtime retrieves and normalizes untrusted textual web content; the agent does
the reasoning.

The implementation must support GET-only retrieval of public HTTPS pages and
textual endpoints, validate every initial and redirect destination, manually
control redirects, stream decoded response data within limits, normalize
supported textual content, return structured per-request results in input order,
and mark all fetched content as `untrusted_web_content`.

## Scope

### In scope

- Canonical public schema:
  `{"requests": [{"url": "...", "max_chars": ...}]}`.
- HTTPS-only, GET-only retrieval of known URLs.
- Host-controlled web-access enablement, request headers, timeout, retry, and
  concurrency bounds.
- URL validation, embedded-credential rejection, DNS resolution, and all-address
  SSRF validation through `ipaddress`.
- Manual redirect handling with redirect-by-redirect URL and destination checks.
- Streaming decoded/decompressed response-size enforcement.
- Supported textual MIME classification, bounded binary sniffing, charset
  decoding, HTML-to-Markdown conversion, JSON formatting, and XML/text handling.
- Per-request and aggregate content limits while retaining full result metadata.
- Registered-tool adapter, bootstrap composition, offline tests, README updates,
  dependency update, and full quality gate.

### Out of scope

- HTTP support, model-controlled methods, headers, cookies, authentication,
  request bodies, proxies, TLS controls, or generic API-client behavior.
- Browser automation, JavaScript execution, web search, PDFs, Office documents,
  images, audio/video, archives, and authenticated connectors.
- Connection-level DNS address pinning or a claim of complete DNS-rebinding
  protection.
- Live-network tests in the default local or CI test suite.
- Refactoring the existing generic HTTPX retry wrapper unless a separately
  accepted reuse need emerges.

## Architecture and ownership

Create a dedicated vertical slice at:

```text
src/fabrica/features/web_content_fetching/
├── application/
│   ├── dtos/
│   ├── ports/
│   ├── use_cases/
│   ├── result_formatting.py
│   └── result_limiting.py
└── adapters/
    ├── inbound/registered_tool/
    └── outbound/
        ├── network_policy/
        ├── httpx_fetcher/
        └── content_processing/
```

The slice application layer owns commands, results, limits, stable error codes,
and ports. Outbound adapters own DNS, `httpx`, URL/destination policy support,
streaming, MIME sniffing, decoding, and `markdownify` integration. The inbound
registered-tool adapter owns the model schema and conversion to/from the agent
runtime’s registered-tool DTOs. Bootstrap owns construction and host policy
injection.

The existing generic adapter at `src/fabrica/adapters/outbound/httpx_client/`
must not be extended for the first implementation. It materializes response text
and does not expose the manual redirects, pre-request DNS checks, streamed decoded
body limits, and response-closure behavior required by this tool.

## Dependency graph

```text
Runtime dependency and package skeleton
        ↓
Application DTOs, errors, ports, and limits
        ↓
URL/DNS/destination policy + content processing
        ↓
Streaming HTTPX fetch and redirect handling
        ↓
Batch orchestration + aggregate output limiting
        ↓
Registered-tool schema and result mapping
        ↓
Bootstrap composition and public exports
        ↓
Offline integration tests, docs, and full quality gate
```

## Progress tracking

Update this dashboard and the matching detailed task when work is completed,
blocked, re-sequenced, or expanded. A task is complete only after all of its
acceptance and verification items are complete.

- [x] FWC-01 — Dependency and feature-slice skeleton.
- [x] FWC-02 — Application DTOs, limits, errors, and ports.
- [x] FWC-03 — URL, DNS, and public-destination policy.
- [x] FWC-04 — Content classification, decoding, extraction, and per-request limits.
- [x] FWC-05 — Streaming HTTPX transport and manual redirects.
- [x] FWC-06 — Batch orchestration, retries, and aggregate output limiting.
- [x] FWC-07 — Registered-tool adapter and canonical schema.
- [x] FWC-08 — Bootstrap composition and host access policy.
- [x] FWC-09 — Acceptance coverage, documentation, and full validation.
- [x] FWC-CP1 — Contract/policy checkpoint before transport implementation.
- [x] FWC-CP2 — Runtime-composition checkpoint before handoff.

## Ordered implementation tasks

### FWC-01 — Add the dependency and establish the feature-slice skeleton

**Dependencies:** None.

**Likely files**

- `pyproject.toml`
- `uv.lock`
- `src/fabrica/features/web_content_fetching/**/__init__.py`
- `tests/unit/features/web_content_fetching/**/__init__.py`
- `tests/integration/features/web_content_fetching/**/__init__.py`

**Work**

1. Add `markdownify` as an explicit runtime dependency and synchronize `uv.lock`.
   Pin or constrain it only as required by the resolved graph; confirm the
   accepted standard-library `html.parser` conversion path does not introduce an
   unaccepted parser dependency.
2. Create the new `web_content_fetching` feature package with application,
   inbound-adapter, outbound-adapter, unit-test, and integration-test package
   structure.
3. Keep package initializers lightweight and free from construction, DNS, or
   network I/O.

**Acceptance criteria**

- `markdownify` is a direct runtime dependency.
- `pyproject.toml` and `uv.lock` describe the same resolved dependency change.
- The slice follows the existing feature-slice conventions.
- Importing any new package performs no fetch, DNS lookup, or HTTP client setup.

**Verification**

- [ ] `uv lock` succeeds.
- [ ] A focused import test passes.

---

### FWC-02 — Define immutable application contracts, limits, errors, and ports

**Dependencies:** FWC-01.

**Likely files**

- `src/fabrica/features/web_content_fetching/application/dtos/fetch_web_content.py`
- `src/fabrica/features/web_content_fetching/application/ports/web_content_fetching.py`
- `src/fabrica/features/web_content_fetching/application/dtos/__init__.py`
- `src/fabrica/features/web_content_fetching/application/ports/__init__.py`
- `tests/unit/features/web_content_fetching/application/test_fetch_web_content_dtos.py`
- `tests/unit/features/web_content_fetching/application/test_ports.py`

**Work**

1. Add immutable request, command, redirect, error, success/failure, and batch
   result DTOs.
2. Define accepted defaults and configurable host bounds:
   - eight requests per call;
   - four concurrent fetches;
   - 30-second per-request deadline;
   - one retry;
   - five redirects;
   - 5,000,000 decoded bytes;
   - 48,000 content characters per request;
   - 96,000 aggregate content characters.
3. Define all accepted stable `FetchErrorCode` values.
4. Define the inbound fetch port, a host context carrying cancellation, deadline,
   limits, and `public_web_enabled: bool`, plus narrow outbound DNS/fetch ports.
   Disabled public web access must return one ordered `PUBLIC_WEB_DISABLED`
   result per request without DNS, HTTP, or extraction work.
5. Define the offline transport seam: the outbound fetch port owns one
   already-validated request attempt and returns a typed attempt outcome; the
   HTTPX adapter receives an injected async-client/transport factory so adapter
   tests can use `httpx.MockTransport` without live DNS or network access.
6. Define typed transient-failure metadata for retryable conditions, including an
   optional parsed and capped `retry_after_seconds`. The application owns
   deadline-aware waiting and never sleeps after cancellation.
7. Define serialized-result delivery bounds separately from content bounds. The
   formatter/limiter must reserve JSON structural and escaping overhead, produce
   no more than 40 `ToolTextContent` parts of at most 48,000 characters each, and
   never rely on the runtime's 20,000-character observation summary to retain
   required metadata.
8. Require every result to carry the fixed trust marker
   `untrusted_web_content`.

**Acceptance criteria**

- Invalid bounds, invalid request shapes, and impossible result states fail fast.
- Public DTOs contain no HTTPX, provider, or framework transport types.
- DTOs can represent every accepted success and failure contract field.
- Every result retains requested URL and trust; known final URL, status,
  redirects, and content metadata survive later-stage failures. Failures cannot
  contain inconsistent success content fields, and successful `204` responses can
  represent empty content and zero counts.
- Error messages are bounded and do not expose local DNS, network, or transport
  implementation detail.

**Verification**

- [ ] DTO invariant tests pass.
- [ ] Port/context contract tests pass.
- [ ] `uv run pytest tests/unit/features/web_content_fetching/application/` passes.

---

### FWC-03 — Implement URL, DNS, and destination policy

**Dependencies:** FWC-02.

**Likely files**

- `src/fabrica/features/web_content_fetching/application/validation.py`
- `src/fabrica/features/web_content_fetching/adapters/outbound/network_policy/url_policy.py`
- `src/fabrica/features/web_content_fetching/adapters/outbound/network_policy/destination_policy.py`
- `src/fabrica/features/web_content_fetching/adapters/outbound/network_policy/dns_resolver.py`
- `tests/unit/features/web_content_fetching/application/test_validation.py`
- `tests/unit/features/web_content_fetching/adapters/outbound/network_policy/test_url_policy.py`
- `tests/unit/features/web_content_fetching/adapters/outbound/network_policy/test_destination_policy.py`
- `tests/unit/features/web_content_fetching/adapters/outbound/network_policy/test_dns_resolver.py`

**Work**

1. Parse and normalize URL inputs without network I/O.
2. Reject malformed URLs, unsupported protocols, plain HTTP, and embedded URL
   credentials before DNS resolution.
3. Support valid Unicode hostname, punycode hostname, IPv4 literal, and IPv6
   literal inputs.
4. Implement an injectable async DNS resolver using `asyncio.getaddrinfo` in the
   production adapter.
5. Validate **every** returned address with standard-library `ipaddress`, allowing
   only globally routable addresses.
6. Reject loopback, private, link-local, multicast, unspecified, reserved,
   carrier-grade NAT, benchmark/internal-use, and IPv4-mapped forbidden IPv6
   destinations.
7. Reject a DNS answer set if any answer is not allowed, including mixed
   public/private answers.
8. Ensure the same complete policy pipeline can be called for each redirect.

**Acceptance criteria**

- HTTP URLs are rejected before DNS resolver invocation.
- `localhost`, private literals, and public-looking names resolving to internal
  addresses fail with `DESTINATION_NOT_ALLOWED`.
- Resolver errors become `DNS_FAILED` without leaking sensitive local network
  details to the model.
- The implementation does not rely on a hand-maintained CIDR deny list as its
  primary policy.
- IPv4 and IPv6 literals, Unicode/punycode hostname equivalence, empty DNS
  answers, and mixed IPv4/IPv6 answer sets have deterministic outcomes. A mixed
  answer set succeeds only when every resolved address is globally routable.

**Verification**

- [x] Unit matrix covers all URL and SSRF cases in the specification.
- [x] Mixed public/private DNS resolution is rejected.
- [x] DNS is re-resolved for independently validated follow-up requests.

---

### FWC-04 — Implement content classification, decoding, extraction, and per-request limits

**Dependencies:** FWC-02. Can proceed in parallel with FWC-03 after contracts
are stable.

**Likely files**

- `src/fabrica/features/web_content_fetching/adapters/outbound/content_processing/classification.py`
- `src/fabrica/features/web_content_fetching/adapters/outbound/content_processing/decoding.py`
- `src/fabrica/features/web_content_fetching/adapters/outbound/content_processing/extraction.py`
- `src/fabrica/features/web_content_fetching/adapters/outbound/content_processing/output_limiting.py`
- `tests/unit/features/web_content_fetching/adapters/outbound/content_processing/test_classification.py`
- `tests/unit/features/web_content_fetching/adapters/outbound/content_processing/test_decoding.py`
- `tests/unit/features/web_content_fetching/adapters/outbound/content_processing/test_extraction.py`
- `tests/unit/features/web_content_fetching/adapters/outbound/content_processing/test_output_limiting.py`
- HTML/JSON fixtures in `tests/fixtures/web_content_fetching/` or an established
  equivalent.

**Work**

1. Parse raw `Content-Type` metadata into media type and charset.
2. Use a bounded byte sample to detect obvious binary content even when headers
   claim a textual type.
3. Support accepted textual families: HTML/XHTML, `text/*`, Markdown, JSON and
   `application/*+json`, and XML.
4. Reject binary types such as images, archives, executables, PDFs, Office files,
   `application/octet-stream`, and unknown binary content.
5. Decode with BOM → declared charset → UTF-8 fallback; return
   `UNSUPPORTED_ENCODING` on unreliable decoding.
6. Process HTML with a real parser: remove comments, `script`, `style`, and
   `noscript`; use `markdownify` with `html.parser`; preserve headings, code,
   tables, and links; resolve relative links against final URL.
7. Parse and deterministically pretty-print JSON. Preserve textual invalid JSON
   with `parse_warning: "INVALID_JSON"` when MIME says JSON.
8. Conservatively normalize XML, Markdown, and plain text.
9. Apply explicit head-preserving per-request content truncation and update
   content/returned/truncation metadata.

**Acceptance criteria**

- No regex-based HTML stripping is used.
- JSON MIME with invalid but textual content is not represented as valid JSON.
- Binary bodies cannot be exposed as arbitrary UTF-8 model text.
- Truncation is always explicit.

**Verification**

- [x] Fixtures cover headings, code blocks, tables, relative links, malformed HTML,
  script/style removal, JSON, XML, Markdown, and plain text.
- [x] MIME/sniffing and charset test matrices pass.

---

### FWC-CP1 — Validate the policy and content boundary before transport work

**Dependencies:** FWC-03 and FWC-04.

**Checkpoint**

- [x] Confirm URL validation, DNS classification, extraction, and output limiting
  are independently testable and contain no HTTP client calls.
- [x] Confirm all accepted error codes have an intended producing component.
- [x] Confirm no implementation claims connection-level DNS pinning or complete
  DNS-rebinding protection.

---

### FWC-05 — Implement streaming HTTPX transport and manual redirect handling

**Dependencies:** FWC-CP1.

**Likely files**

- `src/fabrica/features/web_content_fetching/adapters/outbound/httpx_fetcher/adapter.py`
- `src/fabrica/features/web_content_fetching/adapters/outbound/httpx_fetcher/streaming.py`
- `src/fabrica/features/web_content_fetching/adapters/outbound/httpx_fetcher/redirects.py`
- `src/fabrica/features/web_content_fetching/adapters/outbound/httpx_fetcher/exceptions.py`
- `tests/unit/features/web_content_fetching/adapters/outbound/httpx_fetcher/test_adapter.py`
- `tests/unit/features/web_content_fetching/adapters/outbound/httpx_fetcher/test_streaming.py`
- `tests/unit/features/web_content_fetching/adapters/outbound/httpx_fetcher/test_redirects.py`

**Work**

1. Create a slice-owned `httpx.AsyncClient` adapter with redirects disabled,
   no cookie jar, GET-only requests, and host-controlled safe headers.
2. Resolve/validate destination addresses before every initial request and every
   redirect request.
3. Stream the decoded/decompressed response body while enforcing the 5 MB decoded
   byte limit. Use `Content-Length` only as an early optimization; never trust it
   as the sole limit.
4. Ensure every response stream closes on success, timeout, cancellation,
   redirect, and response-size rejection.
5. Handle redirect statuses manually, resolve relative locations, preserve ordered
   redirect history, enforce a maximum of five redirects, and rerun the full
   validation pipeline for each destination.
6. Reject HTTPS-to-HTTP redirects with `INSECURE_REDIRECT`.
7. Convert non-success HTTP statuses to structured `HTTP_ERROR` failures while
   retaining available status/final-URL/redirect metadata.
8. Classify HTTPX connection, TLS, cancellation, and timeout conditions into
   stable fetch errors.

**Acceptance criteria**

- Automatic HTTP-client redirect following cannot bypass policy.
- `RESPONSE_TOO_LARGE` stops body consumption and closes the stream.
- User cancellation produces `FETCH_CANCELLED`; deadline expiry produces
  `FETCH_TIMEOUT`.
- V1 validates pre-request DNS but does not state or imply address pinning.

**Verification**

- [x] Offline HTTPX transport tests cover status, redirect, stream closure, and
  failure mapping.
- [x] Tests cover lying/missing `Content-Length` and compressed data that expands
  above the decoded-byte limit.

---

### FWC-06 — Implement batch orchestration, retry policy, and aggregate output limiting

**Dependencies:** FWC-05.

**Likely files**

- `src/fabrica/features/web_content_fetching/application/use_cases/fetch_web_content.py`
- `src/fabrica/features/web_content_fetching/application/result_limiting.py`
- `src/fabrica/features/web_content_fetching/application/result_formatting.py`
- `tests/unit/features/web_content_fetching/application/test_fetch_web_content.py`
- `tests/unit/features/web_content_fetching/application/test_result_limiting.py`
- `tests/unit/features/web_content_fetching/application/test_result_formatting.py`

**Work**

1. Schedule independent requests with a maximum concurrency of four.
2. Preserve input order while allowing completion order to differ.
3. Isolate request failures and retain per-request result objects for all inputs.
4. Respect the earliest of the host phase deadline and configured per-request
   deadline across DNS, connection, redirects, download, and extraction.
5. Propagate cancellation to active work and produce ordered cancellation outcomes
   for queued work.
6. Retry at most once only for typed transient DNS/connection conditions and HTTP
   408/429/502/503/504. Parse `Retry-After` into the adapter-provided capped delay;
   wait only while remaining request and batch deadlines permit it, and abort the
   wait immediately on cancellation.
7. Never retry policy failures, ordinary deterministic 4xx responses, decoding or
   MIME errors, response-size errors, or cancellation.
8. Allocate the 96,000 aggregate content budget after complete per-request results
   exist. Retain all metadata and trim only content, setting per-result truncation
   fields and top-level `batch_content_truncated`.
9. Format deterministic compact JSON payloads and apply a serialized-payload
   limit after content allocation. Preserve every result object and required
   metadata; when structural overhead requires further reduction, reduce only
   returned content and update truncation metadata before serialization.

**Acceptance criteria**

- Every input has one ordered result.
- Partial failures never fail the whole batch.
- Aggregate limiting retains status, redirect, trust, size, and error metadata.
- The serialized result can be delivered through the runtime’s bounded multipart
  text-content surface without post-serialization metadata loss or invalid part
  count/part length.

**Verification**

- [x] Scheduler tests cover ordering, concurrency cap, partial failures,
  cancellation, and deadline behavior.
- [x] Retry tests distinguish retryable and non-retryable outcomes.
- [x] Aggregate-limit tests preserve every result object and required metadata.
- [x] Worst-case eight-request payload tests cover long URLs, redirect histories,
  errors, escaped content, multipart boundaries, and runtime observation limits.

---

### FWC-07 — Add the model-facing registered-tool adapter

**Dependencies:** FWC-06.

**Likely files**

- `src/fabrica/features/web_content_fetching/adapters/inbound/registered_tool/adapter.py`
- `src/fabrica/features/web_content_fetching/adapters/inbound/registered_tool/__init__.py`
- `tests/unit/features/web_content_fetching/adapters/inbound/registered_tool/test_adapter.py`

**Work**

1. Define `FETCH_WEB_CONTENT_TOOL_NAME = "fetch_web_content"` and its concise
   model-facing description.
2. Define the closed schema with only:
   - a required `requests` array of one to eight objects;
   - required non-empty `url` strings;
   - optional integer `max_chars` between 1,000 and 48,000;
   - `additionalProperties: false` at both levels.
3. Do not expose `prompt`, method, headers, cookies, auth, body, proxy, TLS, or
   any arbitrary client option.
4. Convert runtime arguments to application commands and invalid shapes to
   recoverable `INVALID_ARGUMENTS` registered-tool rejections.
5. Pass cancellation and the `fetch_web_content` phase deadline through context.
6. Serialize the application-provided, already delivery-safe JSON into ordered
   `ToolTextContent` parts without re-limiting or discarding fields; enforce the
   48,000-character part and 40-part runtime bounds and return
   `ToolMutationGuarantee.NO_MUTATION`.

**Acceptance criteria**

- The public protocol is exactly the accepted schema.
- Tool text describes fetched instructions as untrusted data, not agent
  instructions.
- Adapter code contains no DNS, HTTP, or extraction implementation logic.

**Verification**

- [x] Schema closure tests pass.
- [x] Argument mapping/rejection and phase-deadline forwarding tests pass.
- [x] Multipart JSON serialization boundary tests pass.

---

### FWC-08 — Add bootstrap composition and host public-web access policy

**Dependencies:** FWC-07.

**Likely files**

- `src/fabrica/bootstrap/composition/web_content_fetching.py`
- `src/fabrica/bootstrap/composition/__init__.py`
- `src/fabrica/bootstrap/__init__.py`
- `tests/unit/test_bootstrap_api.py`
- `tests/integration/features/web_content_fetching/test_fetch_web_content_tool_composition.py`

**Work**

1. Add a composition factory following the established registered-tool factory
   pattern and a frozen `FetchWebContentToolOptions` object. It must require
   `public_web_enabled`, safe host-owned request headers/User-Agent, limits, a DNS
   resolver, and an async HTTPX client/transport factory; it must not supply a
   permissive web-access default.
2. Pass `public_web_enabled` to the application context for invocation-time
   `PUBLIC_WEB_DISABLED` per-request outcomes. Do not repurpose the unrelated
   command-execution sandbox policy.
3. Inject host-owned limits, User-Agent/header configuration, DNS resolver, and
   transport/client factory as appropriate for deterministic testing.
4. Ensure construction only wires dependencies: it must not resolve DNS, connect,
   fetch, or invoke a model.
5. Add intended composition/public API exports and update public export tests.

**Acceptance criteria**

- The host can disable public web access entirely.
- Disabled access returns ordered `PUBLIC_WEB_DISABLED` results and performs no
  DNS resolution or HTTP transport construction/request work.
- Composition is inert until the tool is invoked.
- No agent-runtime contracts leak into application ports or outbound adapters.

**Verification**

- [x] Composition integration test uses fake DNS and mock/local HTTP transport,
  not public internet access.
- [x] Host-disabled behavior is covered.
- [x] Curated bootstrap export tests pass.

---

### FWC-09 — Complete acceptance coverage, documentation, and full validation

**Dependencies:** FWC-08.

**Likely files**

- `tests/fixtures/web_content_fetching/**`
- `tests/unit/features/web_content_fetching/**`
- `tests/integration/features/web_content_fetching/**`
- `README.md`
- `docs/specs/tools-fetch-web-content-tool-spec.md` only if an accepted-contract
  ambiguity is discovered and re-confirmed.

**Work**

1. Ensure the specification acceptance matrix has test coverage for:
   - URLs and embedded credentials;
   - public, private, mixed, literal, and DNS-failing destinations;
   - redirects, redirect loops, relative locations, and downgrade rejection;
   - required HTTP statuses;
   - response-size, compression, and content-length behavior;
   - HTML, JSON, MIME sniffing, and encodings;
   - batch ordering/concurrency/partial failures;
   - timeout, cancellation, and stream closure;
   - prompt-injection-looking content remaining ordinary untrusted text.
2. Update README onboarding/tool-composition documentation with the explicit
   factory and HTTPS-only/untrusted-content/host-enable semantics.
3. Do not update the canonical spec merely to mirror implementation details;
   update it only for a material accepted-contract correction.
4. Run focused tests first, then the full quality gate.

**Acceptance criteria**

- Default tests are deterministic and offline.
- Every accepted security and result-contract behavior has direct or clearly
  delegated lower-level coverage.
- Documentation does not overstate DNS-rebinding protection or supported content
  families.

**Verification**

- [x] `uv run ruff format .`
- [x] `uv run ruff check .`
- [x] `uv run ty check src tests`
- [x] `uv run lint-imports`
- [x] `uv run pytest`

---

### FWC-CP2 — Runtime composition and handoff checkpoint

**Dependencies:** FWC-09.

**Checkpoint**

- [x] The factory is explicit, inert during construction, and host-web access can
  be disabled.
- [x] The registered schema contains no general HTTP-client controls.
- [x] All fetched content includes `trust: "untrusted_web_content"`.
- [x] The delivery-safe payload fits the registered-tool multipart bounds without
  relying on runtime observation truncation to retain required metadata.
- [x] Full quality gate evidence is recorded.
- [x] Any deferred DNS-pinning/readability/browser work is documented as out of
  scope rather than represented as implemented behavior.

## Sequencing and parallelization

| Work | Constraint |
| --- | --- |
| FWC-01 → FWC-02 | Contracts depend on installed dependency/package structure. |
| FWC-02 → FWC-03/FWC-04 | Policy and extraction require stable DTOs and error codes. |
| FWC-03 + FWC-04 | Safe to parallelize after FWC-02; neither performs transport I/O. |
| FWC-CP1 → FWC-05 | Transport must use the completed centralized policy and content boundaries. |
| FWC-05 → FWC-06 | Batch orchestration needs the single-request fetch boundary. |
| FWC-06 → FWC-07 → FWC-08 | Register only a tested, delivery-safe application port, then wire it. |
| FWC-08 → FWC-09 | End-to-end offline coverage follows the real composition path. |

## Risks and mitigation

| Risk | Mitigation |
| --- | --- |
| SSRF bypass through misleading hostnames or mixed DNS answers | Resolve before every request/redirect and require every returned address to pass a centralized `ipaddress` global-routability policy. |
| Redirect bypass | Disable automatic redirects and validate URL, protocol, credentials, DNS, and destination on every hop. |
| Decompression bomb / unbounded body | Stream decoded/decompressed content, enforce actual byte count, and close the response immediately on limit failure. |
| Incorrect cancellation semantics | Treat host cancellation and deadline expiry as distinct stable outcomes; test body-stream cleanup. |
| Tool output silently losing metadata | Apply aggregate limiting only after full results exist; preserve objects and metadata while truncating only `content`. |
| Runtime multipart or observation limits invalidating a complete fetch payload | Budget serialized JSON, not content alone; test max parts, part size, escaping overhead, and the runtime observation path before handoff. |
| Offline transport tests accidentally perform DNS/network I/O | Inject DNS and HTTPX client/transport factories; use fakes at application/composition level and `httpx.MockTransport` at adapter level. |
| Prompt injection from page content | Keep all page text as ordinary result data with the untrusted trust marker; do not phrase-filter content. |
| Premature shared HTTP abstraction | Keep streaming HTTP implementation slice-owned until a second consumer proves a common contract. |

## Assumptions and resolved implementation decisions

### Confirmed assumptions

- Version 1 is HTTPS-only and GET-only.
- The existing `httpx` dependency is the chosen transport library.
- `markdownify` with the standard-library `html.parser` backend is the accepted
  HTML-normalization solution.
- Default tests must not use live external services.
- This raw-development-stage project does not require backward-compatibility
  shims.

### Resolved implementation details

- Bootstrap exposes a slice-specific frozen `FetchWebContentToolOptions` object
  rather than reusing command-sandbox policy. The host explicitly supplies
  `public_web_enabled`, safe headers/User-Agent, limits, DNS, and HTTPX factory
  dependencies.
- Disabled public web access is represented as one ordered
  `PUBLIC_WEB_DISABLED` failure for each requested URL at invocation time. It is
  not a construction error and does not perform DNS or HTTP work.
- The application owns complete-result, aggregate-content, serialized-payload,
  retry-delay, and deadline/cancellation decisions. The HTTPX adapter owns one
  streamed attempt and typed transport outcomes; this keeps offline adapter
  testing possible through an injected HTTPX transport/client factory.
- The registered-tool adapter only chunks a payload already proven within the
  runtime multipart limits. It must not rely on the runtime observation summary
  to retain required result metadata.

## Plan verification

- [x] Every task has acceptance criteria.
- [x] Every task has a verification step.
- [x] Dependencies and sequencing constraints are identified.
- [x] Checkpoints exist before transport implementation and final handoff.
- [x] Scope, non-goals, risks, assumptions, and implementation decisions are
  documented.
- [x] Each detailed task/checkpoint has a matching progress-tracking item.
- [x] The plan states how to keep status current during implementation.
