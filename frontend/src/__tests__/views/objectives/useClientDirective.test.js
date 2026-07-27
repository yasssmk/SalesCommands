// frontend/src/__tests__/views/objectives/useClientDirective.test.js
//
// Build-boundary guard: vitest renders outside the Next.js runtime, so it never
// catches a missing "use client" directive — a page that imports a React hook
// without it fails `next build`, not the tests. This static check closes that
// gap for the objectives view: any file under views/objectives/ that uses a
// React hook MUST declare "use client", matching the repo convention where the
// view/list entry (imported by the Server Component page) carries the directive.

import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../views/objectives');

const HOOK_RE = /\buse(State|Effect|Memo|Callback|Ref|Context|Reducer|Router|SWR|[A-Z]\w*)\s*\(/;
const DIRECTIVE_RE = /^\s*(['"])use client\1\s*;?/;

function jsxFiles(dir) {
  return readdirSync(dir).filter((f) => f.endsWith('.jsx') || f.endsWith('.js'));
}

describe('views/objectives — client-boundary directive', () => {
  const files = jsxFiles(DIR);

  it('has files to check', () => {
    expect(files.length).toBeGreaterThan(0);
  });

  files.forEach((file) => {
    it(`${file}: declares "use client" when it uses a React hook`, () => {
      const src = readFileSync(path.join(DIR, file), 'utf8');
      if (!HOOK_RE.test(src)) return; // no hook -> no directive required
      // The directive must precede the first import (Next.js rule).
      const beforeFirstImport = src.split(/^import\s/m)[0];
      expect(DIRECTIVE_RE.test(src.trimStart()) || /['"]use client['"]/.test(beforeFirstImport)).toBe(true);
    });
  });
});
