export type UiValidationField =
  | "mandrel.diameter"
  | "mandrel.wind_length"
  | "tow.width"
  | "tow.thickness"
  | "machine.defaultFeedRate"
  | "layers.helical.wind_angle"
  | "layers.helical.pattern_number"
  | "layers.helical.skip_index"
  | "layers.helical.lock_degrees"
  | "layers.helical.lead_in_mm"
  | "layers.helical.lead_out_degrees"
  | "layers.skip.mandrel_rotation";

export type UiValidationErrors = Partial<Record<UiValidationField, string>>;
