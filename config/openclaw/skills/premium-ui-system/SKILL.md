---
name: premium-ui-system
description: Design a premium, conversion-focused UI system with tokens, components, and spacing scale
user-invocable: true
---

## Design System Structure

**Deliverable:** Design tokens + component library spec ready for Tailwind or CSS custom properties

## Token Hierarchy
```
Primitives (raw values)
  └── Semantic tokens (purpose-named)
        └── Component tokens (component-scoped)
```

**Required token categories:**
- **Color:** primary, secondary, accent, neutral (50-900 scale), semantic (success/warning/error/info)
- **Typography:** font-family (2 max), size scale (12→14→16→18→20→24→32→40→56px), line-height, weight
- **Spacing:** 4px base unit, scale: 4/8/12/16/24/32/48/64/96/128px
- **Radius:** none/sm(4px)/md(8px)/lg(16px)/full
- **Shadow:** sm/md/lg/xl — use for elevation hierarchy
- **Motion:** duration (150ms/300ms/500ms), easing (ease-out default)

## Premium Visual Principles
- White space is a design element — use generously (minimum 64px section padding)
- Maximum 2 font families: geometric sans for UI, serif optional for editorial
- Color palette: primary palette + neutral grays + 1 accent maximum
- Hierarchy via size and weight — not color alone (accessibility)
- Micro-interactions on all interactive elements (hover, focus, active states)

## Component Specs Required
- Button (primary/secondary/ghost, sizes: sm/md/lg, states: default/hover/focus/disabled/loading)
- Input field (default/focus/error/disabled states, with helper text and error message slots)
- Card (with/without image, with/without action)
- Navigation (desktop + mobile responsive)
- Typography scale demonstration

## Output Expectations
- Tailwind config extension with all tokens as CSS variables
- Component spec document with all states described
- Accessibility notes: WCAG 2.2 AA contrast ratios for all color pairs

## Quality Criteria
- All text/background color pairs: minimum 4.5:1 contrast ratio (AA)
- System works in light mode (dark mode optional but noted)
- No more than 3 levels of elevation in shadow system
