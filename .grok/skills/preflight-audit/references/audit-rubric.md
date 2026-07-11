# Preflight audit rubric (coverage checklist)

Use as a **checklist**, not a mandatory web-only template. Skip with N/A when the surface does not exist.

## Security & data exposure

- [ ] Authn/authz: missing server checks, priv-esc, IDOR, cross-tenant
- [ ] Secrets: client code, env, API responses, logs, analytics, URLs, storage, cookies, errors, source maps, digests
- [ ] Injection: SQL, command, template, prompt, HTML/script
- [ ] XSS, CSRF, SSRF, open redirects, uploads, path traversal, sessions, tokens
- [ ] Over-permissive CORS, buckets, webhooks, DB rules, integrations
- [ ] Validation/sanitisation at trust boundaries (never client-only)
- [ ] Local tools: redaction completeness, path join on untrusted ids, install hook overwrite, project-dir copies of sensitive output

## Race / concurrency / state

- [ ] Double-submit / retry / refresh duplicates
- [ ] Non-idempotent payments/messages/jobs/side effects
- [ ] Stale state, lost updates, out-of-order async
- [ ] Cleanup of effects/listeners/timers/requests
- [ ] UI/CLI actions while operation in progress
- [ ] Cache invalidation; multi-tab / multi-process writers
- [ ] Non-atomic file or RMW counters

## Reliability

- [ ] Unhandled rejections, swallowed errors, silent fail
- [ ] Loading / empty / error / offline / timeout / partial
- [ ] Inconsistent state after failure
- [ ] Bad assumptions on nullability, order, timing, network
- [ ] Memory leaks, expensive paths, perf bottlenecks

## Accessibility (UI)

- [ ] Semantics: landmarks, headings, labels, lists, tables, buttons/links
- [ ] Keyboard, tab order, focus visible/trap/restore
- [ ] Accessible names, ARIA correctness
- [ ] Contrast, touch targets, zoom, reduced motion, color-only meaning
- [ ] SR behavior: modals, menus, toasts, validation, live updates
- [ ] Forms: instructions, errors, autocomplete
- [ ] WCAG 2.2 AA where applicable

## Visual & interaction consistency

- [ ] Spacing, type, color, radius, shadow, icons, alignment, responsive
- [ ] Same look ≠ same behavior (or inverse)
- [ ] Design tokens / shared components
- [ ] Hover/focus/active/selected/disabled/loading/success/warning/destructive/error
- [ ] Layout shift, overflow, truncation, breakpoints, empty states
- [ ] Copy/terminology/capitalisation/dates/numbers/actions

## Responsive & edge cases

- [ ] Mobile / tablet / desktop / ultrawide / zoom / large text
- [ ] Long names/emails, i18n expansion, empty, huge datasets, zero results, malformed content
- [ ] Ideal-content / single-viewport assumptions

## Per-finding fields

Severity · Category · Location · Issue · Impact · Evidence · Reproduction · Recommended fix · Confidence
