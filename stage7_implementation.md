# Stage 7: Integration & Animation Polish — Implementation Brief

> **Scope:** Finish the premium interaction layer across the existing frontend.
> **Prerequisite:** All 5 tabs and 16 panels are built, building, and type-checking cleanly.
> **Goal:** Wire the alert detection system, polish tab transitions, and ensure every panel has consistent animation/loading/error behavior.

---

## What's Already Done (Do NOT Rebuild)

These are implemented and working — do not touch unless the task specifically says to modify:

- **Staggered panel reveal** — Tab layout components (`NVDACommandTab.tsx`, etc.) already apply `animate-fade-in` + `stagger-1` through `stagger-N` classes to each panel wrapper. The CSS classes exist in `globals.css` and the keyframes/animations exist in `tailwind.config.js`.
- **Price tick flash** — `HeroPrice.tsx` already tracks `prevPrice` vs current price and applies `price-flash-green` / `price-flash-red` CSS classes (600ms animation).
- **Loading skeletons** — Every panel already renders `<LoadingSkeleton>` while `isLoading` is true.
- **Error states** — Every panel already renders `<ErrorState onRetry={...}>` when the API call fails.
- **Alert banner component** — `AlertBanner.tsx` exists with slide-in/out animation, auto-dismiss after 5s, green/red left border.
- **Alert feed panel** — `AlertFeed.tsx` exists with empty state UI and dismiss handler, but NO alert detection logic.

---

## Tasks To Complete

### Task 1: Wire Alert Detection System (F7-03) — HIGH PRIORITY

**The Problem:** `AlertFeed.tsx` has the UI for displaying alerts but no logic to detect price moves. The alert overlay zone in `App.tsx` (line 88) is an empty div. Alerts need to fire when any tracked ticker moves >1%.

**What to build:**

Create an alert context/hook that:
1. Lives in `App.tsx` (or a new context provider) so it's accessible across tabs
2. Monitors the NVDA price from `usePolling(fetchPrice, { interval: 5000 })` — compare each new tick's `changesPercentage` against a threshold
3. When `|changesPercentage| > 1.0`, generate an alert: `{ id: crypto.randomUUID(), message: "NVDA UP 2.3%", type: 'positive'|'negative', timestamp: HH:MM, ticker: 'NVDA' }`
4. Stores alerts in state (max 10, newest first)
5. Auto-dismisses after 5 seconds
6. Renders alerts in the **fixed overlay zone** (`div.fixed.top-4.right-4.z-50`) in `App.tsx` using `<AlertBanner>` components
7. Also passes alerts down to `<AlertFeed>` on the NVDA Command tab so they appear in the feed

**Files to modify:**
- `src/App.tsx` — Add alert state, detection logic, render AlertBanners in overlay zone, pass alerts to NVDACommandTab
- `src/components/tabs/NVDACommandTab.tsx` — Accept alerts prop, pass to AlertFeed
- `src/components/panels/AlertFeed.tsx` — Accept alerts as prop instead of internal empty state

**Key interfaces already defined in `AlertFeed.tsx`:**
```typescript
interface Alert {
  id: string
  message: string
  type: 'positive' | 'negative'
  timestamp: string
  ticker: string
}
```

**Existing components to use:**
```typescript
import AlertBanner from './components/ui/AlertBanner'
// AlertBanner props: { message: string, type: 'positive'|'negative', timestamp?: string, onDismiss?: () => void }
```

---

### Task 2: Tab Transition Polish (F7-04) — MEDIUM PRIORITY

**The Problem:** Currently when switching tabs, the new tab content just appears instantly (conditional rendering in `App.tsx`). The spec calls for a smooth crossfade.

**What to build:**

In `App.tsx`, wrap the tab content area with a transition effect:
1. When `activeTab` changes, briefly fade out old content, then fade in new content
2. Use the existing `animate-crossfade-in` / `animate-crossfade-out` Tailwind classes (already defined in `tailwind.config.js`: 250ms crossfade)
3. Simple approach: use a `key={activeTab}` on the content wrapper div with `animate-fade-in` class — React will unmount/remount on key change, triggering the fade-in animation each time
4. This is already partially working since tab content has `animate-fade-in` on individual panels. The improvement is making the entire content area transition as a unit.

**Files to modify:**
- `src/App.tsx` — Add key-based transition wrapper around `<main>` content

---

### Task 3: Verify Stagger Animations Are Working (F7-01) — LOW PRIORITY

**The Problem:** The `stagger-N` CSS classes set `animation-delay` but the `animate-fade-in` animation uses `forwards` fill mode. Need to verify panels start invisible (opacity: 0) so the stagger delay is visible, rather than content flashing then animating.

**What to check/fix:**

The `animate-fade-in` class is `fadeIn 400ms ease-out forwards`. The keyframe starts at `opacity: 0, scale(0.97)`. For stagger to work correctly, elements need `opacity: 0` as their initial state before the animation runs.

Add to `globals.css` under the stagger classes:
```css
.stagger-1, .stagger-2, .stagger-3, .stagger-4,
.stagger-5, .stagger-6, .stagger-7, .stagger-8 {
  opacity: 0;
}
```

This ensures panels are invisible until their stagger delay triggers the fadeIn animation (which ends at `opacity: 1` via `forwards` fill).

**Files to modify:**
- `src/styles/globals.css` — Add initial opacity rule for stagger classes

---

## Design System Reference (For Context)

### CSS Classes Available
- `.glass-panel` — primary container (blur, border, shadow, hover glow)
- `.glass-panel-inner` — nested card variant (lighter blur)
- `.skeleton` — green shimmer animation
- `.price-flash-green` / `.price-flash-red` — 600ms price tick flash
- `.tab-active` — green bottom border on active tab
- `.stagger-1` through `.stagger-8` — animation delays (0ms, 80ms, 160ms...)
- `.bg-grid` — faint green grid background
- `.bg-grain` — noise texture overlay
- `.text-glow` — green text shadow
- `.font-display` — Orbitron
- `.font-body` — Exo 2
- `.font-data` — JetBrains Mono

### Tailwind Animations (from tailwind.config.js)
- `animate-fade-in` — fadeIn 400ms ease-out forwards (scale 0.97 -> 1, opacity 0 -> 1)
- `animate-slide-in-right` — slideInRight 300ms ease-out forwards
- `animate-slide-out-right` — slideOutRight 300ms ease-in forwards
- `animate-shimmer` — shimmer 2s linear infinite
- `animate-glow-pulse` — glowPulse 2s ease-in-out infinite
- `animate-price-tick` — priceTick 600ms ease-in-out
- `animate-crossfade-in` — crossfadeIn 250ms ease-out forwards
- `animate-crossfade-out` — crossfadeOut 250ms ease-in forwards

### Color Tokens (Tailwind classes)
- `bg-base` (#0A0A0F), `bg-surface`, `bg-surface-hover`
- `text-nvda-green` (#76B900), `text-red` (#FF3B3B), `text-amber` (#FFB800)
- `text-text-primary` (#E8E8EC), `text-text-muted` (#6B6B7B)
- `border-border`, `border-border-hover`

---

## Rules

- Strict TypeScript: no `any`
- Do NOT install new packages — everything needed is already available
- Do NOT rewrite existing panel components — only modify `App.tsx`, `NVDACommandTab.tsx`, `AlertFeed.tsx`, and `globals.css`
- Run `npx tsc --noEmit` after changes to verify zero type errors
- Run `npx vite build` to verify production build passes

---

## File Map (Only Files You Need To Touch)

```
frontend/src/
├── App.tsx                                    ← MODIFY (alert system, tab transitions)
├── styles/globals.css                         ← MODIFY (stagger opacity fix)
├── components/
│   ├── ui/AlertBanner.tsx                     ← READ ONLY (understand the interface)
│   ├── panels/AlertFeed.tsx                   ← MODIFY (accept alerts as prop)
│   └── tabs/NVDACommandTab.tsx                ← MODIFY (pass alerts to AlertFeed)
```

---

*End of Stage 7 implementation brief.*
