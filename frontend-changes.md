# Frontend Changes

## Dark/Light Theme Toggle

### Files Modified

- `frontend/index.html`
- `frontend/style.css`
- `frontend/script.js`

---

### `frontend/index.html`

- Added a `<button id="themeToggle" class="theme-toggle">` element with two inline SVGs:
  - `.icon-sun` (sun icon) — visible in dark mode; clicking switches to light
  - `.icon-moon` (moon icon) — visible in light mode; clicking switches to dark
- Button is placed outside `.container`, directly before the `<script>` tags, so `position: fixed` keeps it in the top-right corner regardless of layout.
- Bumped CSS cache-bust version `style.css?v=12` → `v=13`.
- Bumped JS cache-bust version `script.js?v=11` → `v=12`.

---

### `frontend/style.css`

**New CSS variable: `--code-bg`**  
Added to `:root` so inline code and pre blocks use a theme-aware background instead of a hardcoded `rgba(0,0,0,0.2)` that was too dark on light backgrounds.

**New block: `[data-theme="light"]`**  
Overrides every CSS custom property with light-mode values:

| Variable | Light value |
|---|---|
| `--background` | `#f8fafc` |
| `--surface` | `#ffffff` |
| `--surface-hover` | `#f1f5f9` |
| `--text-primary` | `#0f172a` |
| `--text-secondary` | `#64748b` |
| `--border-color` | `#e2e8f0` |
| `--shadow` | `0 4px 6px -1px rgba(0,0,0,0.08)` |
| `--welcome-bg` | `#eff6ff` |
| `--code-bg` | `rgba(0,0,0,0.06)` |

Primary/accent colours (`--primary-color`, `--primary-hover`, `--user-message`, `--focus-ring`) are identical in both themes.

**Smooth transition rule**  
Added a multi-selector transition block targeting layout and content elements (`body`, `.sidebar`, `.chat-messages`, `.message-content`, `#chatInput`, etc.) so `background-color`, `color`, and `border-color` all animate over 0.3 s when the theme changes. Existing per-element `transition: all 0.2s` rules (on buttons, inputs) are untouched.

**Source chip**  
Changed `.source-chip` background from `var(--surface)` to `var(--background)` and added a `1px solid var(--border-color)` border so chips are visually distinct from the assistant message bubble in light mode.

**`.theme-toggle` styles**  
- `position: fixed; top: 1rem; right: 1rem; z-index: 1000` — always visible in top-right corner.
- 40 × 40 px circle, matches existing surface/border variables so it adapts automatically to both themes.
- Hover: slight scale-up + primary colour icon + shadow.
- Focus: `box-shadow: 0 0 0 3px var(--focus-ring)` — keyboard-navigable, consistent with other focusable elements.
- Active: scale-down for tactile click feedback.

**Icon visibility**  
`.icon-sun` is `display: block` by default (dark mode); `.icon-moon` is `display: none`.  
`[data-theme="light"]` inverts this so the correct icon is always shown.

---

### `frontend/script.js`

**`initTheme()`**  
Called at the top of `DOMContentLoaded`. Reads `localStorage.getItem('theme')` and, if the saved value is `'light'`, sets `data-theme="light"` on `<html>` before the first paint — no flash of the wrong theme.

**`toggleTheme()`**  
Reads the current `data-theme` attribute on `document.documentElement`:
- If `'light'` → removes the attribute (reverts to dark) and saves `'dark'` to `localStorage`.
- Otherwise → sets `data-theme="light"` and saves `'light'` to `localStorage`.

**Event listener**  
Wired in `setupEventListeners()`:
```js
document.getElementById('themeToggle').addEventListener('click', toggleTheme);
```
