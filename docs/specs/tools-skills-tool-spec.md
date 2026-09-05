# Spec: Skills Tool

## Status

- State: Accepted.
- Implementation status: Partially implemented; explicitly selected skill context
  loading and policy-gated skill scripts exist, but the model-callable `skills`
  tool and its run-scoped activation state are not implemented.
- Accepted by: Maintainer (interview approval).
- Accepted on: September 5, 2026.
- Revision: Accepted Version 1 scope on September 5, 2026: activation-only,
  global/workspace sources, unified frontmatter parsing, bounded transport, and
  no `@skill/...` resource routing.
- Supersedes: The unconfirmed skills-tool draft.

This document is the canonical source of truth for the requirements it defines. Derived plans and implementation must preserve its objective, constraints, execution boundaries, and success criteria; material changes require an updated and re-confirmed specification.

## Objective

Define the model-facing and host-facing specification for the `skills` agent
orchestration tool.

`skills` is the agent's on-demand procedural knowledge activation primitive. It
allows a model to discover configured skills from concise metadata, activate one
relevant skill by identifier, load that skill's complete instructions only when
needed and pass optional invocation arguments as data. Version 1 does not expose
skill-bundled resources through ordinary tools.

The governing principle is:

```text
A skill tells the agent how to use its capabilities; it is not itself a
capability.
```

## Current Context

- Project: `fabrica`, a Python 3.14 local agent runtime experiment using a
  `src/` layout and hexagonal architecture organized by vertical slices.
- Runtime direction is owned by `docs/specs/agent-runtime-spec.md`.
- Model-callable primitive capability specs include
  `docs/specs/tools-read-files-tool-spec.md`, `docs/specs/tools-search-codebase-tool-spec.md`,
  `docs/specs/tools-run-commands-tool-spec.md`, `docs/specs/tools-fetch-web-content-tool-spec.md`, and
  `docs/specs/tools-apply-patch-tool-spec.md`.
- Existing Agent Skill support under `src/fabrica/features/agent_runtime/` can
  load explicitly selected local `SKILL.md` markdown, selected text resources,
  and policy-gated selected skill scripts through application ports and adapters.
- Existing selected skill context is composition-time context augmentation. This
  specification makes its parser and definition model canonical for both that
  path and future model-facing activation.
- The accepted `read_files` and `apply_patch` specifications expose workspace-only
  paths. Version 1 does not change those contracts or expose `@skill/...` paths.

## Assumptions

- The primary caller is a model-driven coding agent operating inside a configured
  workspace and runtime run.
- Cline compatibility matters for the public tool name and simple input shape:
  `skill` plus optional nullable `args`.
- Internally, the operation should be named activation, not execution.
- Skill files use Cline's established `SKILL.md` structure with optional bundled
  resources under sibling directories such as `docs/`, `templates/`, `scripts/`,
  `examples/`, and `schemas/`.
- Version 1 supports configured global and workspace providers only. Filesystem
  locations are provider configuration, not core identity.
- Documentation-only changes should be reviewed for clarity and consistency;
  implementation changes will require tests and the project quality gate.

## Architectural classification

`skills` is not an external capability like filesystem, process, or network
tools. It belongs to the agent orchestration layer.

Recommended tool taxonomy:

```text
Primitive capabilities
──────────────────────
read_files
search_codebase
run_commands
fetch_web_content
apply_patch

Agent orchestration
───────────────────
skills
ask_question
submit_and_exit
```

Activating a skill must never itself execute commands, modify files, fetch URLs,
spawn a sub-agent, grant permissions, register arbitrary new capabilities, or
install/download/enable/disable skills. Activation loads procedural
instructions; ordinary tools implement those instructions later under normal
permission and sandbox policy.

## Scope

### In Scope

- Global and workspace procedural-skill discovery and activation without
  capability expansion.
- Immutable run-scoped registry snapshots, revision integrity, trust evaluation,
  active-skill state, and compaction persistence.
- One canonical YAML-frontmatter `SKILL.md` parser shared with explicitly
  selected skill-context loading.

### Out of Scope

- Plugin and managed providers.
- `@skill/...` resource paths, resource sandbox mounts, and changes to
  `read_files`, `apply_patch`, or `run_commands`.
- Model-callable skill scripts, automatic script execution, dynamic discovery,
  marketplace installation, and skill editing.
- Compatibility support for heading-only `SKILL.md` files.

## Desired Behavior

`skills` must allow a model to:

- inspect available skill names and descriptions in the generated tool
  description;
- activate one configured enabled skill before substantive work when the user's
  request clearly matches the skill description;
- activate a user-explicit skill or slash-command invocation before any other
  substantive action;
- pass optional invocation arguments without concatenating those arguments into
  the instruction body;
- receive structured activation results containing metadata, revision, resource
  root, instructions, and trust classification;
- avoid repeated instruction injection when the same revision is already active;
- keep active skill instructions available through context compaction;
- receive complete bounded instructions through a structured content part rather
  than generic tool result text.

The intended agent loop is:

```text
available skill metadata
      ↓
model decides skill clearly matches
      ↓
skills activates selected instructions
      ↓
ordinary tools perform the work
```

Do not force weak matches. Activate only when a skill description clearly matches
the task or the user explicitly invokes it.

## Tool interface

Tool name:

```text
skills
```

Keep the Cline-compatible name. Semantically, the internal operation should be
called `activateSkill()` rather than `executeSkill()`.

Canonical model-facing JSON schema:

```json
{
  "type": "object",
  "properties": {
    "skill": {
      "type": "string",
      "minLength": 1,
      "maxLength": 256
    },
    "args": {
      "type": ["string", "null"],
      "maxLength": 6000
    }
  },
  "required": ["skill"],
  "additionalProperties": false
}
```

Example:

```json
{
  "skill": "review-pr",
  "args": "123"
}
```

There is little value in making this input more elaborate. Runtime metadata such
as activation reason, run ID, registry revision, host allowlist, or workspace
trust belongs in host context rather than the model-facing schema.

## Model-facing description

Generate the `skills` tool description dynamically from the current registry.
Disabled and disallowed skills must not be advertised.

Recommended description form:

```text
Activate a configured procedural skill in the current agent run.

Before performing a task, check whether an available skill clearly matches
the user's request. If so, activate it before taking substantive action.
If the user explicitly invokes a skill or slash command, activate it first.

Activating a skill loads its detailed instructions into the current run.
It does not itself execute commands or grant additional permissions.
Supporting resources referenced by an activated skill can be accessed using
the normal tools.

Available skills:
- review-pr — Review pull requests for correctness, tests and regressions.
- release — Prepare and validate software releases.
- database-migration — Plan and implement database migrations.
```

Descriptions must explain what the skill does and when to activate it. The model
needs more than a list of names to choose safely.

The model-facing description must fit the existing 1,000-character
`ToolDefinition` description limit. Sort eligible skills by canonical ID, render
complete `<name> — <description>` entries in that order, and stop before the next
complete entry would exceed the bound. If entries remain, append a bounded notice
that the visible catalog is partial; the model must not guess omitted skills.

Recommended metadata budget:

```text
MAX_SKILL_NAME_CHARS        = 64
MAX_SKILL_DESCRIPTION_CHARS = 512
MAX_ENABLED_SKILLS          = 50
MAX_ADVERTISED_CATALOG_CHARS = 1,000
```

## Skill identifiers and resolution

Every skill must have a globally unique canonical ID:

```text
<source>:<name>
```

Examples:

```text
global:commit
workspace:review-pr
```

The display name remains human-friendly, such as `commit`, `review-pr`, or
`triage-issue`.

The `skill` input identifies a configured skill, not a filesystem path. The model
must not invoke arbitrary `/path/to/SKILL.md` files through this tool. Only
entries already present in the runtime `SkillRegistry` are valid.

Normalize invocations before resolution:

```text
trim whitespace
remove leading /
case-fold identifier
```

A bare invocation is allowed only when exactly one enabled, allowed skill has
that name. If multiple candidates exist, return `AMBIGUOUS_SKILL` with candidate
IDs. Do not silently shadow skills with source precedence rules such as
"workspace beats global".

Example ambiguity result:

```json
{
  "success": false,
  "error": {
    "code": "AMBIGUOUS_SKILL",
    "message": "Skill \"review-pr\" is ambiguous.",
    "candidates": [
      "global:review-pr",
      "workspace:review-pr"
    ]
  }
}
```

## Skill registry and metadata

Maintain a registry instead of discovering files during every invocation:

```text
SkillRegistry
    ├── GlobalSkillProvider
    └── WorkspaceSkillProvider
```

Each provider reports skill definitions. The registry owns discovery, metadata,
enable/disable state, canonical IDs, source provenance, revision calculation,
hot reload, and host allowlisting.

At run start, the host must obtain one immutable `SkillRegistrySnapshot`. The
tool description for that run is derived only from this snapshot, and every
activation resolves only against this same snapshot. A snapshot has a stable
opaque `snapshot_id` and a registry revision/digest suitable for audit events.
Refreshing metadata produces a later snapshot for a later run; it must not
silently add, remove, or replace skills in an active run.

Provider discovery happens before the run begins, outside model tool execution.
Invalid or unavailable provider entries are omitted fail-closed and recorded in
host diagnostics without exposing filesystem locations or failure details to the
model. A provider failure must not invalidate healthy provider entries. If no
usable snapshot can be built, the host must either run without the `skills` tool
or fail run startup before the model sees an incomplete advertised catalog.

Registry metadata for each entry should include:

```text
id
name
description
source
enabled
revision
trust
```

Example:

```json
{
  "id": "workspace:review-pr",
  "name": "review-pr",
  "description": "Review a pull request for correctness, tests and maintainability.",
  "source": "workspace",
  "enabled": true,
  "revision": "sha256:8cbb...",
  "trust": "workspace"
}
```

Version 1 source values are exactly `global` and `workspace`. Plugin and managed
provider identity is deferred. Avoid embedding Cline-specific storage locations
in the domain model.

The registry may hot reload skill metadata and revisions as files change for
future snapshots. Each activation result must still include the exact loaded
revision and snapshot ID so a run remains auditable.

## Skill format and validation

Use Cline's established structure:

```text
review-pr/
├── SKILL.md
├── docs/
├── templates/
└── scripts/
```

`SKILL.md` must contain YAML frontmatter followed by markdown instructions:

```markdown
---
name: review-pr
description: Review pull requests for correctness, tests, maintainability and regressions. Use when asked to review or assess a PR.
---

# Pull Request Review

Follow this workflow:

1. Inspect the diff.
2. Understand affected code.
3. Run relevant tests.
4. Identify correctness issues.
5. Report findings by severity.
```

Recommended v1 frontmatter:

```yaml
name: review-pr
description: Review pull requests...
```

Optional:

```yaml
disabled: false
```

Internal/runtime metadata such as source, revision, trust, and resource root
should not need to live in the file.

Skill names must be lowercase kebab-case:

```text
^[a-z0-9]+(?:-[a-z0-9]+)*$
```

Require directory/name consistency:

```text
review-pr/SKILL.md
name: review-pr
```

Reject malformed definitions during registry loading where possible:

- missing `SKILL.md`;
- invalid YAML;
- missing `name`;
- missing `description`;
- empty instruction body;
- invalid skill name;
- directory/name mismatch;
- instruction size exceeded.

Reject UTF-8 BOM before frontmatter parsing so the exact instruction bytes have
one unambiguous revision identity.

Instruction size must be bounded. Recommended limits:

```text
MAX_SKILL_INSTRUCTION_TOKENS = 5,000
MAX_SKILL_INSTRUCTION_CHARS  = 20,000 when tokenizer information is unavailable
MAX_SKILL_INSTRUCTION_CONTENT_CHARS = 48,000
```

Large reference material belongs in supporting resources and should be loaded
only when required.

The successful serialized activation result, including metadata and instructions,
must fit the provider-neutral structured text-content ceiling. Reject a definition
whose successful activation result cannot fit this channel. Never silently
truncate activated instructions.

Calculate the instruction revision from exact UTF-8 `SKILL.md` bytes after
rejecting a UTF-8 BOM and before parsing or newline normalization:

```text
instruction_revision = SHA-256(SKILL.md bytes)
```

Represent revisions as `sha256:<lowercase-hex>`. The instruction revision
identifies instructions only; it does not claim that bundled resources remain
unchanged. Each resource read must return the digest of the exact bytes supplied
to the model. A future tree/manifest revision may add atomic resource-set
pinning, but Version 1 must not imply it.

## Progressive loading

Keep three loading levels:

```text
Level 1 — metadata
name + description

Level 2 — instructions
SKILL.md body when activated

Level 3 — resources
docs/templates/scripts loaded as needed through ordinary tools
```

Activation loads Level 2 only. Supporting resources must not automatically enter
context on activation.

## Activation result

Return structured content rather than XML-like strings.

Success example:

```json
{
  "success": true,
  "status": "activated",
  "skill": {
    "id": "workspace:review-pr",
    "name": "review-pr",
    "description": "Review pull requests...",
    "revision": "sha256:8cbb...",
    "source": "workspace",
    "registry_snapshot_id": "..."
  },
  "args": "123",
  "instructions": "# Pull Request Review\n\n...",
  "trust": "configured_skill_instructions"
}
```

The registered-tool adapter returns the structured activation result as one
bounded `ToolTextContent` part rather than generic `result_text`.

`args` are invocation-specific input data. They are not skill instructions and
must not be concatenated into the instruction body. XML-like, JSON-like, quoted,
Unicode, empty, or omitted arguments must remain ordinary argument data.

If the same skill revision is already active, do not return the complete
instructions again:

```json
{
  "success": true,
  "status": "already_active",
  "skill": {
    "id": "workspace:review-pr",
    "revision": "sha256:8cbb..."
  },
  "args": "123"
}
```

## Active skill state

Maintain an `ActiveSkillSet` for the current agent run. It is application-owned,
run-scoped state; it is not reconstructed from historical model tool messages.

Responsibilities:

- idempotent activation;
- revision pinning;
- run lifecycle ownership;
- compaction rehydration;
- resource authorization;
- audit state.

If a skill's underlying file changes during a run, do not silently replace the
active revision. Keep the active revision for the current run or require explicit
reactivation. This gives deterministic behavior.

Activated skills must survive context compaction. The runtime should persist:

```text
ActiveSkill {
    id
    instruction_revision
    instructions
    activation_order
    registry_snapshot_id
}
```

The runtime compaction port must serialize this ordered state with the compacted
run state. When it rebuilds model context, it must rehydrate each active skill's
instructions once, in `activation_order`, after system/runtime and user context
and before ordinary retrieved data. Rehydrated instructions count against the
normal context budget. If they cannot fit together with required higher-priority
context, the run must fail before the next model turn with a host-visible
`ACTIVE_SKILL_CONTEXT_OVERFLOW`; it must not silently omit, truncate, reorder, or
replace active instructions.

Compaction state is valid only for the owning run and registry snapshot. A resume
attempt with missing or malformed active-skill state must fail closed rather than
silently treating the run as having no active skills. No cross-process durable
recovery is required in Version 1 unless the runtime itself already offers
durable run resumption.

Multiple active skills are allowed when genuinely complementary. Do not implement
an invisible "last skill wins" hierarchy. If active procedures conflict, system
and user requirements remain authoritative, and the model should reconcile the
procedures explicitly.

## Skill instruction precedence and trust

Skills are procedural guidance. They do not override system/runtime policy,
safety policy, explicit user constraints, or tool permission policy.

Recommended hierarchy:

```text
system/runtime constraints
        ↓
user request
        ↓
activated skill procedure
        ↓
ordinary retrieved data
```

Not every source has equal trust:

```text
global/user-installed skill → user-configured procedural instructions
trusted workspace skill     → project procedural instructions
plugin skill                → plugin procedural instructions
untrusted workspace         → disabled or approval-gated
```

Repository-controlled workspace skills can contain harmful instructions. A
workspace skill should be active only when the workspace is trusted or after
explicit user approval.

Skills cannot grant permissions. If a skill says to run a deployment script,
read a secret, fetch a URL, or edit a protected file, ordinary tool permission,
sandbox, network, credential, and filesystem policies still apply.

## Resources and Scripts

Version 1 does not return a model-usable `resource_root` and does not expose
skill-bundled resources through `read_files`, `apply_patch`, or `run_commands`.
The existing host-selected resource-context path remains separate and is not a
model-callable logical namespace.

Future `@skill/...` routing requires coordinated accepted revisions to the
affected tool specifications and a shared application-owned resolver. It is not
an implicit extension of workspace-relative paths.
If instructions reference a script, the agent must explicitly use `run_commands`,
and normal command permissions apply. Activation itself never executes scripts or
changes sandbox visibility.
host-controlled mapping.

## Slash commands

User input such as `/review-pr 123` may normalize to:

```json
{
  "skill": "review-pr",
  "args": "123"
}
```

This may happen in frontend preprocessing or through normal model tool
selection. Both paths must converge on the same `SkillActivator`; do not maintain
a separate slash-command execution architecture.

## Policy, allowlisting, and disabled skills

The registry maintains `enabled: true | false`.

Disabled skills:

- are not advertised;
- cannot be activated by bare name;
- return `SKILL_DISABLED` if explicitly requested by canonical ID.

Support an optional host-level allowlist:

```text
allowed_skill_ids = [
    "global:commit",
    "workspace:review-pr"
]
```

Skills outside the allowlist do not exist from the agent's perspective and must
not be advertised.

Trust and approval are host-owned decisions. The application boundary must use a
revision-bound decision with at least these inputs:

```text
workspace_identity
canonical_skill_id
instruction_revision
source
run_id
```

The decision is either `TRUSTED`, `APPROVED_FOR_RUN`, or `DENIED`. Workspace
approval is valid only for the named workspace, exact instruction revision, and
owning run; it expires when that run ends and cannot authorize a changed skill.
Global sources may be trusted by host policy without a per-run prompt. Workspace
sources require a trusted workspace or explicit revision-bound approval. Denied
or unavailable decisions must not disclose hidden skill metadata.
`SKILL_UNTRUSTED` denotes a source that requires approval but has none;
`SKILL_NOT_ALLOWED` denotes a host allowlist rejection.

## Cancellation, timeouts, retries, and atomicity

Skill activation should normally be local and fast. The run-scoped registry
snapshot is already available before activation; the timeout covers loading and
validating the selected definition only.

Recommended defaults:

```text
SKILL_LOAD_TIMEOUT = 15 seconds
automatic retry    = false
```

Skill loading should respect the active run cancellation signal. If cancellation
occurs before activation completes, do not add the skill to `ActiveSkillSet` and
return `SKILL_LOAD_CANCELLED`.

Activation must be atomic:

```text
resolve skill
    ↓
check enabled/trust/allowlist
    ↓
load exact revision
    ↓
validate instructions
    ↓
resolve resource root
    ↓
register ActiveSkill
    ↓
return activation result
```

If any pre-registration step fails, active skill state remains unchanged.

## Error codes

Define stable error codes:

- `INVALID_INPUT`;
- `SKILL_NOT_FOUND`;
- `SKILL_DISABLED`;
- `AMBIGUOUS_SKILL`;
- `SKILL_NOT_ALLOWED`;
- `SKILL_UNTRUSTED`;
- `INVALID_SKILL_DEFINITION`;
- `SKILL_TOO_LARGE`;
- `SKILL_RESOURCE_UNAVAILABLE`;
- `SKILL_LOAD_TIMEOUT`;
- `SKILL_LOAD_CANCELLED`;
- `ACTIVE_SKILL_CONTEXT_OVERFLOW`;
- `INTERNAL_SKILL_ERROR`.

Missing skill example:

```json
{
  "success": false,
  "error": {
    "code": "SKILL_NOT_FOUND",
    "skill": "foo",
    "available": [
      "review-pr",
      "release"
    ]
  }
}
```

Disabled skill example:

```json
{
  "success": false,
  "error": {
    "code": "SKILL_DISABLED",
    "skill": "global:release"
  }
}
```

## Telemetry and audit

Record an audit event when activation succeeds:

```json
{
  "event": "skill_activated",
  "skill_id": "workspace:review-pr",
  "revision": "sha256:8cbb...",
  "source": "workspace",
  "activation_reason": "model_selected",
  "run_id": "...",
  "registry_snapshot_id": "..."
}
```

Possible activation reasons are `model_selected`, `user_slash_command`, and
`host_forced`. Do not log sensitive `args` by default.

## Relationship to neighboring tools

`skills` loads procedural instructions; primitive tools perform external work.

```text
read_files          reads workspace files
search_codebase     discovers workspace content
run_commands        executes commands under permission and sandbox policy
fetch_web_content   fetches URLs under network policy
apply_patch         mutates workspace files under patch policy
skills              activates configured procedural instructions
```

Existing selected skill script support in Fabrica is policy-gated and bound to
approved immutable script bytes. The `skills` primitive must preserve that
non-escalation model. Skill script execution remains a separate ordinary tool or
application use case, not a side effect of skill activation.

## Architecture and project structure

Recommended component boundaries:

```text
SkillsTool
    ↓
SkillResolver
    ↓
SkillPolicy
    ↓
SkillLoader
    ↓
SkillValidator
    ↓
ActiveSkillSet
    ↓
ActivationResult
```

Backed by:

```text
SkillRegistry
    ├── WorkspaceSkillProvider
    └── GlobalSkillProvider
```

Responsibilities:

- `SkillRegistry`: discovery, metadata, enable/disable state, canonical IDs,
  source provenance, revision, hot reload, and allowlisting. It creates immutable
  run-scoped snapshots and does not modify model context.
- `SkillActivator`: resolve invocation, evaluate trust and policy, load exact
  revision, validate instructions, register active skill, and return instruction
  payload. It receives the host-owned revision-bound trust decision and does not
  execute other tools.
- `ActiveSkillSet`: idempotent activation, revision pinning, run lifecycle,
  ordered compaction serialization, and audit state.
- `SkillDefinitionLoader`: loads and validates configured global/workspace skill
  definitions without exposing filesystem paths to application use cases.

Likely future implementation ownership:

- Spec: `docs/specs/tools-skills-tool-spec.md`.
- Runtime tool contracts, DTOs, and orchestration use cases: under
  `src/fabrica/features/agent_runtime/application/`.
- Filesystem-backed global/workspace providers and `SKILL.md` parsing: adapters
  under the agent runtime slice or composition-root infrastructure.
- Composition and optional CLI wiring: under `src/fabrica/bootstrap/` or the
  relevant driving adapter.
- Unit tests: under `tests/unit/features/agent_runtime/` for registry,
  resolver, validator, activator, and active-set behavior.
- Integration tests: under `tests/integration/features/agent_runtime/` for
  synthetic filesystem skill roots, workspace trust policy, and compaction
  rehydration wiring.

Implementation must preserve hexagonal boundaries: domain and application code
must not perform filesystem I/O directly, provider schemas must not leak into
stable application DTOs, and skill activation must remain orchestration state
rather than a primitive external capability.

## Differences from current Cline behavior

Keep these Cline-compatible concepts:

- `skills` as on-demand instruction loading;
- simple `skill` plus optional `args` input;
- `SKILL.md` format;
- YAML metadata plus markdown instructions;
- progressive loading;
- optional supporting resources;
- enabled/disabled state;
- namespaced skill IDs;
- ambiguity detection;
- host allowlist;
- slash-command invocation;
- dynamic available-skill metadata;
- 15-second default load timeout;
- configuration watcher and hot reload concept.

Change these behaviors for this implementation:

- call the internal operation activation, not execution;
- do not return XML-like instruction strings;
- do not mix `args` into instruction markup;
- expose descriptions to the model, not only skill names;
- require description;
- require directory/name consistency;
- enforce skill-name syntax;
- do not rely solely on tool-result history for persistence;
- do not expose arbitrary skill filesystem paths;
- do not silently shadow same-name skills.

Add these requirements beyond current Cline behavior:

- structured activation result;
- canonical source-qualified IDs;
- revision hashes;
- `ActiveSkillSet`;
- compaction persistence;
- explicit trust levels;
- workspace trust policy;
- permission non-escalation guarantee;
- deferred logical skill-resource namespace;
- atomic activation;
- activation audit events.

## Testing Strategy

Required future acceptance tests include the following scenarios.

### Registry

- Global skill discovered.
- Workspace skill discovered.
- Plugin skill discovered.
- Disabled skill omitted.
- Invalid skill rejected.
- Hot reload updates revision.

### Parsing

- Valid YAML frontmatter.
- UTF-8 BOM.
- Missing name.
- Missing description.
- Empty body.
- Invalid YAML.
- Directory/name mismatch.
- Invalid kebab-case.
- Instruction-size limit.

### Resolution

- Canonical ID.
- Unique bare name.
- Leading slash.
- Different case.
- Ambiguous name.
- Missing name.
- Disabled skill.
- Allowlist rejection.

### Activation

- New activation.
- Already active.
- Different skill.
- Revision retained through run.
- Snapshot catalog remains stable through run.
- Cancellation before commit.
- Invalid definition leaves active state untouched.

### Arguments

- No args.
- Empty args.
- Normal args.
- Unicode args.
- Quotes.
- XML-like args.
- JSON-like args.
- 6k size limit.

XML-like arguments must remain ordinary argument data.

### Resources

- Resource root returned.
- Read existing resource.
- Missing resource.
- Path traversal rejected.
- Resource cannot escape skill root.
- Resource result reports exact byte digest.
- Inactive skill root unavailable.
- `apply_patch` cannot mutate skill root.

### Trust and permissions

- Global trusted skill.
- Trusted workspace skill.
- Untrusted workspace blocked.
- Workspace approval is bound to workspace, run, and instruction revision.
- Plugin policy.
- Skill cannot grant extra filesystem access.
- Skill cannot grant shell permission.

### Compaction

- Activate skill.
- Compact conversation.
- Active instructions remain available.
- Same revision preserved.
- Ordered rehydration preserves all active instructions or fails with
  `ACTIVE_SKILL_CONTEXT_OVERFLOW`.

## Commands and Validation

| Check | Command or procedure | Applicability |
| --- | --- | --- |
| Format | `uv run ruff format --check .` | Required for implementation changes |
| Lint | `uv run ruff check .` | Required for implementation changes |
| Type check | `uv run ty check src tests` | Required for implementation changes |
| Tests | `uv run pytest` | Required for implementation changes |
| Documentation | Review this specification and its internal references for accuracy and consistency. | Required |
| Migration or compatibility | Not applicable unless this specification explicitly introduces a migration. | Not applicable by default |
| Manual acceptance | Confirm this accepted specification remains accurate when implementation uncovers a material scope change. | Required for material changes |

Documentation-only changes should be reviewed for clarity and consistency.

Implementation changes should use the project quality gate:

- Format: `uv run ruff format .`
- Lint: `uv run ruff check .`
- Type check: `uv run ty check src tests`
- Test: `uv run pytest`

Future implementation should start with focused registry, parser, resolver,
policy, activator, active-set, and resource-resolver tests before adding a
model-callable runtime adapter.

## Execution Boundaries

- Always use `skills` as an activation primitive, not an execution primitive.
- Always advertise concise skill descriptions, not only names.
- Always require enabled, allowed, trusted or approved registry entries before
  activation.
- Always return structured activation results with exact revision metadata.
- Always treat `args` as data, not instructions.
- Always preserve active skill state through compaction.
- Always keep Version 1 free of model-callable skill resource roots and preserve
  ordinary workspace-tool path semantics.
- Ask before exposing untrusted workspace skills, broad filesystem locations,
  marketplace installation, skill editing, or any automatic script execution.
- Never allow skills to grant permissions, bypass sandbox policy, or expand tool
  access.
- Never activate arbitrary filesystem paths as skills.
- Never silently shadow same-name skills across sources.
- Never automatically load all resource files during activation.
- Never expose skill roots as mutable ordinary-task paths.

## Success Criteria

- The spec defines `skills` as an agent orchestration primitive for activating
  configured procedural instructions.
- The public interface remains the Cline-compatible `{ "skill": string,
  "args"?: string | null }` schema with strict input bounds.
- The terminology consistently uses activate/load/use instead of execute for the
  skill primitive.
- The registry model includes canonical IDs, source provenance, enabled state,
  descriptions, revisions, trust, allowlisting, and ambiguity detection.
- The skill format requires `SKILL.md`, strict kebab-case names, descriptions,
  directory/name consistency, bounded instruction size, and revision hashes.
- The activation result is structured and separates metadata, arguments, and
  instructions.
- Active skill state covers idempotence, revision pinning, ordered compaction
  persistence, explicit overflow handling, multiple active skills, and conflict
  handling.
- Version 1 does not expose `@skill/...` paths, resource roots, plugin/managed
  providers, automatic scripts, or capability escalation.
- Trust, revision-bound workspace approval, permission non-escalation,
  cancellation, timeouts, atomicity, audit events, and stable error codes are
  specified.
- Future acceptance tests are explicit enough to drive implementation.

## Open Questions

| Question | Impact | Blocking? | Owner | Resolution |
| --- | --- | --- | --- | --- |
| Should future `@skill/...` routing use resource manifests/tree digests? | Future resource-integrity design. | No | Maintainer | Deferred |
| Should a future `run_commands` sandbox-mount contract expose activated roots read-only? | Future command-sandbox design. | No | Maintainer | Deferred |
| How should plugin and managed providers express identity, trust, and revisions? | Future provider design. | No | Maintainer | Deferred |

## Acceptance and Planning Gate

This accepted Version 1 specification is ready for implementation planning. The
deferred questions above must not expand Version 1 unless a maintainer updates and
re-confirms this specification.

## Conventions and Constraints

Follow the project architecture, typing, logging, secret-safety, and validation conventions recorded in `.clinerules/`.

## Project Structure

- Specification: This file under `docs/specs/`.
- Derived plan: `docs/plans/tools-skills-tool-v1-plan.md`.
- Source and test ownership: The detailed architecture section in this specification remains authoritative.
- Documentation ownership: `docs/specs/`, `docs/plans/`, and the relevant indexes.
