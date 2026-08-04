---
name: frontend-ui-engineering
description: Build, review, or refine browser-facing user interfaces so they are accessible, responsive, performant, visually coherent, and aligned with the project design system.
metadata:
  version: "1.2.0"
  dependencies:
    tools: []
    skills:
      - name: browser-runtime-verification
        purpose: Verify browser-facing rendering, interaction, focus, accessibility, network behavior, and visual layout.
        required: false
---

# Frontend UI Engineering

Use this skill when creating or modifying user-facing interface behavior,
components, layouts, states, or interaction flows. The goal is a UI that feels
intentional, accessible, and consistent with the product rather than generic or
template-driven.

This skill is intentionally frontend-specific. Keep browser, UI, accessibility,
responsive layout, and interaction guidance, but avoid assuming a particular
framework, component library, styling system, or state-management tool.

## When to use this skill

Use this skill when:

- building or changing user-facing pages, views, or components
- implementing responsive layout or visual polish
- adding interactivity, forms, navigation, or stateful behavior
- handling loading, empty, error, validation, or success states
- reviewing whether UI work is production-quality

Do not use this skill for backend-only changes, documentation-only edits, or
interfaces that are not rendered or operated by users.

## Principles

- Start from the user task, not the component tree.
- Follow the project’s existing design system before inventing new styles.
- Prefer semantic structure and accessible defaults.
- Keep presentation, data loading, and side effects separated where practical.
- Design responsive, loading, empty, error, and disabled states from the start.
- Verify in a real browser when behavior or visual state matters.

## Steps

### 1. Define the UI scenario

State:

- user goal and primary flow
- affected page, route, component, or view
- expected states, such as loading, empty, error, success, disabled, and pending
- viewport or device classes that matter
- accessibility and keyboard requirements
- design system constraints

If the design intent is unclear, ask for the target experience before filling the
gap with generic styling.

### 2. Follow existing component architecture

Inspect neighboring UI code before introducing a new pattern.

Check how the project handles:

- component boundaries and file organization
- styling tokens and spacing scale
- form controls and validation messages
- data loading and mutation flows
- error, empty, and loading states
- reusable primitives and design-system components
- tests, examples, stories, or visual fixtures

Prefer local conventions over imported preferences from another framework or
toolkit.

### 3. Separate responsibilities

Keep components focused where practical:

- data or state container: fetches, derives, or mutates state
- presentation component: renders provided data and callbacks
- primitive component: encodes reusable interaction, accessibility, and visual
  behavior
- layout component: arranges content without owning domain behavior

Do not split components mechanically. Split when it improves readability,
testing, reuse, or accessibility.

### 4. Use the design system intentionally

Avoid generic generated aesthetics. Match the product’s established visual
language.

Check:

- spacing uses the project scale
- typography follows hierarchy and does not skip semantic heading levels
- color uses semantic tokens or approved palette values
- contrast meets the project accessibility standard
- icons, shadows, borders, radii, and motion match existing patterns
- copy uses realistic content and handles length, wrapping, and localization risk

Do not add arbitrary colors, spacing, animation, or decorative effects just to make
the UI look busy.

### 5. Build accessible interactions

For interactive UI, confirm:

- controls use semantic elements where possible
- every interactive element is keyboard reachable and operable
- focus order follows the visual and task order
- focus indicators are visible
- accessible names are present for controls without visible text
- form inputs have labels, descriptions, and errors
- status changes are perceivable when needed
- modals, menus, popovers, and overlays manage focus intentionally

Use `references/accessibility-checklist.md` for a focused accessibility review.

### 6. Handle all user-visible states

Implement the states users can actually encounter:

- initial and loading
- empty
- partial or stale data
- validation error
- server or network failure
- disabled or permission-limited
- success and confirmation
- optimistic or pending mutation when applicable

Empty and error states should tell the user what happened and what they can do
next.

### 7. Design responsive behavior

Start with the narrowest supported viewport and expand deliberately.

Check:

- content reflows without horizontal scrolling unless intentionally required
- touch targets remain usable
- dense data has a smaller-screen strategy
- navigation and overlays work at target sizes
- text wrapping does not break layout
- zoom and reduced-motion preferences are respected

Use the project’s breakpoints or device classes rather than hardcoded assumptions.

### 8. Verify runtime behavior

When available, use the `browser-runtime-verification` skill if the change
affects rendering, interaction, network behavior, focus, accessibility, or
visual layout. Otherwise, use the project's available browser testing or manual
verification workflow and document the limitation.

At minimum, verify:

- the relevant UI renders without unexplained console errors
- the primary flow works with keyboard and pointer input
- loading, empty, and error states behave as expected
- responsive layout works at representative viewport sizes
- relevant network or mutation behavior is not duplicated or unsafe

### 9. Protect user-facing performance

Keep the interface responsive without optimizing against assumptions.

Check for:

- unnecessary requests, repeated work, or avoidable rerenders
- unexpectedly large assets, bundles, or dependencies
- layout shifts caused by images, fonts, or late-loading content
- slow interactions or long-running work that blocks user input
- long lists or media that need deferred loading or bounded rendering

Use project performance budgets and measurement tools when they exist. For a
suspected regression, compare relevant measurements before and after the change
instead of claiming improvement from code inspection alone.

## Red flags

- generic layout or styling unrelated to the product’s design system
- interactive elements that only work with a pointer
- missing loading, empty, or error states
- color is the only indicator of meaning
- arbitrary spacing, typography, or animation values
- component owns unrelated data, layout, and business behavior at once
- responsive behavior is assumed but not checked
- performance claims made without relevant measurement
- UI shipped without browser runtime verification when visual behavior matters

## Output checklist

- user scenario and states are explicit
- local UI conventions and design system were inspected
- component responsibilities are clear
- semantic structure and keyboard interaction are supported
- accessibility checklist was considered for interactive changes
- responsive behavior was checked at representative sizes
- loading, empty, error, and success states are handled
- user-facing performance risks were checked and measured when relevant
- browser runtime verification was run or skipped with a reason
