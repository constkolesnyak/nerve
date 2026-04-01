# Light Mode for Nerve Frontend

**Date:** 2026-04-01
**Status:** Design approved, pending implementation

## Goal

Add a practical light mode to the Nerve frontend for daytime/bright environment use. The implementation must preserve the exact current dark theme appearance so changes can be committed upstream.

## Approach

Tailwind CSS v4 `@theme` + CSS custom properties. Semantic color tokens are defined as CSS variables, registered with Tailwind so they work as first-class utility classes (e.g., `bg-surface`, `text-muted`). Theme switching is handled at the CSS level via a `data-theme` attribute on `<html>`, with no component-level awareness of themes.

## Color Token System

13 semantic tokens across three categories replace ~321 hardcoded hex values.

### Backgrounds (6 tokens)

| Token | Tailwind Class | Dark Value | Light Value | Usage |
|-------|---------------|------------|-------------|-------|
| `--color-bg` | `bg-bg` | `#0f0f0f` | `#f5f5f5` | Main page background |
| `--color-bg-sunken` | `bg-bg-sunken` | `#0c0c0c` | `#ebebeb` | Recessed areas (assistant messages, side panels) |
| `--color-surface` | `bg-surface` | `#141414` | `#ffffff` | Cards, nav rail, raised surfaces |
| `--color-surface-raised` | `bg-surface-raised` | `#1a1a1a` | `#ffffff` | Inputs, search boxes |
| `--color-surface-hover` | `bg-surface-hover` | `#1f1f1f` | `#e8e8e8` | Hover states on interactive surfaces |
| `--color-code-bg` | `bg-code-bg` | `#161616` | `#f0f0f0` | Code block backgrounds |

### Text (5 tokens)

| Token | Tailwind Class | Dark Value | Light Value | Usage |
|-------|---------------|------------|-------------|-------|
| `--color-text` | `text-text` | `#e0e0e0` | `#1a1a1a` | Primary body text |
| `--color-text-secondary` | `text-text-secondary` | `#cccccc` | `#333333` | Secondary labels, input text |
| `--color-text-muted` | `text-text-muted` | `#888888` | `#666666` | Placeholder text, muted content |
| `--color-text-dim` | `text-text-dim` | `#666666` | `#999999` | Dim icons, disabled elements |
| `--color-text-faint` | `text-text-faint` | `#444444` | `#bbbbbb` | Barely visible labels, ghost text |

### Borders (2 tokens)

| Token | Tailwind Class | Dark Value | Light Value | Usage |
|-------|---------------|------------|-------------|-------|
| `--color-border` | `border-border` | `#2a2a2a` | `#d4d4d4` | Default borders |
| `--color-border-subtle` | `border-border-subtle` | `#222222` | `#e0e0e0` | Subtle dividers |

### Unchanged Colors

Accent and status colors remain constant across themes:

- **Accent:** `#6366f1` (indigo), `#818cf8` (hover)
- **Success:** `#10b981`, `#34d399`, `#5eead4`
- **Error:** `#ef4444`, `#dc2626`
- **Warning:** `#f59e0b`
- **Starred:** `#eab308`, `#ca8a04`
- **Purple/Violet:** `#a855f7`, `#7c3aed`
- **Cyan:** `#22d3ee`
- **Teal:** `#14b8a6`

Opacity-based accent variants (e.g., `bg-[#6366f1]/15`) also remain unchanged since the base accent color is constant.

## Theme Switching Mechanism

### CSS Layer (`index.css`)

Tokens defined using Tailwind v4's `@theme` directive. Dark values are the `:root` default. Light values override via `[data-theme="light"]` selector. When preference is "system", a `@media (prefers-color-scheme: light)` block provides the override.

```css
@theme {
  --color-bg: var(--theme-bg);
  --color-surface: var(--theme-surface);
  /* ... etc */
}

:root {
  --theme-bg: #0f0f0f;
  --theme-surface: #141414;
  /* ... dark defaults */
}

@media (prefers-color-scheme: light) {
  :root:not([data-theme="dark"]) {
    --theme-bg: #f5f5f5;
    --theme-surface: #ffffff;
    /* ... light overrides */
  }
}

[data-theme="light"] {
  --theme-bg: #f5f5f5;
  --theme-surface: #ffffff;
  /* ... light overrides */
}
```

### Zustand Store (`themeStore.ts`)

New store managing user preference:

- **State:** `preference: 'system' | 'light' | 'dark'`
- **Persistence:** Reads/writes `localStorage` key `nerve-theme`
- **Behavior on init:**
  1. Read preference from localStorage (default: `system`)
  2. Set `data-theme` attribute on `<html>` (omit attribute for system, set `"light"` or `"dark"` for explicit choices)
  3. If system: attach `matchMedia('(prefers-color-scheme: dark)')` listener for live OS changes
- **Actions:** `setTheme(preference)` — updates store, localStorage, and `<html>` attribute
- **Cycle helper:** `cycleTheme()` — rotates System → Light → Dark → System

### Flash Prevention (`index.html`)

Inline `<script>` in `<head>`, before React loads:

```js
(function() {
  const pref = localStorage.getItem('nerve-theme');
  if (pref === 'light' || pref === 'dark') {
    document.documentElement.setAttribute('data-theme', pref);
  }
})();
```

This runs synchronously before first paint, preventing a flash of the wrong theme. When preference is `system`, no attribute is set and the CSS `@media` query handles it natively.

## NavRail Toggle

Located at the bottom of the NavRail, matching existing icon styling.

- **Sun icon** (`lucide-react` `Sun`) — light mode active
- **Moon icon** (`lucide-react` `Moon`) — dark mode active
- **Monitor icon** (`lucide-react` `Monitor`) — system mode active (default)

Single click cycles: System → Light → Dark → System. Tooltip displays current mode name. Uses the same icon size, padding, and hover treatment as existing NavRail items.

## Special Cases

### Code Syntax Highlighting

Currently imports `highlight.js/styles/github-dark.min.css` globally in `index.css`. For light mode, the `github.min.css` stylesheet is needed. Two options:

Override highlight.js CSS variables in the light theme block within `index.css`. Highlight.js themes are just CSS — we override the key color properties for light mode rather than dynamically swapping stylesheets.

### Inline Style Colors

A handful of components use `style={{ borderLeftColor: config.color }}` for dynamic status colors (subagent types, session indicators). These pull from config objects with semantic color values and don't need migration — they're already theme-independent.

### Markdown/Prose Styling

`index.css` contains hardcoded colors for markdown tables, blockquotes, links, horizontal rules, and other prose elements. These get migrated to use `var(--color-*)` references alongside the component migration.

### Scrollbar Styling

Custom scrollbar colors in `index.css` (`::-webkit-scrollbar-thumb`, etc.) need light theme variants using the border/surface tokens.

## Migration Strategy

### Hex-to-Token Mapping

Each hardcoded hex value maps to exactly one semantic token:

| Hex Values | Token |
|-----------|-------|
| `#0f0f0f` | `bg` |
| `#0c0c0c`, `#0a0a0a` | `bg-sunken` |
| `#141414`, `#151515` | `surface` |
| `#1a1a1a` | `surface-raised` |
| `#1f1f1f` | `surface-hover` |
| `#161616` | `code-bg` |
| `#e0e0e0` | `text` |
| `#ccc`, `#cccccc` | `text-secondary` |
| `#888`, `#888888` | `text-muted` |
| `#666`, `#666666` | `text-dim` |
| `#555`, `#444`, `#444444` | `text-faint` |
| `#2a2a2a` | `border` |
| `#222`, `#222222`, `#1e1e1e`, `#333` | `border-subtle` |

### File-by-File Migration

1. Define all tokens and both palettes in `index.css`
2. Migrate component files one at a time, replacing `bg-[#0f0f0f]` → `bg-bg`, `text-[#e0e0e0]` → `text-text`, `border-[#2a2a2a]` → `border-border`, etc.
3. Migrate `index.css` prose/markdown rules to `var(--color-*)` references
4. After each file: verify dark theme renders identically (no visual regressions)

### Verification

- Dark theme must be pixel-identical after migration
- Light theme must be readable and visually coherent
- System preference must respond to OS theme changes in real time
- Preference must persist across page reloads via localStorage
- No flash of wrong theme on initial load

## Files to Create

- `web/src/stores/themeStore.ts` — Zustand theme store
- `web/src/components/Layout/ThemeToggle.tsx` — NavRail toggle component

## Files to Modify

- `web/index.html` — Add inline theme script in `<head>`
- `web/src/index.css` — Token definitions, theme palettes, prose/scrollbar migration
- `web/src/components/Layout/NavRail.tsx` — Add ThemeToggle component
- `web/src/components/Layout/AppShell.tsx` — Migrate colors
- `web/src/components/Chat/AssistantMessage.tsx` — Migrate colors
- `web/src/components/Chat/ChatInput.tsx` — Migrate colors
- `web/src/components/Chat/SidePanel.tsx` — Migrate colors
- `web/src/components/Chat/SessionSidebar.tsx` — Migrate colors
- `web/src/components/Chat/ToolCallBlock.tsx` — Migrate colors
- `web/src/components/Chat/ThinkingBlock.tsx` — Migrate colors
- `web/src/components/Chat/SelectionToolbar.tsx` — Migrate colors
- *(plus ~30 other component files with hardcoded colors)*

## Out of Scope

- Custom themes or theme builder UI
- Per-user theme sync (server-side storage)
- Accent color customization
- Animated theme transitions
