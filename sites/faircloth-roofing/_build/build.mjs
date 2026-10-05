// Generates the service pages, the services hub and sitemap.xml.
//
//   node sites/faircloth-roofing/_build/build.mjs
//
// To add a service, add an entry to services.mjs and re-run. This folder starts
// with "_", so GitHub Pages (Jekyll) does not publish it.
import { mkdirSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { services } from './services.mjs';
import { servicePage, hubPage, sitemap } from './template.mjs';

const siteDir = join(dirname(fileURLToPath(import.meta.url)), '..');

function write(rel, html) {
  const file = join(siteDir, rel);
  mkdirSync(dirname(file), { recursive: true });
  writeFileSync(file, html);
  console.log('wrote', rel);
}

// Catch data mistakes before they ship as broken pages.
const slugs = new Set(services.map(s => s.slug));
for (const s of services) {
  if (!existsSync(join(siteDir, s.image.src))) throw new Error(`${s.slug}: missing image ${s.image.src}`);
  if (s.description.length > 160) throw new Error(`${s.slug}: description is ${s.description.length} chars (keep it under 160)`);
  for (const r of s.related) if (!slugs.has(r)) throw new Error(`${s.slug}: unknown related service "${r}"`);
}

for (const s of services) write(`services/${s.slug}/index.html`, servicePage(s, services));
write('services/index.html', hubPage(services));
write('sitemap.xml', sitemap(services));
