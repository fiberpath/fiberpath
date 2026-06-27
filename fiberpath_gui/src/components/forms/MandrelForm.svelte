<script lang="ts">
  import { projectSession } from "../../state/project-session.svelte";
  import { NUMERIC_RANGES, validateNumericRange } from "../../types/components";
  import { parseNumericInput } from "../../lib/numericFields";
  import { debounce } from "../../lib/debounce";
  import NumberField from "../../ui/NumberField.svelte";

  type Field = "diameter" | "wind_length";

  const validate = (field: Field, value: number): string | undefined =>
    field === "diameter"
      ? validateNumericRange(value, NUMERIC_RANGES.MANDREL_DIAMETER, "Diameter")
      : validateNumericRange(value, NUMERIC_RANGES.WIND_LENGTH, "Wind length");

  // minimal: live validation fires on input/blur only, not on programmatic
  // document changes (React validated via an effect on the store value). Harmless
  // until the file-load path lands — wire an $effect on the document then (#217).
  let errors = $state<Partial<Record<Field, string>>>({});

  const debouncedValidate: Record<Field, (v: number) => void> = {
    diameter: debounce((v: number) => (errors = { ...errors, diameter: validate("diameter", v) })),
    wind_length: debounce((v: number) => (errors = { ...errors, wind_length: validate("wind_length", v) })),
  };

  function onInput(field: Field, raw: string) {
    const value = parseNumericInput(raw);
    projectSession.setValidationError(
      field === "diameter" ? "mandrel.diameter" : "mandrel.wind_length",
      undefined,
    );
    projectSession.updateMandrel({ [field]: value });
    debouncedValidate[field](value);
  }

  function onBlur(field: Field, raw: string) {
    errors = { ...errors, [field]: validate(field, parseNumericInput(raw)) };
  }

  const mandrel = $derived(projectSession.document.mandrel);
  const backend = $derived(projectSession.validationErrors);
</script>

<div class="param-form">

  <NumberField
    id="mandrel-diameter"
    label="Diameter"
    unit="mm"
    step="0.1"
    min="0"
    value={mandrel.diameter}
    error={errors.diameter ?? backend["mandrel.diameter"]}
    oninput={(raw) => onInput("diameter", raw)}
    onblur={(raw) => onBlur("diameter", raw)}
  />

  <NumberField
    id="mandrel-wind-length"
    label="Wind Length"
    unit="mm"
    step="0.1"
    min="0"
    value={mandrel.wind_length}
    error={errors.wind_length ?? backend["mandrel.wind_length"]}
    oninput={(raw) => onInput("wind_length", raw)}
    onblur={(raw) => onBlur("wind_length", raw)}
  />
</div>
