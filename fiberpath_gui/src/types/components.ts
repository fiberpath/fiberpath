/**
 * Numeric range constraints shared by the config forms and layer editors.
 */

/**
 * Numeric range constraint for input validation.
 * Use this to document and enforce valid ranges for numeric inputs.
 * @example
 * ```tsx
 * const WIND_ANGLE_RANGE: NumericRange = { min: 0, max: 90, inclusive: { min: false, max: false } };
 * ```
 */
export interface NumericRange {
  /** Minimum allowed value */
  min: number;
  /** Maximum allowed value */
  max: number;
  /** Whether min/max values are inclusive (default: both true) */
  inclusive?: {
    min?: boolean;
    max?: boolean;
  };
}

/**
 * Common numeric ranges used throughout the application.
 * These constants ensure consistency in validation across components.
 */
export const NUMERIC_RANGES = {
  /** Wind angle: 1° to 89° (inclusive), matching the planner's enforced bounds
   * (90° gives cos = 0; the engine clamps to [1, 89]). */
  WIND_ANGLE: {
    min: 1,
    max: 89,
    inclusive: { min: true, max: true },
  } as NumericRange,

  /** Feed rate: 1 to 10000 mm/min */
  FEED_RATE: {
    min: 1,
    max: 10000,
    inclusive: { min: true, max: true },
  } as NumericRange,

  /** Mandrel diameter: > 0 mm */
  MANDREL_DIAMETER: {
    min: 0,
    max: Infinity,
    inclusive: { min: false, max: false },
  } as NumericRange,

  /** Wind length: > 0 mm */
  WIND_LENGTH: {
    min: 0,
    max: Infinity,
    inclusive: { min: false, max: false },
  } as NumericRange,

  /** Tow width: > 0 mm */
  TOW_WIDTH: {
    min: 0,
    max: Infinity,
    inclusive: { min: false, max: false },
  } as NumericRange,

  /** Tow thickness: > 0 mm */
  TOW_THICKNESS: {
    min: 0,
    max: Infinity,
    inclusive: { min: false, max: false },
  } as NumericRange,

  /** Pattern/Skip: positive integers */
  PATTERN_SKIP: {
    min: 1,
    max: Infinity,
    inclusive: { min: true, max: false },
  } as NumericRange,
} as const;

/**
 * Validates a number against a range constraint.
 * @param value - The value to validate
 * @param range - The range constraint
 * @param fieldName - Human-readable field name for error messages
 * @returns Error message if invalid, undefined if valid
 * @example
 * ```tsx
 * const error = validateNumericRange(45, NUMERIC_RANGES.WIND_ANGLE, "Wind Angle");
 * if (error) {
 *   console.error(error); // "Wind Angle must be between 0 and 90 (exclusive)"
 * }
 * ```
 */
export function validateNumericRange(
  value: number,
  range: NumericRange,
  fieldName: string,
): string | undefined {
  if (isNaN(value)) {
    return `${fieldName} must be a valid number`;
  }

  const { min, max, inclusive = { min: true, max: true } } = range;
  const minInclusive = inclusive.min ?? true;
  const maxInclusive = inclusive.max ?? true;

  if (minInclusive ? value < min : value <= min) {
    return `${fieldName} must be ${minInclusive ? "at least" : "greater than"} ${min}`;
  }

  if (maxInclusive ? value > max : value >= max) {
    return `${fieldName} must be ${maxInclusive ? "at most" : "less than"} ${max}`;
  }

  return undefined;
}
