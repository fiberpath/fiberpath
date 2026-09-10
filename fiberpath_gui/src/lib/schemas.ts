/**
 * Application error types and error-handling helpers.
 *
 * `.wind` validation lives in `./validation.ts`, which checks documents against
 * the generated `schemas/wind-schema.json` (plus the engine-parity bounds that
 * JSON Schema cannot express). This module deliberately carries no schema of
 * its own — a second, hand-maintained copy of the `.wind` contract is what
 * drifted in #345.
 */

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
