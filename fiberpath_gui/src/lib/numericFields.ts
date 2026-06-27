export function parseNumericInput(value: string, integer = false): number {
  return integer ? Number.parseInt(value, 10) : Number.parseFloat(value);
}
