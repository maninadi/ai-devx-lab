export function calculateDiscount(
  subtotal: number,
  customerTier: string
): number {
  if (customerTier === "gold") {
    return subtotal * 0.10;
  }

  return 0;
}