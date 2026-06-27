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
    return { valid: true, errors: [] };
  }

  const errors: ValidationError[] = (validator.errors || []).map(
    (err: ErrorObject) => ({
      field: err.instancePath || err.schemaPath,
      message: err.message || "Validation error",
    }),
  );

  return { valid: false, errors };
}
