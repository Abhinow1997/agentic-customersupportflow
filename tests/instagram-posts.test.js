import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const page = readFileSync(new URL('../src/routes/dashboard/instagram-posts/+page.svelte', import.meta.url), 'utf8');

const showImageMatches = page.match(/showImage:\s*true/g) ?? [];

assert.equal(showImageMatches.length, 3);
assert.match(page, /imageSrc:\s*'\/images\/raid-sample\.jpg'/);
assert.match(page, /imageSrc:\s*'\/images\/nature-valley-sample\.jpg'/);
assert.match(page, /imageSrc:\s*'\/images\/daim-sample\.jpg'/);
assert.match(page, /function useSampleFeed\(sample\)\s*\{/);
assert.match(page, /methodSectionContent\s*=\s*sample\.methodSectionContent/);
assert.match(page, /campaignCaption\s*=\s*sample\.campaignCaption/);
assert.match(page, /Method Section Content/);
assert.match(page, /Campaign Caption Seed/);
