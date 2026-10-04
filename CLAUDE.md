# Spenc13.github.io — web creation workspace

This repo is published by GitHub Pages at https://spenc13.github.io and is the
home base for building websites. Skills and shared resources for web work live
here and grow over time.

## Layout

- `index.html`, `privacy.html`, `logo.png` — the ALFRED landing page and privacy
  policy. These URLs are referenced by ALFRED's Google OAuth consent screen:
  do not move, rename, or delete them, and change their content only when asked.
- `sites/<site-name>/` — one folder per website. Each is served at
  `https://spenc13.github.io/sites/<site-name>/`.
- `.claude/skills/<skill-name>/SKILL.md` — Claude Code skills for web work.
  Add a new folder per skill (see "Adding a skill" below).

## Conventions for sites

- Plain static HTML/CSS/JS unless a site needs more; GitHub Pages serves files as-is
  (Jekyll runs by default, so files/folders starting with `_` or `.` are not published).
- Every page: `<!doctype html>`, `lang`, charset and viewport metas, a real `<title>`.
- Mobile-friendly layouts, no horizontal scroll at phone width.
- Use relative links inside a site so it works under `/sites/<site-name>/`.
- Keep assets for a site inside that site's folder.

## Adding a skill

Create `.claude/skills/<skill-name>/SKILL.md` with frontmatter:

```markdown
---
name: <skill-name>
description: What the skill does and when Claude should use it.
---

Step-by-step instructions...
```

Put any supporting files (templates, snippets, checklists) in the same folder.
