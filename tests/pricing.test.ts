import assert from 'node:assert/strict';
import { test } from 'node:test';
import { calculatePrice } from '../src/pricing/pricing.js';

test('sums multiple items without a discount', () => {
  assert.deepEqual(calculatePrice([
    { unitPriceCents: 1250, quantity: 2 },
    { unitPriceCents: 500, quantity: 3 },
  ]), { subtotalCents: 4000, discountCents: 0, totalCents: 4000 });
});

test('applies a percentage discount', () => {
  assert.deepEqual(calculatePrice([{ unitPriceCents: 2000, quantity: 2 }], 25), {
    subtotalCents: 4000, discountCents: 1000, totalCents: 3000,
  });
});

test('rounds the combined discount once, including half cents', () => {
  assert.deepEqual(calculatePrice([
    { unitPriceCents: 5, quantity: 1 },
    { unitPriceCents: 5, quantity: 2 },
  ], 10), { subtotalCents: 15, discountCents: 2, totalCents: 13 });
});

test('handles an empty cart, free items, and a full discount', () => {
  assert.deepEqual(calculatePrice([]), {
    subtotalCents: 0, discountCents: 0, totalCents: 0,
  });
  assert.equal(calculatePrice([{ unitPriceCents: 0, quantity: 1 }]).totalCents, 0);
  assert.equal(calculatePrice([{ unitPriceCents: 999, quantity: 1 }], 100).totalCents, 0);
});

test('rejects invalid inputs', () => {
  for (const unitPriceCents of [-1, 1.5, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1]) {
    assert.throws(() => calculatePrice([{ unitPriceCents, quantity: 1 }]), RangeError);
  }
  for (const quantity of [0, -1, 1.5, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1]) {
    assert.throws(() => calculatePrice([{ unitPriceCents: 1, quantity }]), RangeError);
  }
  for (const discount of [-1, 101, NaN, Infinity]) {
    assert.throws(() => calculatePrice([], discount), RangeError);
  }
});

test('rejects unsafe line totals and combined subtotals', () => {
  assert.throws(() => calculatePrice([
    { unitPriceCents: Number.MAX_SAFE_INTEGER, quantity: 2 },
  ]), RangeError);
  assert.throws(() => calculatePrice([
    { unitPriceCents: Number.MAX_SAFE_INTEGER, quantity: 1 },
    { unitPriceCents: 1, quantity: 1 },
  ]), RangeError);
});
