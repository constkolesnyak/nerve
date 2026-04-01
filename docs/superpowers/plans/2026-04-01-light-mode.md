# Light Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a light mode to the Nerve frontend with a three-way toggle (System/Light/Dark) in the NavRail.

**Architecture:** CSS custom properties define semantic color tokens, registered with Tailwind v4 via `@theme inline`. Dark values are the `:root` default; light values override via `[data-theme="light"]` and `@media (prefers-color-scheme: light)`. A Zustand store manages the user preference, persists to localStorage, and sets the `data-theme` attribute on `<html>`. An inline script in `index.html` prevents flash of wrong theme.

**Tech Stack:** Tailwind CSS 4.2.1, Zustand 5.0.11, React 19.2.0, Lucide React icons

**Spec:** `docs/superpowers/specs/2026-04-01-light-mode-design.md`

---

## File Structure

### New Files
| File | Responsibility |
|------|---------------|
| `web/src/stores/themeStore.ts` | Zustand store: preference state, localStorage persistence, `data-theme` attribute management, OS media query listener |
| `web/src/components/Layout/ThemeToggle.tsx` | Three-way cycle button (System → Light → Dark) for NavRail |

### Modified Files
| File | Change |
|------|--------|
| `web/index.html` | Add inline `<script>` in `<head>` for flash prevention |
| `web/src/index.css` | Add `@theme inline` tokens, dark/light palettes, media query; migrate prose/scrollbar/code styles to tokens; add highlight.js light overrides |
| `web/src/components/Layout/NavRail.tsx` | Import and render `ThemeToggle`; migrate hardcoded colors to tokens |
| `web/src/components/Layout/AppShell.tsx` | Migrate hardcoded colors to tokens |
| ~60 component/page files | Migrate hardcoded hex colors to semantic token classes |

---

## Color Migration Reference

This mapping applies to **all migration tasks** (Tasks 6–17). Every hardcoded hex value in Tailwind classes gets replaced with its semantic token.

### Background Classes
| Find | Replace With |
|------|-------------|
| `bg-[#0f0f0f]` | `bg-bg` |
| `bg-[#0c0c0c]` | `bg-bg-sunken` |
| `bg-[#0a0a0a]` | `bg-bg-sunken` |
| `bg-[#141414]` | `bg-surface` |
| `bg-[#151515]` | `bg-surface` |
| `bg-[#1a1a1a]` | `bg-surface-raised` |
| `bg-[#1f1f1f]` | `bg-surface-hover` |
| `bg-[#161616]` | `bg-code-bg` |
| `bg-[#12121a]` | `bg-bg-sunken` |
| `bg-[#252525]` | `bg-surface-raised` |
| `hover:bg-[#1f1f1f]` | `hover:bg-surface-hover` |
| `hover:bg-[#16162a]` | `hover:bg-surface-hover` |

### Text Classes
| Find | Replace With |
|------|-------------|
| `text-[#e0e0e0]` | `text-text` |
| `text-[#ccc]` | `text-text-secondary` |
| `text-[#cccccc]` | `text-text-secondary` |
| `text-[#888]` | `text-text-muted` |
| `text-[#888888]` | `text-text-muted` |
| `text-[#777]` | `text-text-muted` |
| `text-[#999]` | `text-text-muted` |
| `text-[#666]` | `text-text-dim` |
| `text-[#666666]` | `text-text-dim` |
| `text-[#555]` | `text-text-faint` |
| `text-[#555555]` | `text-text-faint` |
| `text-[#444]` | `text-text-faint` |
| `text-[#444444]` | `text-text-faint` |
| `hover:text-[#999]` | `hover:text-text-muted` |
| `hover:text-[#888]` | `hover:text-text-muted` |

### Border Classes
| Find | Replace With |
|------|-------------|
| `border-[#2a2a2a]` | `border-border` |
| `border-[#222]` | `border-border-subtle` |
| `border-[#222222]` | `border-border-subtle` |
| `border-[#1e1e1e]` | `border-border-subtle` |
| `border-[#333]` | `border-border-subtle` |
| `border-[#333333]` | `border-border-subtle` |
| `border-[#3a3a50]` | `border-border-subtle` |
| `focus:border-[#555]` | `focus:border-border` |
| `divide-[#2a2a2a]` | `divide-border` |
| `divide-[#222]` | `divide-border-subtle` |

### Placeholder Classes
| Find | Replace With |
|------|-------------|
| `placeholder:text-[#444]` | `placeholder:text-text-faint` |
| `placeholder:text-[#555]` | `placeholder:text-text-faint` |

### DO NOT Replace (accent/status — unchanged between themes)
- `#6366f1`, `#818cf8` — indigo accent
- `#6366f1/15`, `#6366f1/20`, `#6366f1/25`, `#6366f1/30`, `#6366f1/50` — accent with opacity
- `#10b981`, `#34d399`, `#5eead4` — green/success
- `#ef4444`, `#dc2626` — red/error
- `#f59e0b` — orange/warning
- `#eab308`, `#ca8a04` — yellow/starred
- `#a855f7`, `#7c3aed` — purple/violet
- `#22d3ee` — cyan
- `#14b8a6` — teal
- `#6b7280` — gray (note action)
- Any color used in `style={{ }}` attributes (dynamic status colors)

### Size-Prefixed Text Colors
Some classes combine a font size with a hex color in the same `text-[]` utility. These are Tailwind font-size values, NOT color values — **do not replace them**:
- `text-[11px]`, `text-[12px]`, `text-[13px]`, `text-[9px]`, `text-[10px]`, `text-[15px]` — these are font sizes

When you see `text-[#xxx]`, check that the value is a hex color (starts with `#` followed by hex digits), not a CSS size.

---

### Task 1: CSS Token System

**Files:**
- Modify: `web/src/index.css`

- [ ] **Step 1: Add theme tokens and palettes to index.css**

Add this block **after** the two `@import` lines and **before** the `body` rule. This defines the semantic tokens via Tailwind v4's `@theme inline` (preserves var() references at runtime), then sets dark values as the default, with light overrides:

```css
/* ── Theme tokens ── */
@theme inline {
  --color-bg: var(--theme-bg);
  --color-bg-sunken: var(--theme-bg-sunken);
  --color-surface: var(--theme-surface);
  --color-surface-raised: var(--theme-surface-raised);
  --color-surface-hover: var(--theme-surface-hover);
  --color-code-bg: var(--theme-code-bg);
  --color-text: var(--theme-text);
  --color-text-secondary: var(--theme-text-secondary);
  --color-text-muted: var(--theme-text-muted);
  --color-text-dim: var(--theme-text-dim);
  --color-text-faint: var(--theme-text-faint);
  --color-border: var(--theme-border);
  --color-border-subtle: var(--theme-border-subtle);
}

/* ── Dark palette (default) ── */
:root {
  --theme-bg: #0f0f0f;
  --theme-bg-sunken: #0c0c0c;
  --theme-surface: #141414;
  --theme-surface-raised: #1a1a1a;
  --theme-surface-hover: #1f1f1f;
  --theme-code-bg: #161616;
  --theme-text: #e0e0e0;
  --theme-text-secondary: #cccccc;
  --theme-text-muted: #888888;
  --theme-text-dim: #666666;
  --theme-text-faint: #444444;
  --theme-border: #2a2a2a;
  --theme-border-subtle: #222222;
}

/* ── Light palette (explicit) ── */
[data-theme="light"] {
  --theme-bg: #f5f5f5;
  --theme-bg-sunken: #ebebeb;
  --theme-surface: #ffffff;
  --theme-surface-raised: #ffffff;
  --theme-surface-hover: #e8e8e8;
  --theme-code-bg: #f0f0f0;
  --theme-text: #1a1a1a;
  --theme-text-secondary: #333333;
  --theme-text-muted: #666666;
  --theme-text-dim: #999999;
  --theme-text-faint: #bbbbbb;
  --theme-border: #d4d4d4;
  --theme-border-subtle: #e0e0e0;
}

/* ── System preference (when no explicit data-theme) ── */
@media (prefers-color-scheme: light) {
  :root:not([data-theme="dark"]) {
    --theme-bg: #f5f5f5;
    --theme-bg-sunken: #ebebeb;
    --theme-surface: #ffffff;
    --theme-surface-raised: #ffffff;
    --theme-surface-hover: #e8e8e8;
    --theme-code-bg: #f0f0f0;
    --theme-text: #1a1a1a;
    --theme-text-secondary: #333333;
    --theme-text-muted: #666666;
    --theme-text-dim: #999999;
    --theme-text-faint: #bbbbbb;
    --theme-border: #d4d4d4;
    --theme-border-subtle: #e0e0e0;
  }
}
```

- [ ] **Step 2: Migrate body styles to tokens**

Replace the current `body` rule:

```css
/* Before */
body {
  margin: 0;
  background: #0f0f0f;
  color: #e0e0e0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
}

/* After */
body {
  margin: 0;
  background: var(--theme-bg);
  color: var(--theme-text);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
}
```

- [ ] **Step 3: Verify build compiles**

Run: `cd /Users/kelsey/nerve/web && npx vite build 2>&1 | tail -5`

Expected: Build succeeds. If `@theme inline` is not supported in Tailwind 4.2.1, try `@theme` without `inline` — the values are `var()` references so they should stay dynamic. If neither works, fall back to defining `--color-*` variables directly on `:root` and using `bg-(--color-bg)` syntax in components.

- [ ] **Step 4: Commit**

```bash
cd /Users/kelsey/nerve && git add web/src/index.css
git commit -m "feat(web): add CSS theme token system with dark/light palettes"
```

---

### Task 2: Theme Store

**Files:**
- Create: `web/src/stores/themeStore.ts`

- [ ] **Step 1: Create the theme store**

```typescript
import { create } from 'zustand';

type ThemePreference = 'system' | 'light' | 'dark';

interface ThemeState {
  preference: ThemePreference;
  setTheme: (pref: ThemePreference) => void;
  cycleTheme: () => void;
}

const STORAGE_KEY = 'nerve-theme';
const CYCLE_ORDER: ThemePreference[] = ['system', 'light', 'dark'];

function applyTheme(pref: ThemePreference) {
  const el = document.documentElement;
  if (pref === 'system') {
    el.removeAttribute('data-theme');
  } else {
    el.setAttribute('data-theme', pref);
  }
}

function getInitialPreference(): ThemePreference {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === 'light' || stored === 'dark' || stored === 'system') return stored;
  return 'system';
}

export const useThemeStore = create<ThemeState>((set, get) => {
  // Apply initial theme
  const initial = getInitialPreference();
  applyTheme(initial);

  return {
    preference: initial,

    setTheme: (pref) => {
      localStorage.setItem(STORAGE_KEY, pref);
      applyTheme(pref);
      set({ preference: pref });
    },

    cycleTheme: () => {
      const current = get().preference;
      const idx = CYCLE_ORDER.indexOf(current);
      const next = CYCLE_ORDER[(idx + 1) % CYCLE_ORDER.length];
      get().setTheme(next);
    },
  };
});
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/kelsey/nerve/web && npx tsc -b --noEmit 2>&1 | tail -10`

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
cd /Users/kelsey/nerve && git add web/src/stores/themeStore.ts
git commit -m "feat(web): add Zustand theme store with localStorage persistence"
```

---

### Task 3: Flash Prevention Script

**Files:**
- Modify: `web/index.html`

- [ ] **Step 1: Add inline theme script to index.html**

Add a `<script>` tag inside `<head>`, after `<title>`. This runs synchronously before React loads, preventing a flash of the wrong theme:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Nerve</title>
    <script>
      (function() {
        var p = localStorage.getItem('nerve-theme');
        if (p === 'light' || p === 'dark') {
          document.documentElement.setAttribute('data-theme', p);
        }
      })();
    </script>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 2: Commit**

```bash
cd /Users/kelsey/nerve && git add web/index.html
git commit -m "feat(web): add flash prevention script for theme loading"
```

---

### Task 4: Theme Toggle Component

**Files:**
- Create: `web/src/components/Layout/ThemeToggle.tsx`

- [ ] **Step 1: Create the theme toggle component**

```tsx
import { Sun, Moon, Monitor } from 'lucide-react';
import { useThemeStore } from '../../stores/themeStore';

const THEME_ICONS = {
  system: Monitor,
  light: Sun,
  dark: Moon,
} as const;

const THEME_LABELS = {
  system: 'System theme',
  light: 'Light mode',
  dark: 'Dark mode',
} as const;

export function ThemeToggle() {
  const preference = useThemeStore((s) => s.preference);
  const cycleTheme = useThemeStore((s) => s.cycleTheme);
  const Icon = THEME_ICONS[preference];

  return (
    <button
      onClick={cycleTheme}
      className="w-10 h-10 rounded-lg flex items-center justify-center text-text-faint hover:text-text-muted hover:bg-surface-hover cursor-pointer transition-colors"
      title={THEME_LABELS[preference]}
    >
      <Icon size={16} />
    </button>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/kelsey/nerve/web && npx tsc -b --noEmit 2>&1 | tail -10`

Expected: No errors. If token-based classes (`text-text-faint`, etc.) cause type issues, they won't — Tailwind classes are just strings. But if the theme tokens from Task 1 didn't register properly, the classes will still work as CSS (just won't have autocomplete). The component itself has no type dependencies on the token system.

- [ ] **Step 3: Commit**

```bash
cd /Users/kelsey/nerve && git add web/src/components/Layout/ThemeToggle.tsx
git commit -m "feat(web): add ThemeToggle component for NavRail"
```

---

### Task 5: NavRail Integration

**Files:**
- Modify: `web/src/components/Layout/NavRail.tsx`

- [ ] **Step 1: Add ThemeToggle import and migrate NavRail colors**

Replace the entire `NavRail.tsx` with migrated colors and the theme toggle:

```tsx
import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { MessageSquare, FolderOpen, CheckSquare, Inbox, Activity, Brain, LogOut, Clock, Lightbulb, Sparkles, Bell, Plug, Users } from 'lucide-react';
import { useAuthStore } from '../../stores/authStore';
import { useNotificationStore } from '../../stores/notificationStore';
import { ws } from '../../api/websocket';
import { api } from '../../api/client';
import { ThemeToggle } from './ThemeToggle';

const NAV_ITEMS = [
  { path: '/chat', icon: MessageSquare, label: 'Chat' },
  { path: '/files', icon: FolderOpen, label: 'Files' },
  { path: '/tasks', icon: CheckSquare, label: 'Tasks' },
  { path: '/plans', icon: Lightbulb, label: 'Plans' },
  { path: '/skills', icon: Sparkles, label: 'Skills' },
  { path: '/mcp', icon: Plug, label: 'MCP' },
  { path: '/houseofagents', icon: Users, label: 'HoA', feature: 'hoa' as const },
  { path: '/notifications', icon: Bell, label: 'Notifs' },
  { path: '/sources', icon: Inbox, label: 'Inbox' },
  { path: '/cron', icon: Clock, label: 'Cron' },
  { path: '/memory', icon: Brain, label: 'Memory' },
  { path: '/diagnostics', icon: Activity, label: 'Diag' },
];

export function NavRail() {
  const location = useLocation();
  const navigate = useNavigate();
  const { logout } = useAuthStore();
  const pendingCount = useNotificationStore(s => s.pendingCount);
  const loadNotifications = useNotificationStore(s => s.loadNotifications);
  const [hoaEnabled, setHoaEnabled] = useState(false);

  // Load notification count + feature flags on mount
  useEffect(() => {
    loadNotifications();
    api.getHoaStatus().then(s => setHoaEnabled(s.enabled)).catch(() => {});
  }, []);

  const visibleItems = NAV_ITEMS.filter(item => {
    if (item.feature === 'hoa' && !hoaEnabled) return false;
    return true;
  });

  return (
    <div className="w-14 bg-surface border-r border-border flex flex-col items-center py-3 shrink-0">
      <div className="text-[#6366f1] font-bold text-xs mb-4 tracking-wider">N</div>

      <div className="flex-1 flex flex-col gap-1">
        {visibleItems.map(({ path, icon: Icon, label }) => {
          const active = location.pathname.startsWith(path);
          const isNotifs = path === '/notifications';
          return (
            <button
              key={path}
              onClick={() => navigate(path)}
              className={`relative w-10 h-10 rounded-lg flex flex-col items-center justify-center gap-0.5 cursor-pointer transition-colors
                ${active
                  ? 'bg-[#6366f1]/15 text-[#6366f1]'
                  : 'text-text-dim hover:text-text-muted hover:bg-surface-hover'
                }`}
              title={label}
            >
              <Icon size={18} />
              <span className="text-[9px]">{label}</span>
              {isNotifs && pendingCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-red-500 rounded-full text-[9px] text-white flex items-center justify-center font-medium">
                  {pendingCount > 9 ? '9+' : pendingCount}
                </span>
              )}
            </button>
          );
        })}
      </div>

      <div className="flex flex-col items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${ws.connected ? 'bg-emerald-400' : 'bg-red-400'}`}
             title={ws.connected ? 'Connected' : 'Disconnected'} />
        <ThemeToggle />
        <button
          onClick={logout}
          className="w-10 h-10 rounded-lg flex items-center justify-center text-text-faint hover:text-text-muted hover:bg-surface-hover cursor-pointer"
          title="Logout"
        >
          <LogOut size={16} />
        </button>
      </div>
    </div>
  );
}
```

Changes from original:
- Added `import { ThemeToggle } from './ThemeToggle';`
- `bg-[#141414]` → `bg-surface`
- `border-[#2a2a2a]` → `border-border`
- `text-[#666]` → `text-text-dim`
- `hover:text-[#999]` → `hover:text-text-muted`
- `hover:bg-[#1f1f1f]` → `hover:bg-surface-hover`
- `text-[#555]` → `text-text-faint`
- `hover:text-[#888]` → `hover:text-text-muted`
- Added `<ThemeToggle />` above the logout button

- [ ] **Step 2: Verify build**

Run: `cd /Users/kelsey/nerve/web && npx vite build 2>&1 | tail -5`

Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
cd /Users/kelsey/nerve && git add web/src/components/Layout/NavRail.tsx
git commit -m "feat(web): integrate ThemeToggle into NavRail, migrate NavRail colors"
```

---

### Task 6: Migrate Layout & Auth Components

**Files:**
- Modify: `web/src/components/Layout/AppShell.tsx`
- Modify: `web/src/components/Auth/LoginPage.tsx`

Apply the replacements from the **Color Migration Reference** at the top of this plan. For each file, open it, find every hardcoded hex class that appears in the reference table, and replace it with the semantic token class.

- [ ] **Step 1: Migrate AppShell.tsx**

One change: `bg-[#0f0f0f]` → `bg-bg`

```tsx
export function AppShell() {
  return (
    <div className="h-screen flex bg-bg">
      <NavRail />
      <div className="flex-1 min-w-0">
        <Outlet />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Migrate LoginPage.tsx**

Apply the migration reference. Key replacements:
- `bg-[#0f0f0f]` → `bg-bg`
- `bg-[#1a1a1a]` → `bg-surface-raised`
- `bg-[#252525]` → `bg-surface-raised`
- `border-[#333]` → `border-border-subtle`
- `text-[#e0e0e0]` → `text-text`

- [ ] **Step 3: Verify build**

Run: `cd /Users/kelsey/nerve/web && npx vite build 2>&1 | tail -5`

- [ ] **Step 4: Commit**

```bash
cd /Users/kelsey/nerve && git add web/src/components/Layout/AppShell.tsx web/src/components/Auth/LoginPage.tsx
git commit -m "refactor(web): migrate Layout and Auth components to theme tokens"
```

---

### Task 7: Migrate Chat Core Components

**Files:**
- Modify: `web/src/components/Chat/AssistantMessage.tsx`
- Modify: `web/src/components/Chat/StreamingMessage.tsx`
- Modify: `web/src/components/Chat/MessageList.tsx`
- Modify: `web/src/components/Chat/UserMessage.tsx`
- Modify: `web/src/components/Chat/ChatInput.tsx`
- Modify: `web/src/components/Chat/ThinkingBlock.tsx`
- Modify: `web/src/components/Chat/SelectionToolbar.tsx`
- Modify: `web/src/components/Chat/CodeBlock.tsx`

Apply the **Color Migration Reference** table to each file. Open each file, find all hardcoded hex Tailwind classes from the reference, replace with their token equivalents.

- [ ] **Step 1: Migrate AssistantMessage.tsx**

One change: `bg-[#0c0c0c]` → `bg-bg-sunken`

- [ ] **Step 2: Migrate StreamingMessage.tsx**

Replace: `bg-[#0c0c0c]` → `bg-bg-sunken`

- [ ] **Step 3: Migrate MessageList.tsx**

Replace: `text-[#444]` → `text-text-faint`

- [ ] **Step 4: Migrate UserMessage.tsx**

Replace: `border-[#333]` → `border-border-subtle`

- [ ] **Step 5: Migrate ChatInput.tsx**

Key replacements:
- `border-[#222]` → `border-border-subtle`
- `bg-[#0f0f0f]` → `bg-bg`
- `bg-[#1a1a1a]` → `bg-surface-raised`
- `border-[#2a2a2a]` → `border-border`
- `text-[#e0e0e0]` → `text-text`
- `placeholder:text-[#444]` → `placeholder:text-text-faint`
- `bg-[#151515]` → `bg-surface`
- `text-[#888]` → `text-text-muted`
- `text-[#ccc]` → `text-text-secondary`
- `text-[#444]` → `text-text-faint`
- `focus:border-[#555]` → `focus:border-border`

Do NOT replace: `#6366f1`, `#818cf8`, `#ef4444`, `#a855f7`, `#f59e0b`, `#6b7280`, `focus:border-[#6366f1]/50`

Do NOT replace `text-[15px]`, `text-[11px]`, `text-[12px]`, `text-[13px]` — these are font sizes, not colors.

- [ ] **Step 6: Migrate ThinkingBlock.tsx**

Replacements:
- `border-[#3a3a50]` → `border-border-subtle`
- `bg-[#12121a]` → `bg-bg-sunken`
- `hover:bg-[#16162a]` → `hover:bg-surface-hover`
- `text-[#555]` → `text-text-faint`
- `text-[#777]` → `text-text-muted`
- `text-[#888]` → `text-text-muted`

Do NOT replace: `text-[#6366f1]`, `bg-[#6366f1]`, `text-[13px]`

- [ ] **Step 7: Migrate SelectionToolbar.tsx**

Replacements:
- `bg-[#1e1e1e]` → `bg-surface-raised`
- `border-[#2a2a2a]` → `border-border`

- [ ] **Step 8: Migrate CodeBlock.tsx**

Replacements:
- `bg-[#1a1a1a]` → `bg-surface-raised`
- `border-[#2a2a2a]` → `border-border`
- `text-[#666]` → `text-text-dim`

- [ ] **Step 9: Verify build**

Run: `cd /Users/kelsey/nerve/web && npx vite build 2>&1 | tail -5`

- [ ] **Step 10: Commit**

```bash
cd /Users/kelsey/nerve && git add web/src/components/Chat/AssistantMessage.tsx web/src/components/Chat/StreamingMessage.tsx web/src/components/Chat/MessageList.tsx web/src/components/Chat/UserMessage.tsx web/src/components/Chat/ChatInput.tsx web/src/components/Chat/ThinkingBlock.tsx web/src/components/Chat/SelectionToolbar.tsx web/src/components/Chat/CodeBlock.tsx
git commit -m "refactor(web): migrate Chat core components to theme tokens"
```

---

### Task 8: Migrate Chat Panel Components

**Files:**
- Modify: `web/src/components/Chat/SessionSidebar.tsx`
- Modify: `web/src/components/Chat/SidePanel.tsx`
- Modify: `web/src/components/Chat/ToolCallBlock.tsx`
- Modify: `web/src/components/Chat/ToolCallGroupBlock.tsx`
- Modify: `web/src/components/Chat/BackgroundJobs.tsx`
- Modify: `web/src/components/Chat/ContextBar.tsx`
- Modify: `web/src/components/Chat/TodoPanel.tsx`
- Modify: `web/src/components/Chat/FileChangesPanel.tsx`
- Modify: `web/src/components/Chat/DiffView.tsx`

Apply the **Color Migration Reference** to each file.

- [ ] **Step 1: Migrate SessionSidebar.tsx**

High-count file (43 instances). Apply all replacements from the reference table. Watch out for `text-[9px]`, `text-[10px]`, `text-[11px]` etc. — those are font sizes, not colors.

- [ ] **Step 2: Migrate SidePanel.tsx**

Apply reference table. Do NOT replace accent colors used for tab indicators.

- [ ] **Step 3: Migrate ToolCallBlock.tsx**

Apply reference table.

- [ ] **Step 4: Migrate ToolCallGroupBlock.tsx**

Apply reference table.

- [ ] **Step 5: Migrate BackgroundJobs.tsx**

Apply reference table.

- [ ] **Step 6: Migrate ContextBar.tsx**

Apply reference table.

- [ ] **Step 7: Migrate TodoPanel.tsx**

Apply reference table.

- [ ] **Step 8: Migrate FileChangesPanel.tsx**

Apply reference table.

- [ ] **Step 9: Migrate DiffView.tsx**

Apply reference table. Note: Diff view may have green/red background colors for added/removed lines — do NOT replace those (they're semantic diff colors, not theme colors).

-[ ] **Step 10: Verify build**

Run: `cd /Users/kelsey/nerve/web && npx vite build 2>&1 | tail -5`

- [ ] **Step 11: Commit**

```bash
cd /Users/kelsey/nerve && git add web/src/components/Chat/SessionSidebar.tsx web/src/components/Chat/SidePanel.tsx web/src/components/Chat/ToolCallBlock.tsx web/src/components/Chat/ToolCallGroupBlock.tsx web/src/components/Chat/BackgroundJobs.tsx web/src/components/Chat/ContextBar.tsx web/src/components/Chat/TodoPanel.tsx web/src/components/Chat/FileChangesPanel.tsx web/src/components/Chat/DiffView.tsx
git commit -m "refactor(web): migrate Chat panel components to theme tokens"
```

---

### Task 9: Migrate Chat Tool Blocks

**Files:**
- Modify: `web/src/components/Chat/tools/SkillToolBlock.tsx`
- Modify: `web/src/components/Chat/tools/HoAToolBlock.tsx`
- Modify: `web/src/components/Chat/tools/TaskToolBlock.tsx`
- Modify: `web/src/components/Chat/tools/NotificationToolBlock.tsx`
- Modify: `web/src/components/Chat/tools/SourceToolBlock.tsx`
- Modify: `web/src/components/Chat/tools/EditToolBlock.tsx`
- Modify: `web/src/components/Chat/tools/FileToolBlock.tsx`
- Modify: `web/src/components/Chat/tools/PlanToolBlock.tsx`
- Modify: `web/src/components/Chat/tools/BashToolBlock.tsx`
- Modify: `web/src/components/Chat/tools/PlanApprovalBlock.tsx`
- Modify: `web/src/components/Chat/tools/QuestionBlock.tsx`
- Modify: `web/src/components/Chat/tools/SubagentToolBlock.tsx`
- Modify: `web/src/components/Chat/tools/MemoryToolBlock.tsx`

Apply the **Color Migration Reference** to each file.

- [ ] **Step 1: Migrate all 13 tool block files**

Open each file and apply the reference table. These files follow consistent patterns — mostly `bg-surface`, `bg-surface-raised`, `border-border`, `text-text-muted`, `text-text-faint`, `text-text-dim`, `text-text-secondary`.

Do NOT replace accent/status colors used for tool-specific indicators (green for success, red for errors, etc.).

- [ ] **Step 2: Verify build**

Run: `cd /Users/kelsey/nerve/web && npx vite build 2>&1 | tail -5`

- [ ] **Step 3: Commit**

```bash
cd /Users/kelsey/nerve && git add web/src/components/Chat/tools/
git commit -m "refactor(web): migrate Chat tool block components to theme tokens"
```

---

### Task 10: Migrate Files Components

**Files:**
- Modify: `web/src/components/Files/FileEditor.tsx`
- Modify: `web/src/components/Files/EditorTabBar.tsx`
- Modify: `web/src/components/Files/FileTree.tsx`

Apply the **Color Migration Reference** to each file.

- [ ] **Step 1: Migrate FileEditor.tsx, EditorTabBar.tsx, FileTree.tsx**

Apply reference table to all three files.

- [ ] **Step 2: Verify build**

Run: `cd /Users/kelsey/nerve/web && npx vite build 2>&1 | tail -5`

- [ ] **Step 3: Commit**

```bash
cd /Users/kelsey/nerve && git add web/src/components/Files/
git commit -m "refactor(web): migrate Files components to theme tokens"
```

---

### Task 11: Migrate Task Components

**Files:**
- Modify: `web/src/components/Tasks/TaskCard.tsx`
- Modify: `web/src/components/Tasks/TaskCreateDialog.tsx`
- Modify: `web/src/components/Tasks/TaskList.tsx`
- Modify: `web/src/components/Tasks/TaskFilters.tsx`

Apply the **Color Migration Reference** to each file.

- [ ] **Step 1: Migrate all four Task component files**

Apply reference table.

- [ ] **Step 2: Verify build**

Run: `cd /Users/kelsey/nerve/web && npx vite build 2>&1 | tail -5`

- [ ] **Step 3: Commit**

```bash
cd /Users/kelsey/nerve && git add web/src/components/Tasks/
git commit -m "refactor(web): migrate Task components to theme tokens"
```

---

### Task 12: Migrate Other Components

**Files:**
- Modify: `web/src/components/Diagnostics/DiagnosticsPanel.tsx`
- Modify: `web/src/components/Memory/MemoryBrowser.tsx`
- Modify: `web/src/components/Notifications/NotificationToast.tsx`
- Modify: `web/src/components/Sources/renderers/GitHubRenderer.tsx`
- Modify: `web/src/components/Sources/renderers/EmailRenderer.tsx`
- Modify: `web/src/components/Sources/renderers/MarkdownRenderer.tsx`

Apply the **Color Migration Reference** to each file.

- [ ] **Step 1: Migrate all six component files**

Apply reference table.

- [ ] **Step 2: Verify build**

Run: `cd /Users/kelsey/nerve/web && npx vite build 2>&1 | tail -5`

- [ ] **Step 3: Commit**

```bash
cd /Users/kelsey/nerve && git add web/src/components/Diagnostics/ web/src/components/Memory/ web/src/components/Notifications/ web/src/components/Sources/
git commit -m "refactor(web): migrate remaining components to theme tokens"
```

---

### Task 13: Migrate Pages (Part 1)

**Files:**
- Modify: `web/src/pages/MemuPage.tsx`
- Modify: `web/src/pages/SourcesPage.tsx`
- Modify: `web/src/pages/DiagnosticsPage.tsx`
- Modify: `web/src/pages/CronPage.tsx`

These are the highest-instance-count pages. Apply the **Color Migration Reference** to each file.

- [ ] **Step 1: Migrate MemuPage.tsx (127 instances)**

This is the largest file. Apply reference table carefully. Watch for font-size `text-[Npx]` values.

- [ ] **Step 2: Migrate SourcesPage.tsx (118 instances)**

Apply reference table.

- [ ] **Step 3: Migrate DiagnosticsPage.tsx (57 instances)**

Apply reference table.

- [ ] **Step 4: Migrate CronPage.tsx (50 instances)**

Apply reference table.

- [ ] **Step 5: Verify build**

Run: `cd /Users/kelsey/nerve/web && npx vite build 2>&1 | tail -5`

- [ ] **Step 6: Commit**

```bash
cd /Users/kelsey/nerve && git add web/src/pages/MemuPage.tsx web/src/pages/SourcesPage.tsx web/src/pages/DiagnosticsPage.tsx web/src/pages/CronPage.tsx
git commit -m "refactor(web): migrate high-density pages to theme tokens (Memu, Sources, Diagnostics, Cron)"
```

---

### Task 14: Migrate Pages (Part 2)

**Files:**
- Modify: `web/src/pages/SkillDetailPage.tsx`
- Modify: `web/src/pages/SkillsPage.tsx`
- Modify: `web/src/pages/NotificationsPage.tsx`
- Modify: `web/src/pages/McpServerDetailPage.tsx`
- Modify: `web/src/pages/PlanDetailPage.tsx`
- Modify: `web/src/pages/HouseOfAgentsPage.tsx`
- Modify: `web/src/pages/TaskDetailPage.tsx`

Apply the **Color Migration Reference** to each file.

- [ ] **Step 1: Migrate all seven page files**

Apply reference table to each.

- [ ] **Step 2: Verify build**

Run: `cd /Users/kelsey/nerve/web && npx vite build 2>&1 | tail -5`

- [ ] **Step 3: Commit**

```bash
cd /Users/kelsey/nerve && git add web/src/pages/SkillDetailPage.tsx web/src/pages/SkillsPage.tsx web/src/pages/NotificationsPage.tsx web/src/pages/McpServerDetailPage.tsx web/src/pages/PlanDetailPage.tsx web/src/pages/HouseOfAgentsPage.tsx web/src/pages/TaskDetailPage.tsx
git commit -m "refactor(web): migrate mid-density pages to theme tokens"
```

---

### Task 15: Migrate Pages (Part 3)

**Files:**
- Modify: `web/src/pages/PlansPage.tsx`
- Modify: `web/src/pages/McpServersPage.tsx`
- Modify: `web/src/pages/ChatPage.tsx`
- Modify: `web/src/pages/TasksPage.tsx`
- Modify: `web/src/pages/FilesPage.tsx`

Apply the **Color Migration Reference** to each file.

- [ ] **Step 1: Migrate all remaining page files**

Apply reference table.

- [ ] **Step 2: Verify build**

Run: `cd /Users/kelsey/nerve/web && npx vite build 2>&1 | tail -5`

- [ ] **Step 3: Commit**

```bash
cd /Users/kelsey/nerve && git add web/src/pages/PlansPage.tsx web/src/pages/McpServersPage.tsx web/src/pages/ChatPage.tsx web/src/pages/TasksPage.tsx web/src/pages/FilesPage.tsx
git commit -m "refactor(web): migrate remaining pages to theme tokens"
```

---

### Task 16: Migrate index.css Styles

**Files:**
- Modify: `web/src/index.css`

- [ ] **Step 1: Migrate scrollbar styles**

```css
/* Before */
::-webkit-scrollbar-thumb { background: #333; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #444; }

/* After */
::-webkit-scrollbar-thumb { background: var(--theme-border-subtle); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--theme-border); }
```

- [ ] **Step 2: Migratemarkdown styles**

```css
/* Before */
.markdown-content blockquote { border-left: 3px solid #444; padding-left: 1em; margin: 0.5em 0; color: #999; }
.markdown-content th, .markdown-content td { border: 1px solid #333; padding: 0.4em 0.8em; text-align: left; }
.markdown-content th { background: #1a1a1a; font-weight: 600; }
.markdown-content tr:nth-child(even) { background: #151515; }
.markdown-content hr { border: none; border-top: 1px solid #333; margin: 1em 0; }

/* After */
.markdown-content blockquote { border-left: 3px solid var(--theme-text-faint); padding-left: 1em; margin: 0.5em 0; color: var(--theme-text-muted); }
.markdown-content th, .markdown-content td { border: 1px solid var(--theme-border-subtle); padding: 0.4em 0.8em; text-align: left; }
.markdown-content th { background: var(--theme-surface-raised); font-weight: 600; }
.markdown-content tr:nth-child(even) { background: var(--theme-surface); }
.markdown-content hr { border: none; border-top: 1px solid var(--theme-border-subtle); margin: 1em 0; }
```

- [ ] **Step 3: Migrate inline code and code block styles**

```css
/* Before */
.markdown-content code:not(pre code) {
  background: #252525;
  padding: 0.15em 0.4em;
  border-radius: 3px;
  font-size: 0.9em;
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
}
.markdown-content pre {
  background: #161616;
  border: 1px solid #2a2a2a;
  border-radius: 6px;
  padding: 1em;
  overflow-x: auto;
  margin: 0.5em 0;
  font-size: 0.85em;
}

/* After */
.markdown-content code:not(pre code) {
  background: var(--theme-surface-raised);
  padding: 0.15em 0.4em;
  border-radius: 3px;
  font-size: 0.9em;
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
}
.markdown-content pre {
  background: var(--theme-code-bg);
  border: 1px solid var(--theme-border);
  border-radius: 6px;
  padding: 1em;
  overflow-x: auto;
  margin: 0.5em 0;
  font-size: 0.85em;
}
```

- [ ] **Step 4: Verify build**

Run: `cd /Users/kelsey/nerve/web && npx vite build 2>&1 | tail -5`

- [ ] **Step 5: Commit**

```bash
cd /Users/kelsey/nerve && git add web/src/index.css
git commit -m "refactor(web): migrate index.css prose/scrollbar/code styles to theme tokens"
```

---

### Task 17: Highlight.js Light Theme Overrides

**Files:**
- Modify: `web/src/index.css`

- [ ] **Step 1: Add highlight.js light mode overrides**

The app imports `highlight.js/styles/github-dark.min.css`. Rather than dynamically swapping stylesheets, override the key highlight.js colors for light mode. Add this block at the end of `index.css`, before the animation keyframes:

```css
/* ── Highlight.js light mode overrides ── */
[data-theme="light"] .hljs,
:root:not([data-theme="dark"]) .hljs {
  color: #24292e;
  background: var(--theme-code-bg);
}

@media (prefers-color-scheme: light) {
  :root:not([data-theme="dark"]) .hljs {
    color: #24292e;
    background: var(--theme-code-bg);
  }
  :root:not([data-theme="dark"]) .hljs-comment,
  :root:not([data-theme="dark"]) .hljs-quote { color: #6a737d; }
  :root:not([data-theme="dark"]) .hljs-keyword,
  :root:not([data-theme="dark"]) .hljs-selector-tag { color: #d73a49; }
  :root:not([data-theme="dark"]) .hljs-string,
  :root:not([data-theme="dark"]) .hljs-addition { color: #032f62; }
  :root:not([data-theme="dark"]) .hljs-number,
  :root:not([data-theme="dark"]) .hljs-literal { color: #005cc5; }
  :root:not([data-theme="dark"]) .hljs-built_in,
  :root:not([data-theme="dark"]) .hljs-type { color: #e36209; }
  :root:not([data-theme="dark"]) .hljs-title,
  :root:not([data-theme="dark"]) .hljs-section,
  :root:not([data-theme="dark"]) .hljs-name { color: #6f42c1; }
  :root:not([data-theme="dark"]) .hljs-attr,
  :root:not([data-theme="dark"]) .hljs-attribute { color: #005cc5; }
  :root:not([data-theme="dark"]) .hljs-variable { color: #e36209; }
  :root:not([data-theme="dark"]) .hljs-deletion { color: #b31d28; background: #ffeef0; }
  :root:not([data-theme="dark"]) .hljs-addition { color: #22863a; background: #f0fff4; }
}

[data-theme="light"] .hljs-comment,
[data-theme="light"] .hljs-quote { color: #6a737d; }
[data-theme="light"] .hljs-keyword,
[data-theme="light"] .hljs-selector-tag { color: #d73a49; }
[data-theme="light"] .hljs-string,
[data-theme="light"] .hljs-addition { color: #032f62; }
[data-theme="light"] .hljs-number,
[data-theme="light"] .hljs-literal { color: #005cc5; }
[data-theme="light"] .hljs-built_in,
[data-theme="light"] .hljs-type { color: #e36209; }
[data-theme="light"] .hljs-title,
[data-theme="light"] .hljs-section,
[data-theme="light"] .hljs-name { color: #6f42c1; }
[data-theme="light"] .hljs-attr,
[data-theme="light"] .hljs-attribute { color: #005cc5; }
[data-theme="light"] .hljs-variable { color: #e36209; }
[data-theme="light"] .hljs-deletion { color: #b31d28; background: #ffeef0; }
[data-theme="light"] .hljs-addition { color: #22863a; background: #f0fff4; }
```

These colors match the GitHub Light highlight.js theme.

- [ ] **Step 2: Verify build**

Run: `cd /Users/kelsey/nerve/web && npx vite build 2>&1 | tail -5`

- [ ] **Step 3: Commit**

```bash
cd /Users/kelsey/nerve && git add web/src/index.css
git commit -m "feat(web): add highlight.js light mode overrides for code blocks"
```

---

### Task 18: Final Verification & Cleanup

- [ ] **Step 1: Search for remaining hardcoded theme colors**

Run a grep to find any hex colors we missed. Search for the background/text/border hex values that should have been migrated:

```bash
cd /Users/kelsey/nerve/web/src && grep -rn --include="*.tsx" --include="*.ts" -E '(bg|text|border|divide|placeholder:text)-\[#(0f0f0f|0c0c0c|0a0a0a|141414|151515|1a1a1a|1f1f1f|161616|12121a|252525|e0e0e0|ccc|cccccc|888|888888|777|666|666666|555|555555|444|444444|2a2a2a|222|222222|1e1e1e|333|333333|3a3a50)\]' . | head -50
```

Expected: No matches. If any remain, migrate them using the reference table.

- [ ] **Step 2: Full build verification**

```bash
cd /Users/kelsey/nerve/web && npx tsc -b --noEmit && npx vite build
```

Expected: TypeScript compiles with no errors, Vite build succeeds.

- [ ] **Step 3: Manual smoke test**

Start the dev server and verify:
```bash
cd /Users/kelsey/nerve/web && npx vite dev
```

Check these in the browser:
1. Default (system) theme matches your OS preference
2. Click the theme toggle in NavRail — cycles through System (Monitor) → Light (Sun) → Dark (Moon)
3. Dark mode looks identical to before (no visual regressions)
4. Light mode is readable: backgrounds are light gray/white, text is dark, borders are visible
5. Code blocks have correct syntax highlighting in both themes
6. Refresh the page — theme preference persists (no flash)
7. Markdown tables, blockquotes, and inline code render correctly in both themes

- [ ] **Step 4: Commit any remaining fixes**

If the smoke test revealed issues, fix them and commit:

```bash
cd /Users/kelsey/nerve && git add -A
git commit -m "fix(web): address light mode visual issues from smoke test"
```
