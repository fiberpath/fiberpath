<script lang="ts">
  import { projectSession } from "../../state/project-session.svelte";
  import { parseNumericInput } from "../../lib/numericFields";
  import { debounce } from "../../lib/debounce";
  import NumberField from "../../ui/NumberField.svelte";

  // Feed-rate validation is bespoke (not a NUMERIC_RANGES entry) — keep the exact
  // messages the React form used for behaviour parity.
  const validate = (value: number): string | undefined => {
    if (Number.isNaN(value) || value <= 0) {
      return "Feed rate must be greater than 0";
    }
    if (value > 10000) {
      return "Feed rate seems unreasonably high";
    }
    return undefined;
  };

  // minimal: see MandrelForm — live validation fires on input/blur only;
  // programmatic-document-change validation lands with the load path (#217).
  let error = $state<string | undefined>(undefined);

  const debouncedValidate = debounce((v: number) => (error = validate(v)));

  function onInput(raw: string) {
    const value = parseNumericInput(raw);
    projectSession.setValidationError("machine.defaultFeedRate", undefined);
    projectSession.updateDefaultFeedRate(value);
    debouncedValidate(value);
  }

  function onBlur(raw: string) {
    error = validate(parseNumericInput(raw));
  }

  const feedRate = $derived(projectSession.document.defaultFeedRate);
  const backend = $derived(projectSession.validationErrors);
</script>

<div class="param-form">

  <NumberField
    id="defaultFeedRate"
    label="Default Feed Rate"
    unit="mm/min"
    step="100"
    min="1"
    max="10000"
    value={feedRate}
    error={error ?? backend["machine.defaultFeedRate"]}
    oninput={onInput}
    onblur={onBlur}
  />
</div>
