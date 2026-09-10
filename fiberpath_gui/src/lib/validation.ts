import Ajv, { type ValidateFunction, type ErrorObject } from "ajv";
import windSchema from "../../schemas/wind-schema.json";

let ajv: Ajv | null = null;
let validate: ValidateFunction | null = null;

function getValidator(): ValidateFunction {
  if (!ajv) {
    ajv = new Ajv({
      allErrors: true,
      strict: false, // Allow Pydantic/OpenAPI keywords like 'discriminator'
      validateFormats: false, // Don't validate formats we don't need
    });
    validate = ajv.compile(windSchema);
  }
  return validate!;
}

export interface ValidationError {
  field: string;
  message: string;
}

// Bounds the engine enforces in a Pydantic *validator* rather than a field
// constraint, so `generate_schema.py` cannot express them in wind-schema.json
// and ajv alone would accept values the planner later rejects with a 422.
// Mirrored here to keep the GUI gate at engine parity.
// Source of truth: fiberpath/planning/validators.py (MIN/MAX_WIND_ANGLE).
const MIN_WIND_ANGLE = 1;
const MAX_WIND_ANGLE = 89;

/**
 * Checks the engine constraints the JSON Schema cannot carry. Only meaningful
 * once ajv has accepted the document, so the shape can be trusted.
 */
function engineParityErrors(data: unknown): ValidationError[] {
  const layers = (data as { layers?: unknown[] } | null)?.layers;
  if (!Array.isArray(layers)) return [];

  const errors: ValidationError[] = [];
  layers.forEach((layer, index) => {
    const angle = (layer as { windAngle?: unknown } | null)?.windAngle;
    if (typeof angle !== "number") return;
    if (angle < MIN_WIND_ANGLE || angle > MAX_WIND_ANGLE) {
      errors.push({
        field: `/layers/${index}/windAngle`,
        message: `wind angle ${angle}° must be between ${MIN_WIND_ANGLE}° and ${MAX_WIND_ANGLE}°`,
      });
    }
  });
  return errors;
}

/**
 * Validates a wind definition object against the generated JSON Schema.
 * Returns structured field/message pairs for UI mapping.
 */
export function validateWindDefinition(data: unknown): {
  valid: boolean;
  errors: ValidationError[];
} {
  const validator = getValidator();
  const valid = validator(data);

  if (valid) {
    const parity = engineParityErrors(data);
    return { valid: parity.length === 0, errors: parity };
  }

  const errors: ValidationError[] = (validator.errors || []).map(
    (err: ErrorObject) => ({
      field: err.instancePath || err.schemaPath,
      message: err.message || "Validation error",
    }),
  );

  return { valid: false, errors };
}
