import { open, save, ask } from "@tauri-apps/plugin-dialog";
import { saveWindFile, loadWindFile, planWind } from "../lib/commands";
import {
  projectToWindDefinition,
  windDefinitionToDocument,
} from "../types/converters";
import { WindDefinitionSchema, validateData, parseError } from "../lib/schemas";
import { addRecentFile } from "../lib/recentFiles";
import { projectSession } from "../state/project-session.svelte";
import { notifications } from "../state/notifications.svelte";
import type { WindDefinition } from "../types/wind-schema";

const WIND_FILTER = [{ name: "Wind Files", extensions: ["wind"] }];

async function confirmDiscardIfDirty(action: string): Promise<boolean> {
  if (!projectSession.isDirty) return true;
  return ask(`You have unsaved changes. ${action} anyway?`, {
    title: "Unsaved Changes",
    kind: "warning",
  });
}

async function saveToFile(filePath: string): Promise<boolean> {
  try {
    const windDef = projectToWindDefinition(projectSession.document);
    await saveWindFile(filePath, JSON.stringify(windDef, null, 2));
    projectSession.filePath = filePath;
    projectSession.markSaved();
    addRecentFile(filePath);
    return true;
  } catch (error) {
    notifications.error(`Failed to save file: ${parseError(error)}`);
    return false;
  }
}

async function loadFromPath(filePath: string): Promise<boolean> {
  try {
    const content = await loadWindFile(filePath);
    const windDef: WindDefinition = JSON.parse(content);
    validateData(WindDefinitionSchema, windDef, `.wind file at ${filePath}`);
    projectSession.loadDocument(windDefinitionToDocument(windDef), filePath);
    addRecentFile(filePath);
    return true;
  } catch (error) {
    notifications.error(`Failed to open file: ${parseError(error)}`);
    return false;
  }
}

export async function newProject(): Promise<boolean> {
  if (!(await confirmDiscardIfDirty("Create new project"))) return false;
  projectSession.newDocument();
  return true;
}

export async function openProject(): Promise<boolean> {
  if (!(await confirmDiscardIfDirty("Open new file"))) return false;
  const filePath = await open({ filters: WIND_FILTER, multiple: false });
  if (typeof filePath !== "string") return false;
  return loadFromPath(filePath);
}

export async function openRecent(filePath: string): Promise<boolean> {
  if (!(await confirmDiscardIfDirty("Open file"))) return false;
  return loadFromPath(filePath);
}

export async function saveProject(): Promise<boolean> {
  if (projectSession.filePath) return saveToFile(projectSession.filePath);
  return saveProjectAs();
}

export async function saveProjectAs(): Promise<boolean> {
  const filePath = await save({ filters: WIND_FILTER, defaultPath: "untitled.wind" });
  if (typeof filePath !== "string") return false;
  return saveToFile(filePath);
}

export async function exportGcode(): Promise<boolean> {
  const filePath = await save({
    filters: [{ name: "G-code Files", extensions: ["gcode"] }],
    defaultPath: "output.gcode",
  });
  if (typeof filePath !== "string") return false;
  try {
    const windDef = projectToWindDefinition(projectSession.document);
    await planWind(JSON.stringify(windDef), filePath);
    notifications.info(`G-code exported to: ${filePath}`);
    return true;
  } catch (error) {
    notifications.error(`Failed to export G-code: ${parseError(error)}`);
    return false;
  }
}
