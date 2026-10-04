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
- `design-md/<brand>/DESIGN.md` — 74 reference design systems (Apple, Stripe, Linear,
  Notion, …) from VoltAgent/awesome-design-md. When the user asks for a site "like X",
  read the matching DESIGN.md and follow its tokens and rules.
- `_config.yml` — excludes workspace files (design-md, CLAUDE.md, skills-lock.json) from
  the published site. Add new non-site folders to its `exclude` list.
- `.claude/skills/<skill-name>/SKILL.md` — Claude Code skills for web work.
  Add a new folder per skill (see "Adding a skill" below).
  Third-party skills installed with `npx skills add <owner/repo> -a claude-code --copy`
  are tracked in `skills-lock.json`; update them with `npx skills update`.
  Installed: `Leonxlnx/taste-skill` (design-taste-frontend, minimalist-ui,
  high-end-visual-design, redesign-existing-projects, and others) and
  `vercel-labs/agent-skills` → web-design-guidelines (UI/accessibility review), and
  `microsoft/playwright-cli` → playwright-cli (browser automation).

## Conventions for sites

- Plain static HTML/CSS/JS unless a site needs more; GitHub Pages serves files as-is
  (Jekyll runs by default, so files/folders starting with `_` or `.` are not published).
- Every page: `<!doctype html>`, `lang`, charset and viewport metas, a real `<title>`.
- Mobile-friendly layouts, no horizontal scroll at phone width.
- Use relative links inside a site so it works under `/sites/<site-name>/`.
- Keep assets for a site inside that site's folder.

## Testing sites in a browser

Use the `playwright-cli` skill. Serve the repo first, then open the page:

```bash
python3 -m http.server 8765 &   # from the repo root
playwright-cli open http://localhost:8765/sites/<site-name>/            # desktop
playwright-cli open http://localhost:8765/sites/<site-name>/ --mobile   # phone
playwright-cli screenshot
playwright-cli close
```

In cloud sessions, `.claude/hooks/session-start.sh` installs `playwright-cli` and writes
`.playwright/cli.config.json` so it uses the container's Chromium. Browser output goes to
`.playwright-cli/`; both folders are git-ignored.

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
