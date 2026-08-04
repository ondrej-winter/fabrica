---
name: source-driven-development
description: Grounds implementation decisions in authoritative sources. Use when building with external APIs, libraries, frameworks, platforms, standards, or tools where current documented behavior matters.
metadata:
  version: "1.1.1"
  dependencies:
    tools: []
    skills: []
---

# Source-Driven Development

## Overview

Use authoritative sources before making implementation decisions that depend on a
specific dependency, runtime, protocol, platform, standard, or external system.
Do not rely on memory when documented behavior, version compatibility, or current
recommended practice matters. APIs change, examples age, and implementation
details vary by version.

The expected outcome is implementation guidance or code that can be traced to
current, relevant sources the user can verify.

## When to use this skill

Use this skill when:

- implementing code against a library, framework, platform, service, standard, or
  command-line tool
- writing reusable patterns, starter code, templates, or examples that others may
  copy
- the user asks for documented, verified, current, or best-practice
  implementation
- reviewing code for outdated, deprecated, or version-specific patterns
- behavior depends on a particular version, feature flag, runtime, protocol, API,
  schema, or compatibility matrix

Do not use this skill for changes whose correctness does not depend on an
external source, such as renaming local variables, fixing typos, or moving files
without changing behavior.

## Steps

### 1. Identify the source-sensitive decision

Name the exact decision that needs verification. Avoid broad searches when a
focused source is enough.

Examples:

- which API signature to call for `<library_name>` version `<version>`
- which configuration key is supported by `<tool_name>`
- which protocol status code, header, or schema field is expected
- which migration path replaces a deprecated feature
- which compatibility constraint applies to `<runtime_or_platform>`

### 2. Detect versions and constraints

Inspect project files, lockfiles, manifests, schemas, command help, or existing
configuration to identify the relevant versions and constraints.

Common sources include:

- dependency manifests and lockfiles
- module, package, or build configuration
- container, runtime, or infrastructure descriptors
- API schemas, generated clients, or protocol definitions
- existing ADRs, specs, or project documentation

State what you found before fetching sources:

```text
SOURCE CONTEXT
- Dependency: <library_name> <version> from <manifest_file>
- Runtime: <runtime_name> <version> from <config_file>
- Decision: choose the documented pattern for <capability>
```

If the version or target environment is missing and affects correctness, ask the
user instead of guessing.

### 3. Fetch the most authoritative focused source

Use the narrowest official source that covers the decision. Prefer a specific API
reference, migration guide, standard section, command reference, or compatibility
entry over a documentation homepage.

Source hierarchy, from most to least authoritative:

| Priority | Source                                                                       | Use for                                                                    |
| -------- | ---------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| 1        | Official reference documentation                                             | API signatures, configuration keys, supported behavior                     |
| 2        | Official migration guides, changelogs, release notes, or deprecation notices | version changes and replacement patterns                                   |
| 3        | Standards documents or vendor-neutral specifications                         | protocol, file format, accessibility, security, or browser behavior        |
| 4        | Official compatibility matrices or runtime support tables                    | feature availability by version or platform                                |
| 5        | Source code in the dependency or tool repository                             | behavior not documented elsewhere, when repository source is authoritative |

Do not cite community posts, Q&A sites, tutorials, or AI-generated summaries as
primary evidence. They may help discovery, but the implementation decision should
trace back to an authoritative source whenever possible.

### 4. Extract the applicable rule

Record the source-backed rule in plain language:

```text
DOCUMENTED RULE
- Source: <full_url_or_local_reference>
- Applies to: <dependency_or_platform> <version_or_range>
- Relevant guidance: <short quote or paraphrase>
- Impact: use <chosen_pattern>; avoid <deprecated_or_unsupported_pattern>
```

When official sources conflict, surface the discrepancy and explain which source
appears to apply to the detected version or context. Ask the user when the tradeoff
changes behavior, compatibility, or project conventions.

### 5. Implement according to the source

Use the documented signatures, configuration keys, lifecycle rules, schemas, or
workflow steps. When existing project code uses a different pattern, decide
explicitly whether to follow current documentation or preserve local consistency.

Example conflict note:

```text
CONFLICT DETECTED
The project uses <existing_pattern>, but the documented pattern for
<dependency_name> <version> is <documented_pattern>.

Options:
1. Use the documented pattern for new code.
2. Match the existing local pattern for consistency and note the follow-up risk.
```

Do not silently choose a path when the choice has compatibility, migration, or
maintenance implications.

### 6. Cite the sources

Include citations where they help future maintainers verify non-obvious or
source-sensitive choices.

Citation rules:

- Use full URLs or precise repository-local references.
- Prefer deep links, anchors, section names, or versioned documentation when
  available.
- Quote the relevant passage for decisions that are easy to dispute or misapply.
- Include compatibility evidence when recommending platform or runtime features.
- If no authoritative source exists, mark the decision as unverified.

Example handoff note:

```text
I used <documented_pattern> because <official_source> documents it for
<dependency_name> <version>. I could not find official guidance for
<unverified_detail>, so that part should be verified before production use.
```

## Common rationalizations

| Rationalization                              | Reality                                                                         |
| -------------------------------------------- | ------------------------------------------------------------------------------- |
| "I know this API."                           | Confidence is not evidence. Version-specific details change.                    |
| "The docs are too broad."                    | Fetch the focused page or reference section, not the whole docs site.           |
| "A popular blog says this is best practice." | Community material is not a primary source for source-driven implementation.    |
| "The project already does it this way."      | Existing code may be outdated. Surface the conflict instead of copying blindly. |
| "I'll add a disclaimer."                     | A clear citation or explicit unverified note is better than vague hedging.      |

## Red flags

- writing source-sensitive code without checking the relevant version
- using a deprecated or changed API because it appears in older examples
- citing community content as the primary source for an implementation decision
- fetching broad documentation instead of the page or section that answers the
  current question
- failing to surface conflicts between official guidance and existing project code
- presenting unverified implementation details as fact

## Verification

Before handoff, confirm:

- [ ] relevant versions, constraints, or target platforms were identified
- [ ] focused authoritative sources were consulted
- [ ] source-backed decisions include citations where useful
- [ ] deprecated or incompatible patterns were avoided or explicitly justified
- [ ] conflicts between sources and existing project code were surfaced
- [ ] unverified details are clearly marked as unverified
