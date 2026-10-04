---
name: new-website
description: Scaffold a new website in this repo under sites/<site-name>/ from the starter template. Use when the user wants to start, create, or set up a new website or landing page.
---

# New website

1. Get a short site name from the user (lowercase, hyphens, e.g. `bakery-shop`).
   Also ask for the site's title and a one-line description if they weren't given.
2. Create `sites/<site-name>/` and copy `template/index.html` from this skill's
   folder into it.
3. Replace the placeholders in the copy:
   - `{{TITLE}}` — the site title
   - `{{DESCRIPTION}}` — the one-line description
   If the user wants the site to look like a known brand, read
   `design-md/<brand>/DESIGN.md` and apply its colors, type, and component rules.
4. Fill in the content the user asked for, keeping the color tokens in `:root`
   and the dark-mode block so the page works in both themes.
5. Check the page at phone width (no horizontal scroll) and that links are relative.
6. Tell the user the live URL once pushed and Pages has deployed:
   `https://spenc13.github.io/sites/<site-name>/`
