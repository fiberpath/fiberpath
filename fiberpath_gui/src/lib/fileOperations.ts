import { open, save, ask } from "@tauri-apps/plugin-dialog";
import {
  saveWindFile,
  loadWindFile,
  validateWindDefinition as validateWindCmd,
  planWind,
} from "./commands";
import {
  projectToWindDefinition,
  windDefinitionToProject,
} from "../types/converters";
import { addRecentFile } from "./recentFiles";
import {
  FileError,
  ValidationError,
  parseError,
  WindDefinitionSchema,
  validateData,
} from "./schemas";
import { validateWindDefinition as validateWindSchema } from "./validation";
import {
  mapBackendValidationErrors,
  type UiValidationErrors,
} from "./validationErrors";
import type { FiberPathProject } from "../types/project";
import type { WindDefinition } from "../types/wind-schema";

export interface FileOperationCallbacks {
  getProject: () => FiberPathProject; // Changed to function to get current state
  newProject: () => void;
  loadProject: (project: FiberPathProject) => void;
  setFilePath: (path: string | null) => void;
  clearDirty: () => void;
  getActiveLayerId: () => string | null; // Changed to function
  duplicateLayer: (layerId: string) => void;
  removeLayer: (layerId: string) => void;
  updateRecentFiles?: () => void;
  showError?: (message: string) => void;
  showInfo?: (message: string) => void;
  setValidationErrors?: (errors: UiValidationErrors) => void;
  clearValidationErrors?: () => void;
}

export function createFileOperations(callbacks: FileOperationCallbacks) {
  const {
    getProject,
    newProject,
    loadProject,
    setFilePath,
    clearDirty,
    getActiveLayerId,
    duplicateLayer,
    removeLayer,
    updateRecentFiles,
    showError,
    showInfo,
    setValidationErrors,
    clearValidationErrors,
  } = callbacks;

  const saveToFile = async (filePath: string) => {
    try {
      const project = getProject();
      const windDef = projectToWindDefinition(project);
      const content = JSON.stringify(windDef, null, 2);

      await saveWindFile(filePath, content);
      setFilePath(filePath);
      clearDirty();
      addRecentFile(filePath);
      updateRecentFiles?.();
    } catch (error) {
      const message = parseError(error);
      showError?.(`Failed to save file: ${message}`);
      throw new FileError(`Failed to save file: ${message}`, filePath, "save", {
        originalError: error,
      });
    }
  };

  const handleNewProject = async () => {
    const project = getProject();
    if (project.isDirty) {
      const confirmed = await ask(
        "You have unsaved changes. Create new project anyway?",
        {
          title: "Unsaved Changes",
          kind: "warning",
        },
      );
      if (!confirmed) return false;
    }
    newProject();
    clearValidationErrors?.();
    return true;
  };

  const handleOpen = async () => {
    const project = getProject();
    if (project.isDirty) {
      const confirmed = await ask(
        "You have unsaved changes. Open new file anyway?",
        {
          title: "Unsaved Changes",
          kind: "warning",
        },
      );
      if (!confirmed) return false;
    }

    const filePath = await open({
      filters: [
        {
          name: "Wind Files",
          extensions: ["wind"],
        },
      ],
      multiple: false,
    });

    if (!filePath) return false;

    try {
      const content = await loadWindFile(filePath);
      const windDef: WindDefinition = JSON.parse(content);

      // Runtime validation of loaded .wind file structure
      validateData(WindDefinitionSchema, windDef, `.wind file at ${filePath}`);

      const fullProject = windDefinitionToProject(windDef, filePath);

      loadProject(fullProject);
      setFilePath(filePath);
      clearValidationErrors?.();
      addRecentFile(filePath);
      updateRecentFiles?.();
      return true;
    } catch (error) {
      const message = parseError(error);
      showError?.(`Failed to open file: ${message}`);
      throw new FileError(`Failed to open file: ${message}`, filePath, "load", {
        originalError: error,
      });
    }
  };

  const handleSave = async () => {
    const project = getProject();
    if (project.filePath) {
      await saveToFile(project.filePath);
      return true;
    } else {
      return await handleSaveAs();
    }
  };

  const handleSaveAs = async () => {
    const filePath = await save({
      filters: [
        {
          name: "Wind Files",
          extensions: ["wind"],
        },
      ],
      defaultPath: "untitled.wind",
    });

    if (!filePath) return false;

    try {
      await saveToFile(filePath);
      return true;
    } catch (error) {
      return false;
    }
  };

  // This is called after user confirms in the export dialog
  const handleExportGcode = async () => {
    try {
      const project = getProject();
      const windDef = projectToWindDefinition(project);

      const gcodeFilePath = await save({
        filters: [
          {
            name: "G-code Files",
            extensions: ["gcode"],
          },
        ],
        defaultPath: "output.gcode",
      });

      if (!gcodeFilePath) return false;

      // The API plans from the definition body and returns the G-code; planWind
      // writes it to the chosen path (no temporary .wind file needed).
      await planWind(JSON.stringify(windDef), gcodeFilePath);

      showInfo?.(`G-code exported to: ${gcodeFilePath}`);
      return true;
    } catch (error) {
      const message = parseError(error);
      showError?.(`Failed to export G-code: ${message}`);
      throw new FileError(
        `Failed to export G-code: ${message}`,
        undefined,
        "export",
        { originalError: error },
      );
    }
  };

  const handleOpenRecent = async (filePath: string) => {
    const project = getProject();
    if (project.isDirty) {
      const confirmed = await ask(
        "You have unsaved changes. Open file anyway?",
        {
          title: "Unsaved Changes",
          kind: "warning",
        },
      );
      if (!confirmed) return false;
    }

    try {
      const content = await loadWindFile(filePath);
      const windDef: WindDefinition = JSON.parse(content);

      // Runtime validation of loaded .wind file structure
      validateData(WindDefinitionSchema, windDef, `.wind file at ${filePath}`);

      const fullProject = windDefinitionToProject(windDef, filePath);

      loadProject(fullProject);
      setFilePath(filePath);
      clearValidationErrors?.();
      addRecentFile(filePath);
      updateRecentFiles?.();
      return true;
    } catch (error) {
      const message = parseError(error);
      showError?.(`Failed to open file: ${message}`);
      throw new FileError(`Failed to open file: ${message}`, filePath, "load", {
        originalError: error,
      });
    }
  };

  const handleDuplicateLayer = () => {
    const activeLayerId = getActiveLayerId();
    if (activeLayerId) {
      duplicateLayer(activeLayerId);
      return true;
    }
    return false;
  };

  const handleDeleteLayer = () => {
    const activeLayerId = getActiveLayerId();
    if (activeLayerId) {
      removeLayer(activeLayerId);
      return true;
    }
    return false;
  };

  const handleValidate = async () => {
    const formatValidationErrors = (
      errors: Array<{ field: string; message: string }>,
    ) =>
      errors
        .map((error) => `• ${error.field}: ${error.message}`)
        .join("\n");

    try {
      const project = getProject();
      const windDef = projectToWindDefinition(project);
      const schemaValidation = validateWindSchema(windDef);

      if (!schemaValidation.valid) {
        const mapped = mapBackendValidationErrors(schemaValidation.errors);
        setValidationErrors?.(mapped.fieldErrors);
        const errorList = formatValidationErrors(schemaValidation.errors);
        showError?.(`Validation failed:\n${errorList}`);
        throw new ValidationError(
          "Wind definition validation failed",
          schemaValidation.errors,
        );
      }

      const result = await validateWindCmd(JSON.stringify(windDef));

      const isValid = result.valid === true;

      if (isValid) {
        clearValidationErrors?.();
        showInfo?.("✓ Definition is valid");
        return true;
      } else {
        const errors =
          result.errors && result.errors.length > 0
            ? result.errors
            : [{ field: "validation", message: "Unknown validation error" }];
        const mapped = mapBackendValidationErrors(errors);
        setValidationErrors?.(mapped.fieldErrors);
        const errorList = formatValidationErrors(errors);
        const validationError = new ValidationError(
          `Wind definition validation failed`,
          errors,
        );
        showError?.(`Validation failed:\n${errorList}`);
        throw validationError;
      }
    } catch (error) {
      if (error instanceof ValidationError) {
        throw error;
      }
      const message = parseError(error);
      showError?.(`Validation error: ${message}`);
      throw error;
    }
  };

  return {
    handleNewProject,
    handleOpen,
    handleSave,
    handleSaveAs,
    handleExportGcode,
    handleOpenRecent,
    handleDuplicateLayer,
    handleDeleteLayer,
    handleValidate,
  };
}
