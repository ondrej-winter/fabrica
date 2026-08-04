---
name: conventional-commits
description: Write, review, and validate Conventional Commits v1.0.0 messages with correct type, scope, description, body, footer, and breaking-change syntax.
metadata:
  version: "1.0.1"
  dependencies:
    tools:
      - name: git
        purpose: Inspect staged changes, diffs, branch context, and commit history when drafting or reviewing commit messages.
        required: false
    skills:
      - name: git-workflow-and-versioning
        purpose: Coordinate Conventional Commits guidance with broader branch, diff, and version-control workflow decisions.
        required: false
---

# Conventional Commits

Use this skill when writing, reviewing, or correcting commit messages that should
follow the Conventional Commits v1.0.0 specification. The goal is to make commit
history machine-readable while keeping messages useful to humans.

This skill focuses on commit message syntax and meaning. Use it with the
project's existing version-control workflow, release process, and validation
requirements.

## When to use this skill

Use this skill when:

- creating a commit message in a project that uses Conventional Commits
- reviewing whether a commit message follows the v1.0.0 specification
- choosing between `feat`, `fix`, and other project-defined types
- describing breaking changes in a commit message
- preparing release notes, changelog inputs, or semantic-versioning signals from
  commit history

## Message shape

Use this general form:

```text
<type>[optional scope][optional !]: <description>

[optional body]

[optional footer(s)]
```

The prefix is required. It consists of:

- a type, such as `feat`, `fix`, `docs`, `refactor`, or another project-defined
  noun
- an optional scope in parentheses, such as `(parser)` or `(api)`
- an optional `!` before the colon to indicate a breaking change
- a required colon followed by one space
- a required short description immediately after the colon and space

## Steps

### 1. Choose the type

Select the type that best describes the user-visible or maintainer-visible
meaning of the change.

Required Conventional Commits meanings:

- Use `feat` when the commit adds a new feature to the application or library.
- Use `fix` when the commit represents a bug fix for the application.

Other types are allowed when the project uses them. Common examples include:

- `docs` for documentation-only changes
- `test` for test additions or updates
- `refactor` for code changes that neither fix a bug nor add a feature
- `chore` for maintenance tasks
- `ci` for continuous-integration configuration or automation

Do not use a vague type when `feat` or `fix` is required by the specification.

### 2. Add a scope when it improves clarity

A scope is optional. When present, it must be a noun that describes the affected
section of the codebase and must be surrounded by parentheses.

Examples:

```text
fix(parser): handle escaped delimiters
feat(auth): add token refresh support
docs(readme): clarify setup steps
```

Use the project's established scope names when they exist. Omit the scope when it
would be forced, misleading, or less clear than the description.

### 3. Write the description

The description is required and must immediately follow the colon and space after
the type or scope prefix.

Keep the description short and specific:

```text
fix: handle missing config file
feat(api): expose account status endpoint
```

Avoid descriptions such as `update`, `misc`, `changes`, or `fix stuff` because
they do not explain what changed.

### 4. Add a body when context is useful

A longer body is optional. Use it when the short description is not enough to
explain context, motivation, trade-offs, migration notes, or validation details.

The body must begin one blank line after the description. It is free-form and may
contain multiple paragraphs.

Example:

```text
fix(config): ignore empty environment overrides

Empty environment variables were previously treated as intentional overrides,
which prevented defaults from loading in containerized development setups.
```

### 5. Add footers for trailers and references

Footers are optional and must begin one blank line after the body. If there is no
body, footers begin one blank line after the description.

Each footer must use one of these separators:

- `:<space>`
- `<space>#`

Footer tokens must use hyphens instead of whitespace, except for the special
`BREAKING CHANGE` token.

Examples:

```text
Refs: #123
Reviewed-by: Contributor Name
Acked-by: Maintainer Name
```

Footer values may contain spaces and newlines. A footer value ends when the next
valid footer token and separator is found.

### 6. Mark breaking changes explicitly

Breaking changes must be indicated either in the prefix or in a footer.

Use `!` immediately before the colon in the type or scope prefix:

```text
feat(api)!: require explicit account identifiers
```

When `!` is used, the description describes the breaking change and the
`BREAKING CHANGE:` footer may be omitted.

Alternatively, use a breaking-change footer:

```text
feat(config): load environment variables before files

BREAKING CHANGE: environment variables now take precedence over config files.
```

The breaking-change footer token must be uppercase `BREAKING CHANGE` followed by
a colon, a space, and a description. `BREAKING-CHANGE` is synonymous with
`BREAKING CHANGE` when used as a footer token.

### 7. Review case and parser expectations

Conventional Commits units of information are not case-sensitive for
implementors, except that `BREAKING CHANGE` must be uppercase.

For consistency in human-authored messages, prefer lowercase types and scopes,
and write `BREAKING CHANGE` exactly uppercase.

## Examples

Feature:

```text
feat: add project export command
```

Bug fix with scope:

```text
fix(cli): preserve quoted arguments
```

Documentation change with body:

```text
docs: explain local setup flow

The previous instructions skipped the environment file step, which made the
first run fail for new contributors.
```

Breaking change with `!`:

```text
refactor(api)!: remove deprecated response fields
```

Breaking change with footer:

```text
feat(auth): enforce scoped access tokens

Tokens must now include the resource scope used by the target endpoint.

BREAKING CHANGE: unscoped tokens are rejected by authenticated endpoints.
```

## Review checklist

- message has a required type followed by optional scope, optional `!`, and `: `
- `feat` is used for a feature and `fix` is used for a bug fix
- scope, when present, is a noun in parentheses
- description is present immediately after `: ` and summarizes the change
- body, when present, starts after one blank line
- footers, when present, start after one blank line and use valid trailer syntax
- footer tokens use hyphens instead of whitespace, except `BREAKING CHANGE`
- breaking changes are marked with `!` or a `BREAKING CHANGE:` footer
- `BREAKING CHANGE` is uppercase when used
- message follows any stricter project-specific type, scope, or release rules
