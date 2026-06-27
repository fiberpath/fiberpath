<script lang="ts">
  import { projectSession } from "../../state/project-session.svelte";
  import { NUMERIC_RANGES, validateNumericRange } from "../../types/components";
  import { parseNumericInput } from "../../lib/numericFields";
  import { debounce } from "../../lib/debounce";
  import NumberField from "../../ui/NumberField.svelte";

  type Field = "width" | "thickness";

  const validate = (field: Field, value: number): string | undefined =>
    field === "width"
      ? validateNumericRange(value, NUMERIC_RANGES.TOW_WIDTH, "Width")
      : validateNumericRange(value, NUMERIC_RANGES.TOW_THICKNESS, "Thickness");

  // minimal: see MandrelForm — live validation fires on input/blur only;
  // programmatic-document-change validation lands with the load path (#217).
  let errors = $state<Partial<Record<Field, string>>>({});

  const debouncedValidate: Record<Field, (v: number) => void> = {
    width: debounce((v: number) => (errors = { ...errors, width: validate("width", v) })),
    thickness: debounce((v: number) => (errors = { ...errors, thickness: validate("thickness", v) })),
  };

  function onInput(field: Field, raw: string) {
    const value = parseNumericInput(raw);
    projectSession.setValidationError(
      field === "width" ? "tow.width" : "tow.thickness",
      undefined,
    );
    projectSession.updateTow({ [field]: value });
    debouncedValidate[field](value);
  }

  function onBlur(field: Field, raw: string) {
    errors = { ...errors, [field]: validate(field, parseNumericInput(raw)) };
  }

  const tow = $derived(projectSession.document.tow);
  const backend = $derived(projectSession.validationErrors);
</script>

<div class="param-form">

  <NumberField
    id="tow-width"
    label="Width"
    unit="mm"
    step="0.1"
    min="0"
    value={tow.width}
    error={errors.width ?? backend["tow.width"]}
    oninput={(raw) => onInput("width", raw)}
    onblur={(raw) => onBlur("width", raw)}
  />

  <NumberField
    id="tow-thickness"
    label="Thickness"
    unit="mm"
    step="0.01"
    min="0"
    value={tow.thickness}
    error={errors.thickness ?? backend["tow.thickness"]}
    oninput={(raw) => onInput("thickness", raw)}
    onblur={(raw) => onBlur("thickness", raw)}
  />
</div>
