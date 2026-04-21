---
name: elementor-section-build
description: Build Elementor Pro sections and containers with responsive layout and performance best practices
version: 1
---

## Build Standards

**Target:** Elementor Pro 3.x with Containers (Flexbox), not legacy Sections/Columns

**Structure per section:**
- Outer Container: full-width, set min-height via custom CSS (not fixed px)
- Inner Container: max-width 1200px, centered, responsive padding
- Mobile-first: design for 375px → tablet 768px → desktop 1200px+
- Never use absolute positioning for layout — use flex/grid only

## Implementation Steps
1. Define section purpose: hero / features / testimonials / CTA / FAQ
2. Set Container layout: direction, align-items, justify-content
3. Apply typography from site kit (Global Fonts only — no inline font-size overrides)
4. Apply colors from Global Colors only (no hardcoded hex in widget settings)
5. Set responsive visibility and spacing for each breakpoint
6. Optimize images: WebP format, lazy load on all below-fold images

## Performance Rules
- No custom JS in Elementor widgets — use WordPress `wp_enqueue_script` properly
- CSS custom classes only — no `#id` selectors (specificity issues)
- Limit animations: entrance effects only, duration ≤ 0.5s, `prefers-reduced-motion` respected
- Elementor Custom Code for CSS injection (not `<style>` in HTML widget)

## Output Expectations
- JSON export of Elementor template (`.json`) ready for import
- Written description of layout structure for human review
- List of Global Colors and Fonts used (to verify site kit compliance)

## Quality Criteria
- CLS < 0.1 (no layout shift from lazy-loaded images without dimensions)
- Section renders correctly on mobile (375px), tablet (768px), desktop (1440px)
- No Elementor deprecation warnings in console
