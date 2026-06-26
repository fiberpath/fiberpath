import { z } from "zod";

// ===========================
// Tauri Command Response Schemas
// ===========================

// Compute responses (plan/simulate/plot/validate) are typed by the generated
// OpenAPI client (src/api) now, not hand-maintained here. Only the schemas for
// responses still served over the Tauri bridge (stream, CLI health) remain.

/**
 * Schema for StreamSummary response from stream_program command
 */
export const StreamSummarySchema = z.object({
  status: z.string(),
  commands: z.number().int().nonnegative(),
  total: z.number().int().nonnegative(),
  baudRate: z.number().int().positive(),
  dryRun: z.boolean(),
});

/**
 * Schema for CliHealthResponse from check_cli_health command
 */
export const CliHealthResponseSchema = z.object({
  healthy: z.boolean(),
  version: z.string().nullable(),
  errorMessage: z.string().nullable(),
});

// ===========================
// Wind File Structure Schemas
// ===========================

/**
 * Schema for MandrelParameters object in .wind files (Python backend format)
 */
export const MandrelParametersSchema = z.object({
  diameter: z.number().positive(),
  windLength: z.number().positive(),
});

/**
 * Schema for TowParameters object in .wind files (Python backend format)
 */
export const TowParametersSchema = z.object({
  width: z.number().positive(),
  thickness: z.number().positive(),
});

/**
 * Schema for HoopLayer in .wind files (Python backend format)
 */
export const WindHoopLayerSchema = z.object({
  windType: z.literal("hoop"),
  terminal: z.boolean().optional().default(false),
});

/**
 * Schema for HelicalLayer in .wind files (Python backend format)
 */
export const WindHelicalLayerSchema = z.object({
  windType: z.literal("helical"),
  // Bounds match the planner contract (PositiveFloat/PositiveInt; wind angle
  // is enforced to [1, 89]). Keeping these in sync avoids the save gate
  // accepting values the engine later rejects with a 422.
  windAngle: z.number().min(1).max(89),
  patternNumber: z.number().int().positive(),
  skipIndex: z.number().int().positive(),
  lockDegrees: z.number().positive(),
  leadInMM: z.number().positive(),
  leadOutDegrees: z.number().positive(),
  skipInitialNearLock: z.boolean().optional(),
});

/**
 * Schema for SkipLayer in .wind files (Python backend format)
 */
export const WindSkipLayerSchema = z.object({
  windType: z.literal("skip"),
  mandrelRotation: z.number(),
});

/**
 * Schema for Layer discriminated union in .wind files (Python backend format)
 */
export const WindLayerSchema = z.discriminatedUnion("windType", [
  WindHoopLayerSchema,
  WindHelicalLayerSchema,
  WindSkipLayerSchema,
]);

/**
 * Schema for complete .wind file structure (Python backend format)
 * This matches the format saved by projectToWindDefinition() and expected by the Python CLI
 */
export const WindDefinitionSchema = z.object({
  // Any 1.x minor is accepted (additive evolution); absent is treated as 1.0
  // by the backend. An incompatible major (2.0+) is rejected.
  schemaVersion: z
    .string()
    .regex(/^1\.\d+$/)
    .optional(),
  mandrelParameters: MandrelParametersSchema,
  towParameters: TowParametersSchema,
  defaultFeedRate: z.number().positive(),
  layers: z.array(WindLayerSchema),
});

// ===========================
// Type Inference Helpers
// ===========================

export type StreamSummary = z.infer<typeof StreamSummarySchema>;
export type WindDefinition = z.infer<typeof WindDefinitionSchema>;

// ===========================
// Validation Helper Functions
// ===========================

/**
 * Validates and parses data against a schema
 * @throws {ValidationError} if validation fails
 */
export function validateData<T>(
  schema: z.ZodType<T>,
  data: unknown,
  context: string,
): T {
  const result = schema.safeParse(data);
  if (!result.success) {
    const errors = result.error.issues
      .map((issue) => `${issue.path.join(".")}: ${issue.message}`)
      .join(", ");
    throw new ValidationError(`${context} validation failed: ${errors}`);
  }
  return result.data;
}

/**
 * Type guard to check if data matches schema
 */
export function isValidData<T>(
  schema: z.ZodType<T>,
  data: unknown,
): data is T {
  return schema.safeParse(data).success;
}

// ===========================
// Custom Error Classes
// ===========================

/**
 * Base error class for FiberPath application errors
 */
export class FiberPathError extends Error {
  constructor(
    message: string,
    public readonly context?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "FiberPathError";
    Object.setPrototypeOf(this, FiberPathError.prototype);
  }
}

/**
 * Error for file system operations (save, load, export)
 */
export class FileError extends FiberPathError {
  constructor(
    message: string,
    public readonly path?: string,
    public readonly operation?: "save" | "load" | "export",
    context?: Record<string, unknown>,
  ) {
    super(message, { ...context, path, operation });
    this.name = "FileError";
    Object.setPrototypeOf(this, FileError.prototype);
  }
}

/**
 * Error for validation failures (schema, runtime checks)
 */
export class ValidationError extends FiberPathError {
  constructor(
    message: string,
    public readonly errors?: Array<{ field: string; message: string }>,
    context?: Record<string, unknown>,
  ) {
    super(message, { ...context, errors });
    this.name = "ValidationError";
    Object.setPrototypeOf(this, ValidationError.prototype);
  }
}

/**
 * Error for Tauri command invocations
 */
export class CommandError extends FiberPathError {
  constructor(
    message: string,
    public readonly command?: string,
    public readonly originalError?: unknown,
    context?: Record<string, unknown>,
  ) {
    super(message, { ...context, command, originalError });
    this.name = "CommandError";
    Object.setPrototypeOf(this, CommandError.prototype);
  }
}

/**
 * Error for network/connection issues with CLI backend
 */
export class ConnectionError extends FiberPathError {
  constructor(
    message: string,
    public readonly endpoint?: string,
    context?: Record<string, unknown>,
  ) {
    super(message, { ...context, endpoint });
    this.name = "ConnectionError";
    Object.setPrototypeOf(this, ConnectionError.prototype);
  }
}

// ===========================
// Error Parsing Utilities
// ===========================

/**
 * Extracts user-friendly error message from various error types
 */
export function parseError(error: unknown): string {
  if (error instanceof FiberPathError) {
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  if (typeof error === "string") {
    return error;
  }

  if (error && typeof error === "object" && "message" in error) {
    return String(error.message);
  }

  return "An unknown error occurred";
}

/**
 * Checks if error is retryable (transient failure)
 */
export function isRetryableError(error: unknown): boolean {
  if (error instanceof ValidationError) {
    return false; // Validation errors won't fix themselves
  }

  if (error instanceof FileError) {
    // Retry file operations (might be temporary lock)
    return true;
  }

  if (error instanceof ConnectionError) {
    return true; // Network issues might resolve
  }

  if (error instanceof CommandError) {
    // Check if it's a validation vs IO error
    const message = error.message.toLowerCase();
    return !message.includes("validation") && !message.includes("invalid");
  }

  return true; // Default: retry unknown errors
}
