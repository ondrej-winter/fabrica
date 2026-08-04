# Accessibility Checklist

Use this checklist when creating or reviewing browser-facing UI changes.

## Structure and semantics

- Use semantic elements for landmarks, headings, buttons, links, lists, forms, and tables.
- Preserve a logical heading hierarchy.
- Ensure interactive elements have accessible names.
- Associate form inputs with labels, descriptions, and errors.
- Make important status changes perceivable when loading, validation, success, or error states update.

## Keyboard and focus

- Confirm all interactive controls are keyboard reachable.
- Confirm focus order follows visual and task order.
- Confirm focus states are visible.
- Confirm modals, menus, and overlays manage focus intentionally.

## Visual accessibility

- Meet contrast requirements for text, icons, controls, and focus indicators.
- Do not rely on color alone to communicate state.
- Support zoom, responsive layouts, and reduced motion preferences.

## Verification

- Run automated accessibility checks when available.
- Manually test key flows with keyboard only.
- Verify screen-reader-facing names for non-obvious controls.
