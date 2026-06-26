#!/usr/bin/env node

import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..");
const srcRoot = path.join(repoRoot, "src");

const DECLARATION_FILE_EXT = new Set([".css"]);
const USAGE_FILE_EXT = new Set([".css", ".ts", ".tsx", ".svelte"]);

async function collectFiles(rootDir, extSet) {
  const results = [];

  async function walk(currentDir) {
    const entries = await fs.readdir(currentDir, { withFileTypes: true });

    for (const entry of entries) {
      const fullPath = path.join(currentDir, entry.name);

      if (entry.isDirectory()) {
        await walk(fullPath);
        continue;
      }

      if (entry.isFile() && extSet.has(path.extname(entry.name))) {
        results.push(fullPath);
      }
    }
  }

  await walk(rootDir);
  return results;
}

function getLineNumber(content, index) {
  let line = 1;
  for (let i = 0; i < index; i += 1) {
    if (content.charCodeAt(i) === 10) {
      line += 1;
    }
  }
  return line;
}

function toRelative(filePath) {
  return path.relative(repoRoot, filePath).replaceAll("\\", "/");
}

function collectDeclaredVars(cssFiles) {
  const declared = new Set();
  const declarationRegex = /(^|[;{\s])(--[A-Za-z0-9_-]+)\s*:/g;

  return Promise.all(
    cssFiles.map(async (filePath) => {
      const content = await fs.readFile(filePath, "utf8");
      for (const match of content.matchAll(declarationRegex)) {
        declared.add(match[2]);
      }
    }),
  ).then(() => declared);
}

async function collectUsageSites(files) {
  const usageRegex = /var\(\s*(--[A-Za-z0-9_-]+)/g;
  const usageSites = [];

  await Promise.all(
    files.map(async (filePath) => {
      const content = await fs.readFile(filePath, "utf8");
      for (const match of content.matchAll(usageRegex)) {
        usageSites.push({
          variable: match[1],
          filePath,
          line: getLineNumber(content, match.index ?? 0),
        });
      }
    }),
  );

  return usageSites;
}

async function main() {
  const declarationFiles = await collectFiles(srcRoot, DECLARATION_FILE_EXT);
  const usageFiles = await collectFiles(srcRoot, USAGE_FILE_EXT);

  const declaredVars = await collectDeclaredVars(declarationFiles);
  const usageSites = await collectUsageSites(usageFiles);

  const missing = usageSites
    .filter((site) => !declaredVars.has(site.variable))
    .sort((a, b) => {
      if (a.variable !== b.variable) {
        return a.variable.localeCompare(b.variable);
      }
      if (a.filePath !== b.filePath) {
        return a.filePath.localeCompare(b.filePath);
      }
      return a.line - b.line;
    });

  if (missing.length === 0) {
    console.log("CSS variable guard passed: all var(--token) usages resolve.");
    return;
  }

  console.error("CSS variable guard failed: unresolved custom properties found.\n");

  for (const site of missing) {
    console.error(`${site.variable} -> ${toRelative(site.filePath)}:${site.line}`);
  }

  process.exitCode = 1;
}

main().catch((error) => {
  console.error("CSS variable guard crashed:", error);
  process.exit(1);
});
