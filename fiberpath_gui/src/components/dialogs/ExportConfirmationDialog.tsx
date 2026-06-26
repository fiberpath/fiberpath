import { useEffect, useState } from "react";
import { validateWindDefinition } from "../../lib/commands";
import { projectToWindDefinition } from "../../types/converters";
import { useToastStore } from "../../stores/toastStore";
import type { FiberPathProject } from "../../types/project";
import type { OnCloseCallback } from "../../types/components";
import { BaseDialog } from "./BaseDialog";

interface ExportConfirmationDialogProps {
  project: FiberPathProject;
  onConfirm: OnCloseCallback;
  onCancel: OnCloseCallback;
}

export function ExportConfirmationDialog({
  project,
  onConfirm,
  onCancel,
}: ExportConfirmationDialogProps) {
  const [validationStatus, setValidationStatus] = useState<
    "checking" | "valid" | "invalid"
  >("checking");
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const addToast = useToastStore((s) => s.addToast);

  useEffect(() => {
    const validate = async () => {
      try {
        const windDef = projectToWindDefinition(project);
        const result = await validateWindDefinition(JSON.stringify(windDef));
        const isValid = result.valid === true;

        if (isValid) {
          setValidationStatus("valid");
          return;
        }

        setValidationStatus("invalid");
        const errors =
          result.errors?.map(
            (entry: { field: string; message: string }) =>
              `${entry.field}: ${entry.message}`,
          ) || ["Validation failed"];
        setValidationErrors(errors);
      } catch (error) {
        setValidationStatus("invalid");
        const errorMessage =
          error instanceof Error ? error.message : String(error);
        setValidationErrors([`Validation error: ${errorMessage}`]);
        addToast({ type: "error", message: `Validation failed: ${errorMessage}` });
      }
    };

    void validate();
  }, [project, addToast]);

  const layerCount = project.layers.length;

  return (
    <BaseDialog
      isOpen
      title="Export G-code"
      onClose={onCancel}
      contentClassName="dialog-content--medium"
      footer={
        <>
          <button className="btn btn--secondary" onClick={onCancel}>
            Cancel
          </button>
          <button
            className="btn btn--primary"
            onClick={onConfirm}
            disabled={validationStatus !== "valid"}
          >
            {validationStatus === "checking" ? "Validating..." : "Export G-code"}
          </button>
        </>
      }
    >
      {validationStatus === "checking" && (
        <div className="export-validation">
          <div className="export-validation__status export-validation__status--checking">
            <span className="spinner"></span>
            <span>Validating project...</span>
          </div>
        </div>
      )}

      {validationStatus === "invalid" && (
        <div className="export-validation">
          <div className="export-validation__status export-validation__status--error">
            <span className="status-icon">⚠</span>
            <span>Validation Failed</span>
          </div>
          <div className="export-validation__errors">
            {validationErrors.map((error, index) => (
              <div key={`${error}-${index}`} className="export-validation__error">
                {error}
              </div>
            ))}
          </div>
          <p className="export-validation__message">
            Please fix the errors above before exporting.
          </p>
        </div>
      )}

      {validationStatus === "valid" && (
        <div className="export-summary">
          <div className="export-validation__status export-validation__status--success">
            <span className="status-icon">✓</span>
            <span>Project validated successfully</span>
          </div>

          <div className="export-summary__section">
            <h3>Export Configuration</h3>
            <div className="export-summary__grid">
              <div className="export-summary__item">
                <span className="export-summary__label">Layers:</span>
                <span className="export-summary__value">
                  {layerCount} layer{layerCount !== 1 ? "s" : ""}
                </span>
              </div>
              <div className="export-summary__item">
                <span className="export-summary__label">Default Feed Rate:</span>
                <span className="export-summary__value">
                  {project.defaultFeedRate} mm/min
                </span>
              </div>
              <div className="export-summary__item">
                <span className="export-summary__label">Mandrel:</span>
                <span className="export-summary__value">
                  Ø{project.mandrel.diameter}mm × {project.mandrel.wind_length}mm
                </span>
              </div>
            </div>
          </div>

          <div className="export-summary__note">
            <strong>Note:</strong> All {layerCount} layers will be included in the
            exported G-code file. The layer scrubber in the preview is for
            visualization only.
          </div>
        </div>
      )}
    </BaseDialog>
  );
}
