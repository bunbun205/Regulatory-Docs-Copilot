import { expect } from '@playwright/test';
import type { Locator, Page } from '@playwright/test';

export async function tabTo(page: Page, target: Locator) {
  for (let i = 0; i < 100; i++) {
    if (await target.evaluate(element => element === document.activeElement)) return;
    await page.keyboard.press('Tab');
  }
  await expect(target).toBeFocused();
}
export async function keyboardNavigate(page: Page, name: string) {
  const menu = page.getByRole('button', { name: 'Open navigation', exact: true });
  if (await menu.isVisible()) { await tabTo(page, menu); await page.keyboard.press('Enter'); }
  const link = page.getByRole('link', { name, exact: true }); await tabTo(page, link); await page.keyboard.press('Enter');
}
export async function accessibilityCheck(page: Page) {
  const cdp = await page.context().newCDPSession(page);
  const tree = await cdp.send('Accessibility.getFullAXTree'); await cdp.detach();
  const interactive = new Set(['button', 'link', 'textbox', 'combobox', 'checkbox', 'tab']);
  const unnamed = tree.nodes.filter(node => !node.ignored && interactive.has(String(node.role?.value)) && !String(node.name?.value ?? '').trim()).map(node => node.role?.value);
  expect(unnamed, 'Interactive controls need accessibility-tree names').toEqual([]);
  const contrast = await page.evaluate(() => {
    type Color = [number, number, number, number];
    const parse = (value: string): Color => { const parts = value.match(/[\d.]+/g)?.map(Number) ?? []; const scale = value.startsWith('color(srgb') ? 255 : 1; return [(parts[0] ?? 0) * scale, (parts[1] ?? 0) * scale, (parts[2] ?? 0) * scale, parts[3] ?? 1]; };
    const blend = (front: Color, back: Color): Color => [0, 1, 2].map(i => front[i] * front[3] + back[i] * (1 - front[3])).concat(1) as Color;
    const luminance = (color: Color) => color.slice(0, 3).map(channel => { const n = channel / 255; return n <= .04045 ? n / 12.92 : ((n + .055) / 1.055) ** 2.4; }).reduce((sum, n, i) => sum + n * [.2126, .7152, .0722][i], 0);
    const ratio = (a: Color, b: Color) => { const x = luminance(a); const y = luminance(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); };
    const failures: { text: string; ratio: number; required: number }[] = []; let checked = 0; let minimum = 21;
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode; const text = node.textContent?.trim(); const parent = node.parentElement;
      if (!text || !parent || parent.closest('[inert], [disabled], [aria-disabled="true"], script, style') || !parent.getClientRects().length || getComputedStyle(parent).visibility !== 'visible') continue;
      const closed = parent.closest('details:not([open])');
      if (closed && !closed.querySelector('summary')?.contains(parent)) continue;
      const ancestors: Element[] = []; let current: Element | null = parent;
      while (current) { ancestors.unshift(current); current = current.parentElement; }
      let background: Color = [255, 255, 255, 1]; let opacity = 1;
      for (const element of ancestors) { const style = getComputedStyle(element); background = blend(parse(style.backgroundColor), background); opacity *= Number(style.opacity); }
      const style = getComputedStyle(parent); const foreground = parse(style.color); foreground[3] *= opacity;
      const actual = ratio(blend(foreground, background), background); const large = parseFloat(style.fontSize) >= 24 || parseFloat(style.fontSize) >= 18.66 && Number(style.fontWeight) >= 700; const required = large ? 3 : 4.5;
      checked++; minimum = Math.min(minimum, actual);
      if (actual + .01 < required) failures.push({ text: text.slice(0, 90), ratio: Number(actual.toFixed(2)), required });
    }
    for (const element of Array.from(document.querySelectorAll<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>('input, textarea, select'))) {
      if (element.closest('[inert], [disabled]') || element.matches(':disabled') || !element.getClientRects().length || ['file', 'checkbox', 'hidden'].includes(element.type)) continue;
      const ancestors: Element[] = []; let current: Element | null = element; let background: Color = [255, 255, 255, 1];
      while (current) { ancestors.unshift(current); current = current.parentElement; }
      for (const ancestor of ancestors) background = blend(parse(getComputedStyle(ancestor).backgroundColor), background);
      const placeholder = !element.value && 'placeholder' in element && Boolean(element.placeholder);
      const style = getComputedStyle(element, placeholder ? '::placeholder' : null); const foreground = parse(style.color); foreground[3] *= Number(style.opacity);
      const actual = ratio(blend(foreground, background), background); checked++; minimum = Math.min(minimum, actual);
      if (actual + .01 < 4.5) failures.push({ text: `${placeholder ? 'Placeholder' : 'Control text'}: ${element.id}`, ratio: Number(actual.toFixed(2)), required: 4.5 });
      const border = getComputedStyle(element); if (parseFloat(border.borderTopWidth) > 0 && border.borderTopStyle !== 'none') {
        const borderRatio = ratio(blend(parse(border.borderTopColor), background), background);
        if (borderRatio + .01 < 3) failures.push({ text: `Control boundary: ${element.id}`, ratio: Number(borderRatio.toFixed(2)), required: 3 });
      }
    }
    return { checked, minimum: Number(minimum.toFixed(2)), failures };
  });
  expect(contrast.failures, 'Visible text contrast (disabled/inert content excluded)').toEqual([]);
  return { live_regions: tree.nodes.filter(node => !node.ignored && ['alert', 'status'].includes(String(node.role?.value))).map(node => ({ role: node.role?.value, live: node.properties?.find(property => property.name === 'live')?.value.value })), named_controls: tree.nodes.filter(node => !node.ignored && interactive.has(String(node.role?.value))).length, ...contrast };
}
