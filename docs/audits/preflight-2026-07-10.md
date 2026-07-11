# Preflight audit — grokprint

**Date:** 2026-07-10  
**Scope:** `/home/eglobal/repos/grokprint` (CLI + Stop hook + session extract; no web UI)  
**Method:** End-to-end flow review (install → Stop → extract → write → show/notify); adversarial redaction probes; concurrency/race review  
**Code modified during audit:** None  
**Tests at audit:** 24 passed, 1 skipped  

**App shape note:** This is a local CLI/hook tool, not a multi-tenant web app. Categories that apply only to browser UIs (WCAG DOM, CSS tokens, SSRF to browser) are marked **N/A** with residual CLI/TUI notes.

---

## Executive summary

| Severity | Count |
|-|-|
| Critical | 0 |
| High | 3 |
| Medium | 6 |
| Low | 5 |
| Informational | 4 |

**Release recommendation: Ship with known risks**

Justification: Local-only observer; fail-open hooks; no remote auth surface. High findings are **data-exposure via incomplete redaction** and **workspace card copies / wrong-turn titles**, which matter for shared machines, accidental commits of digests, and notification surfaces—not remote RCE. Not “Do not ship” for a public alpha CLI; not “Safe to ship” until redaction + write hygiene improve.

---

## Findings (by severity)

### HIGH

#### H1 — Incomplete secret redaction (multiple secret families pass through)

| Field | Value |
|-|-|
| **Severity** | High |
| **Category** | Security |
| **Location** | `src/grokprint/redaction.py` → `redact_text` / `redact_card` |
| **Issue** | Redaction patterns miss common credential formats that can appear in tool titles, chat, or NEED lines. |
| **Impact** | Digests written to session dir, `.grokprint/`, and optionally notifications/annotations can retain live secrets if they appeared in assistant/tool text. |
| **Evidence** | Live probes (2026-07-10): |
| | `npm … _authToken=npm_<REDACTED>…` → **unchanged** |
| | `slack token xoxb-<REDACTED>…` → **unchanged** |
| | `postgres://user:<REDACTED_PASSWORD>@host/db` → **password retained** |
| | `password is <REDACTED_PASSWORD>` → **unchanged** (no `key=` form) |
| | `sk_live_<REDACTED>…` (Stripe-style) → **unchanged** (`sk-` pattern requires hyphen) |
| | `Authorization: Basic …` → key redacted but **base64 blob remains** |
| **Reproduction** | `PYTHONPATH=src python3 -c "from grokprint.redaction import redact_text; print(redact_text('xoxb-<REDACTED>'))"` |
| **Recommended fix** | Expand patterns: `xox[baprs]-`, `npm_`, `sk_live_`/`sk_test_`, URI userinfo `://user:pass@`, Slack webhook paths, `Basic ` base64; optional entropy-based blob filter; never put unredacted NEED from raw chat without second pass. |
| **Confidence** | **Confirmed** |

#### H2 — Workspace copy of digest can re-home session-derived content into the git tree

| Field | Value |
|-|-|
| **Severity** | High |
| **Category** | Security |
| **Location** | `extract.write_card` → `also_project=True` default; `session.project_last_print_path` → `<cwd>/.grokprint/` |
| **Issue** | Every successful extract writes `last-print.md` + `grokprint.json` into the **project workspace**. Directory is gitignored, but tools, editors, backup agents, and accidental `git add -f` still expose content; multi-user worktrees share the copy. |
| **Impact** | Secrets that survive H1, plus private paths / business content from chat, land next to source. Higher blast radius than session-only storage under `~/.grok/sessions`. |
| **Evidence** | `write_card` lines 537–546 always attempt project write; repo contains `.grokprint/last-print.md` with live session tool tallies. |
| **Reproduction** | `grokprint extract --cwd <repo>` then `cat .grokprint/last-print.md` |
| **Recommended fix** | Default `also_project=False`; opt-in via `GROKPRINT_PROJECT_COPY=1`; document; never write NEED lines containing secrets to project copy. |
| **Confidence** | **Confirmed** |

#### H3 — `updates.jsonl` titles not turn-bounded (cross-turn leakage into HAPPENED)

| Field | Value |
|-|-|
| **Severity** | High |
| **Category** | Reliability / Security |
| **Location** | `extract._updates_tool_titles` (tail 400KB of entire updates stream) |
| **Issue** | Tool titles are taken from a **global file tail**, not restricted to the current turn’s events window. Prior-turn tool names (and any secrets in titles) can appear under “also: …”. |
| **Impact** | Misleading HAPPENED; privacy bleed across turns; wrong operator decisions in loops. |
| **Evidence** | `_tail_bytes(updates_path, 400_000)` then all `tool_call` titles in that window; no correlation with `turn_started` timestamp. |
| **Reproduction** | Two turns with distinct tools; extract mid-second turn—expect first-turn titles still in top counts. |
| **Recommended fix** | Bound titles by turn time range from `events` turn_started/ended; or only use events-derived names. |
| **Confidence** | **High Confidence** |

---

### MEDIUM

#### M1 — Non-atomic dual file writes (torn reads / partial cards)

| Field | Value |
|-|-|
| **Severity** | Medium |
| **Category** | Race Condition |
| **Location** | `extract.write_card` — sequential `write_text` to json then md (×2 for project) |
| **Issue** | No temp-file + rename; concurrent Stop hooks or `show` during write can observe partial JSON or mismatched json/md. |
| **Impact** | `grokprint show --json` parse failures; notify-body fallback; rare corruption. |
| **Evidence** | Direct `Path.write_text` without `os.replace` pattern. |
| **Reproduction** | Parallel `extract_and_write` in two processes on same session (loop Stop storms). |
| **Recommended fix** | Write `*.tmp` then `os.replace`; single-writer flock optional. |
| **Confidence** | **High Confidence** |

#### M2 — Loop throttle counter race (lost updates / wrong throttle)

| Field | Value |
|-|-|
| **Severity** | Medium |
| **Category** | Race Condition |
| **Location** | `loop.should_write_this_stop` — read/modify/write `.grokprint-loop-count` |
| **Issue** | Non-atomic counter under concurrent Stop hooks. |
| **Impact** | Under `GROKPRINT_LOOP_EVERY>1`, may write more or less often than configured. |
| **Evidence** | No file lock; classic RMW. |
| **Recommended fix** | `fcntl.flock` or accept and document “best effort”; default every=1 is safe. |
| **Confidence** | **Confirmed** (code path) |

#### M3 — Full `events.jsonl` scan every Stop (latency / UI block risk)

| Field | Value |
|-|-|
| **Severity** | Medium |
| **Category** | Performance / Reliability |
| **Location** | `extract._last_turn_events` |
| **Issue** | Entire events file read line-by-line each extract; large sessions (multi-MB, tens of k lines) push against hook timeout (5s) and block hook runner. |
| **Impact** | Missing digests (fail-open empty/error); slow Stop stack with other hooks. |
| **Evidence** | Live session ~728KB+ events; doctor scans 5000 lines of mostly `phase_changed`; extract still walks all events discarding phase_changed one-by-one. |
| **Recommended fix** | Reverse-read / mmap tail; skip persisting phase_changed earlier; store byte offset of last turn_started. |
| **Confidence** | **High Confidence** |

#### M4 — Session id path not constrained (local path traversal / confused deputy)

| Field | Value |
|-|-|
| **Severity** | Medium |
| **Category** | Security |
| **Location** | `session.find_session_dir` — `group / sid` and scan |
| **Issue** | `session_id` from env/payload is joined without allowlist (`[A-Za-z0-9-]+`). Values with `..` can resolve outside the intended group directory when later resolved. |
| **Impact** | Local attacker controlling env could point extract at unexpected dirs with `events.jsonl`; mostly self-DoS or reading alternate session trees under home. |
| **Evidence** | No sanitization of `sid` before `Path` join. |
| **Recommended fix** | Reject sid unless `re.fullmatch(r"[0-9a-fA-F-]{8,64}", sid)` (UUIDv7-ish). |
| **Confidence** | **High Confidence** |

#### M5 — `install.sh` silently overwrites global Stop hook config

| Field | Value |
|-|-|
| **Severity** | Medium |
| **Category** | Reliability |
| **Location** | `install.sh` → `~/.grok/hooks/grokprint-stop.json` |
| **Issue** | No backup; no merge with user customizations; overwrites entire file. |
| **Impact** | Lost local hook tweaks; surprise after reinstall. |
| **Recommended fix** | Backup `*.bak`; idempotent merge; print diff. |
| **Confidence** | **Confirmed** |

#### M6 — Fallback session selection can attach wrong session

| Field | Value |
|-|-|
| **Severity** | Medium |
| **Category** | Reliability |
| **Location** | `find_session_dir` when `GROK_SESSION_ID` unset — “newest events.jsonl in cwd group” |
| **Issue** | CLI without session id may summarize a different concurrent session in the same workspace. |
| **Impact** | Wrong HAPPENED/NEED for operator; loop confusion. |
| **Evidence** | Lines 56–69 pick max mtime. |
| **Recommended fix** | Require session id for write path in hook (always set); CLI warn when falling back. |
| **Confidence** | **Confirmed** |

---

### LOW

#### L1 — Notification body may surface unredacted NEED via OS notifications

| Field | Value |
|-|-|
| **Severity** | Low |
| **Category** | Security |
| **Location** | `hooks/notify_print.sh` + `render.render_notification` |
| **Issue** | Desktop notifications often land in lock-screen / history; content comes from card after redaction (H1 gaps apply). |
| **Impact** | Shoulder-surfing / notification center leaks. |
| **Recommended fix** | Truncate; strip NEED details unless `GROKPRINT_NOTIFY_DETAIL=1`. |
| **Confidence** | **High Confidence** |

#### L2 — Hook stdin size unbounded

| Field | Value |
|-|-|
| **Severity** | Low |
| **Category** | Reliability |
| **Location** | `hook.main` — `sys.stdin.read()` |
| **Issue** | No max size on hook payload. |
| **Impact** | Memory spike if runner misbehaves (unlikely). |
| **Recommended fix** | Cap read (e.g. 1 MiB). |
| **Confidence** | **Needs Verification** (depends on Grok runner) |

#### L3 — No uninstall path

| Field | Value |
|-|-|
| **Severity** | Low |
| **Category** | Reliability |
| **Location** | `install.sh` only |
| **Issue** | No `uninstall.sh` to remove hook/skill/symlink. |
| **Impact** | Stale hooks after remove. |
| **Recommended fix** | Add uninstall. |
| **Confidence** | **Confirmed** |

#### L4 — CLI `doctor` exit 4 on compat probe may confuse automation

| Field | Value |
|-|-|
| **Severity** | Low |
| **Category** | Reliability |
| **Location** | `cli.cmd_doctor` |
| **Issue** | Missing turn markers → exit 4; scripts may treat as hard fail mid-session. |
| **Recommended fix** | Document exit codes; soft warn for in_progress. |
| **Confidence** | **Confirmed** |

#### L5 — Annotate mode adds scrollback noise (product risk)

| Field | Value |
|-|-|
| **Severity** | Low |
| **Category** | Visual Consistency (TUI) |
| **Location** | `hook.main` + `GROKPRINT_ANNOTATE` |
| **Issue** | Default off (good); if enabled under loops, defeats product purpose. |
| **Recommended fix** | Force-disable annotate when `loop_active`. |
| **Confidence** | **Confirmed** |

---

### INFORMATIONAL

#### I1 — No web UI / classic a11y surface

| Field | Value |
|-|-|
| **Severity** | Informational |
| **Category** | Accessibility |
| **Issue** | No HTML/CSS app; WCAG 2.2 AA N/A for DOM. CLI/markdown output is plain text (good). |
| **Recommended fix** | Keep markdown semantic headings; avoid color-only status if TUI colors added later. |
| **Confidence** | **Confirmed** |

#### I2 — No authn/authz / multi-tenant API

| Field | Value |
|-|-|
| **Severity** | Informational |
| **Category** | Security |
| **Issue** | Runs as local user; trust boundary is OS user + Grok folder-trust for project hooks. |
| **Confidence** | **Confirmed** |

#### I3 — Trademark / unofficial positioning already in README

| Field | Value |
|-|-|
| **Severity** | Informational |
| **Category** | Security (compliance-ish) |
| **Issue** | Residual brand risk for “Grok” in name; not a code vuln. |
| **Confidence** | **Confirmed** |

#### I4 — Tests do not cover adversarial redaction set

| Field | Value |
|-|-|
| **Severity** | Informational |
| **Category** | Reliability |
| **Issue** | Current redaction tests only cover ghp_/sk-/env assignment. |
| **Recommended fix** | Add fixtures from H1 probe list. |
| **Confidence** | **Confirmed** |

---

## N/A for this codebase (explicit)

| Area | Why N/A |
|-|-|
| XSS/CSRF/CORS/browser storage | No web client |
| SQL injection / DB RLS | No database |
| Server-side IDOR / multi-tenant | Single-user local |
| SSRF / webhook handlers | No outbound network in core path |
| WCAG visual contrast / touch targets | No GUI |
| Design tokens / component library | CLI only |

---

## Prioritised remediation plan

| Priority | Items | Goal |
|-|-|-|
| P0 | H1 redaction expansion + tests | Stop secret survival in cards |
| P0 | H2 default off project copy | Shrink leak surface |
| P1 | H3 turn-bound updates titles | Correctness + privacy |
| P1 | M1 atomic writes | Concurrent Stop safety |
| P2 | M3 events tail/offset | Hook latency at scale |
| P2 | M4 session_id allowlist | Local path hygiene |
| P3 | M5 install backup, L3 uninstall, L1 notify trim | Ops polish |

---

## Quick wins (low regression)

1. Expand `redaction.py` patterns + table-driven tests (H1, I4).  
2. `also_project` default False / env opt-in (H2).  
3. Validate `session_id` regex (M4).  
4. Atomic write helper (M1).  
5. Disable annotate when loop_active (L5).  

---

## Needs architecture / deeper investigation

1. **Incremental events index** (M3) — offset journal per session.  
2. **Turn-scoped updates join** (H3) — may need timestamp correlation design.  
3. **Optional secret scanning model** — beyond regex (entropy, deny-lists).  

---

## Release recommendation

### **Ship with known risks**

| Safe if… | Not safe if… |
|-|-|
| Operators treat cards as sensitive as session logs | Digests are committed, emailed, or posted publicly |
| Project copy disabled or carefully gitignored | Secrets routinely appear in tool args without stronger redaction |
| Alpha audience accepts format/break risk | Marketing as “secure audit log” or multi-user SaaS |

After P0 (H1+H2): closer to **Safe to ship** for local alpha.  
Without P0: keep **Ship with known risks**.

---

## Flow trace (reference)

```text
Grok Stop
  → python -m grokprint.hook (fail-open)
    → extract_and_write
      → find_session_dir (env/cwd)
      → events.jsonl full scan → last turn tools
      → chat_history → NEED heuristics
      → updates.jsonl tail → titles (not turn-bound)  [H3]
      → redact_card  [H1 gaps]
      → write session + project copies  [H2, M1]
  → optional annotate / notify  [L1]
```
