---
name: nextjs-build
description: Build Next.js 15 App Router pages and components with TypeScript and Tailwind
user-invocable: true
---

## Implementation Standards

**Stack:** Next.js 15, React 19, TypeScript 5.x, Tailwind CSS 4, shadcn/ui

**Component rules:**
- Server Components by default — use `"use client"` only when browser APIs or state are needed
- All props typed with explicit TypeScript interfaces (no `any`)
- Error boundaries with `error.tsx` and loading states with `loading.tsx` per route segment
- Metadata exported from every `page.tsx` for SEO

## File Structure
```
app/
  (feature)/
    page.tsx          # Server component, fetches data
    _components/      # Feature-scoped components
    loading.tsx
    error.tsx
components/
  ui/                 # shadcn/ui primitives
  shared/             # Cross-feature components
```

**Performance requirements:**
- Images: always `next/image` with explicit `width`/`height` or `fill`
- Fonts: `next/font` only, no external font CDN calls
- Dynamic imports for heavy components (charts, editors)
- Target: LCP < 2.5s, CLS < 0.1, INP < 200ms

## Output Expectations
- Full working component/page code with types
- Tailwind classes only (no inline styles, no CSS modules unless justified)
- Accessible: ARIA labels, keyboard navigation, WCAG 2.2 AA
- Vitest unit test for logic-heavy components

## Quality Criteria
- `tsc --noEmit` passes with zero errors
- ESLint next/core-web-vitals ruleset passes
- Mobile-first responsive (sm → md → lg breakpoints)
