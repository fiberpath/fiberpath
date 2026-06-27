# Type Safety Reference

Complete guide to TypeScript patterns and type safety practices in FiberPath GUI.

## Overview

FiberPath GUI uses **TypeScript strict mode** for maximum type safety. This reference covers patterns for discriminated unions, type guards, error handling, and Zod integration.

## Discriminated Unions

### Layer Types

```typescript
// Base type
type BaseLayer = {
  id: string;
  terminal: boolean;
  skipEvery?: number;
};
// Specific layer types
type HoopLayer = BaseLayer & {
  windType: "hoop";
};
type HelicalLayer = BaseLayer & {
  windType: "helical";
  windAngle: number;
};
// Union type with discriminator
type Layer = HoopLayer | HelicalLayer;
```

**Discriminated Field:** `windType` uniquely identifies layer variant.

### Type Guards

```typescript
function isHoopLayer(layer: Layer): layer is HoopLayer {
  return layer.windType === "hoop";
}
function isHelicalLayer(layer: Layer): layer is HelicalLayer {
  return layer.windType === "helical";
}
// Usage
function getLayerInfo(layer: Layer): string {
  if (isHoopLayer(layer)) {
    return `Hoop layer (terminal: ${layer.terminal})`;
    // TypeScript knows layer is HoopLayer (no windAngle)
  } else if (isHelicalLayer(layer)) {
    return `Helical layer (angle: ${layer.windAngle}°)`;
    // TypeScript knows layer is HelicalLayer (has windAngle)
  } else {
    // Exhaustiveness check
    const _exhaustive: never = layer;
    throw new Error(`Unknown layer type: ${_exhaustive}`);
  }
}
```

### Exhaustive Switch

```typescript
function processLayer(layer: Layer): void {
  switch (layer.windType) {
    case "hoop":
      console.log("Processing hoop layer");
      break;
    case "helical":
      console.log(`Processing helical layer at ${layer.windAngle}°`);
      break;
    default:
      // If we add a new layer type and forget to handle it,
      // TypeScript will error here
      const _exhaustive: never = layer;
      throw new Error(`Unhandled layer type: ${_exhaustive}`);
  }
}
```

**Benefit:** Compiler enforces handling all cases.

## Zod Schema Integration

### Type Inference

```typescript
import { z } from "zod";
// Define schema
export const MandrelParametersSchema = z.object({
  diameter: z.number().positive(),
  windLength: z.number().positive(),
});
// Infer TypeScript type from schema
export type MandrelParameters = z.infer<typeof MandrelParametersSchema>;
// Equivalent to:
// type MandrelParameters = {
//   diameter: number;
//   windLength: number;
// };
```

**Benefit:** Single source of truth - runtime and compile-time validation aligned.

### Runtime Validation with Type Safety

```typescript
function validateMandrel(data: unknown): MandrelParameters {
  const result = MandrelParametersSchema.safeParse(data);
  if (!result.success) {
    throw new ValidationError(
      "Invalid mandrel parameters",
      result.error.issues
    );
  }
  return result.data; // Type: MandrelParameters
}
```

### Partial Updates

```typescript
// Schema for full object
export const LayerSchema = z.object({
  id: z.string(),
  windType: z.enum(["hoop", "helical"]),
  terminal: z.boolean(),
  skipEvery: z.number().int().positive().optional(),
});
// Schema for partial updates (all fields optional)
export const PartialLayerSchema = LayerSchema.partial();
export type Layer = z.infer<typeof LayerSchema>;
export type PartialLayer = z.infer<typeof PartialLayerSchema>;
// Usage
function updateLayer(id: string, updates: PartialLayer): void {
  // updates can be { terminal: true } or { skipEvery: 2 } etc.
}
```

## Error Handling

### Custom Error Classes

```typescript
export class CommandError extends Error {
  constructor(
    message: string,
    public command: string,
    public cause?: unknown
  ) {
    super(message);
    this.name = "CommandError";
  }
}
export class ValidationError extends Error {
  constructor(
    message: string,
    public errors: Array<{ field: string; message: string }>
  ) {
    super(message);
    this.name = "ValidationError";
  }
}
export class FileError extends Error {
  constructor(
    message: string,
    public filePath: string,
    public cause?: unknown
  ) {
    super(message);
    this.name = "FileError";
  }
}
export class ConnectionError extends Error {
  constructor(
    message: string,
    public port: string,
    public cause?: unknown
  ) {
    super(message);
    this.name = "ConnectionError";
  }
}
```

### Type-Safe Error Handling

```typescript
async function executePlan(inputPath: string): Promise<PlanSummary> {
  try {
    return await planWind(inputPath);
  } catch (error) {
    if (error instanceof CommandError) {
      console.error(`Command ${error.command} failed: ${error.message}`);
      throw error;
    } else if (error instanceof ValidationError) {
      console.error("Validation failed:", error.errors);
      throw error;
    } else if (error instanceof FileError) {
      console.error(`File error at ${error.filePath}: ${error.message}`);
      throw error;
    } else {
      // Unknown error
      console.error("Unexpected error:", error);
      throw new Error("An unexpected error occurred");
    }
  }
}
```

### Result Type Pattern

```typescript
type Result<T, E = Error> =
  | { success: true; data: T }
  | { success: false; error: E };
function safePlanWind(inputPath: string): Promise<Result<PlanSummary>> {
  return planWind(inputPath)
    .then((data) => ({ success: true as const, data }))
    .catch((error) => ({ success: false as const, error }));
}
// Usage
const result = await safePlanWind(inputPath);
if (result.success) {
  console.log(result.data.commands); // Type: PlanSummary
} else {
  console.error(result.error); // Type: Error
}
```

## Utility Types

### Partial

```typescript
type MandrelParameters = {
  diameter: number;
  windLength: number;
};
// All fields optional
type PartialMandrel = Partial<MandrelParameters>;
// Equivalent to: { diameter?: number; windLength?: number; }
```

### Required

```typescript
type OptionalConfig = {
  previewScale?: number;
  dryRun?: boolean;
};
// All fields required
type RequiredConfig = Required<OptionalConfig>;
// Equivalent to: { previewScale: number; dryRun: boolean; }
```

### Pick

```typescript
type Layer = {
  id: string;
  windType: "hoop" | "helical";
  terminal: boolean;
  skipEvery?: number;
};
// Pick specific fields
type LayerSummary = Pick<Layer, "id" | "windType">;
// Equivalent to: { id: string; windType: "hoop" | "helical"; }
```

### Omit

```typescript
// Omit specific fields
type LayerWithoutId = Omit<Layer, "id">;
// Equivalent to: { windType: "hoop" | "helical"; terminal: boolean; skipEvery?: number; }
```

### Exclude

```typescript
type OutputMode = "plot" | "simulate" | "stream" | "all";
// Exclude specific values from union
type InteractiveModes = Exclude<OutputMode, "all">;
// Equivalent to: "plot" | "simulate" | "stream"
```

### Extract

```typescript
type Action =
  | { type: "add"; payload: Layer }
  | { type: "remove"; payload: string }
  | { type: "update"; payload: { id: string; changes: Partial<Layer> } };
// Extract specific variants
type AddAction = Extract<Action, { type: "add" }>;
// Equivalent to: { type: "add"; payload: Layer }
```

### ReturnType

```typescript
function createLayer(type: LayerType): Layer {
  // ...
}
type CreatedLayer = ReturnType<typeof createLayer>;
// Equivalent to: Layer
```

### Parameters

```typescript
function updateMandrel(id: string, params: MandrelParameters): void {
  // ...
}
type UpdateMandrelParams = Parameters<typeof updateMandrel>;
// Equivalent to: [id: string, params: MandrelParameters]
```

## Advanced Patterns

### Branded Types

```typescript
// Ensure IDs are not mixed with regular strings
type LayerId = string & { __brand: "LayerId" };
type ProjectId = string & { __brand: "ProjectId" };
function createLayerId(id: string): LayerId {
  return id as LayerId;
}
function removeLayer(id: LayerId): void {
  // ...
}
// Usage
const layerId = createLayerId("layer-123");
removeLayer(layerId); // ✅ OK
const projectId: ProjectId = "proj-456" as ProjectId;
removeLayer(projectId); // ❌ Type error
```

### Const Assertions

```typescript
const config = {
  previewScale: 1,
  dryRun: false,
} as const;
// Type: { readonly previewScale: 1; readonly dryRun: false; }
// vs
const config = {
  previewScale: 1,
  dryRun: false,
};
// Type: { previewScale: number; dryRun: boolean; }
```

**Use Case:** Narrow types to literal values.

### Template Literal Types

```typescript
type CommandName = "plan" | "simulate" | "plot";
type CommandKey = `${CommandName}_command`;
// Equivalent to: "plan_command" | "simulate_command" | "plot_command"
```

### Mapped Types

```typescript
type LayerState = {
  isEditing: boolean;
  isHovered: boolean;
  isSelected: boolean;
};
// Create optional version of all fields
type OptionalLayerState = {
  [K in keyof LayerState]?: LayerState[K];
};
// Equivalent to:
// type OptionalLayerState = {
//   isEditing?: boolean;
//   isHovered?: boolean;
//   isSelected?: boolean;
// };
```

### Conditional Types

```typescript
type IsArray<T> = T extends any[] ? true : false;
type A = IsArray<string[]>; // true
type B = IsArray<number>; // false
// More practical: Unwrap array type
type Unwrap<T> = T extends Array<infer U> ? U : T;
type C = Unwrap<Layer[]>; // Layer
type D = Unwrap<number>; // number
```

## Type Assertions

### As Const

```typescript
const layers = [
  { windType: "hoop", terminal: false },
  { windType: "helical", windAngle: 45, terminal: false },
] as const;
// Type: readonly [
//   { readonly windType: "hoop"; readonly terminal: false },
//   { readonly windType: "helical"; readonly windAngle: 45; readonly terminal: false }
// ]
```

### Type Casting

```typescript
// ❌ Avoid when possible
const data = response as MandrelParameters;
// ✅ Prefer validation
const data = MandrelParametersSchema.parse(response);
```

### Non-Null Assertion

```typescript
// When you know value is not null
const layer = projectSession.selectedLayer;
const angle = layer!.helical.wind_angle;
// ⚠️ Dangerous: Runtime error if no layer is selected
// ✅ Prefer optional chaining
const angle = layer?.helical?.wind_angle;
```

## Type Narrowing

### typeof

```typescript
function processValue(value: string | number): string {
  if (typeof value === "string") {
    return value.toUpperCase(); // Type: string
  } else {
    return value.toFixed(2); // Type: number
  }
}
```

### instanceof

```typescript
try {
  await planWind(inputPath);
} catch (error) {
  if (error instanceof CommandError) {
    console.error(`Command failed: ${error.command}`);
  } else if (error instanceof Error) {
    console.error(`Error: ${error.message}`);
  } else {
    console.error("Unknown error:", error);
  }
}
```

### in operator

```typescript
type Response =
  | { status: "success"; data: PlanSummary }
  | { status: "error"; message: string };
function handleResponse(response: Response): void {
  if ("data" in response) {
    console.log(response.data.commands); // Type: PlanSummary
  } else {
    console.error(response.message); // Type: string
  }
}
```

### Equality

```typescript
type State = "idle" | "loading" | "success" | "error";
function handleState(state: State): void {
  if (state === "loading") {
    // Type: "loading"
  } else if (state === "success" || state === "error") {
    // Type: "success" | "error"
  } else {
    // Type: "idle"
  }
}
```

## Best Practices

### ✅ Do

- **Enable strict mode** in tsconfig.json
- **Infer types from schemas** with Zod
- **Use discriminated unions** for variants
- **Write type guards** for runtime type checks
- **Prefer unknown over any** for untyped data
- **Use exhaustiveness checks** in switches
- **Document complex types** with JSDoc

### ❌ Don't

- **Use `any`** (breaks type safety)
- **Ignore TypeScript errors** with `@ts-ignore`
- **Over-assert with `as`** (validate instead)
- **Create overly complex types** (keep types readable)
- **Forget to handle all union cases**

## Testing Types

### Type Tests

```typescript
import { expectType } from "tsd";
// Assert return type
expectType<MandrelParameters>(
  MandrelParametersSchema.parse({ diameter: 150, windLength: 800 })
);
// Assert discriminated union narrows correctly
const layer: Layer = { windType: "hoop", terminal: false };
if (layer.windType === "hoop") {
  expectType<HoopLayer>(layer);
}
```

### Compile-Time Tests

```typescript
// Should compile
const validLayer: Layer = { windType: "hoop", terminal: false };
// Should NOT compile (uncomment to test)
// const invalidLayer: Layer = { windType: "unknown", terminal: false };
```

## Resources

- [TypeScript Handbook](https://www.typescriptlang.org/docs/handbook/intro.html)
- [Zod Documentation](https://zod.dev/)
- [TypeScript Deep Dive](https://basarat.gitbook.io/typescript/)

## Next Steps

- [Schema Validation Guide](../guides/schemas.md) - Zod patterns
- [State Management](../architecture/state-management.md) - Typed store
- [Testing Guide](../testing.md) - Type-safe tests
