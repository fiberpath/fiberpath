import { beforeEach, describe, expect, it } from "vitest";
import { getRecentFiles, addRecentFile } from "./recentFiles";

const RECENT_FILES_KEY = "fiberpath_recent_files";

describe("recentFiles", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  describe("getRecentFiles()", () => {
    it("returns empty array when nothing is stored", () => {
      expect(getRecentFiles()).toEqual([]);
    });

    it("returns stored files sorted by most recent first", () => {
      const files = [
        { path: "/older.wind", lastOpened: 1000 },
        { path: "/newer.wind", lastOpened: 2000 },
      ];
      localStorage.setItem(RECENT_FILES_KEY, JSON.stringify(files));

      const result = getRecentFiles();
      expect(result[0].path).toBe("/newer.wind");
      expect(result[1].path).toBe("/older.wind");
    });

    it("returns empty array when localStorage contains invalid JSON", () => {
      localStorage.setItem(RECENT_FILES_KEY, "not-json");
      expect(getRecentFiles()).toEqual([]);
    });
  });

  describe("addRecentFile()", () => {
    it("adds a new file to the list", () => {
      addRecentFile("/path/to/file.wind");
      const files = getRecentFiles();
      expect(files).toHaveLength(1);
      expect(files[0].path).toBe("/path/to/file.wind");
    });

    it("moves an existing file to the front instead of duplicating", () => {
      addRecentFile("/first.wind");
      addRecentFile("/second.wind");
      addRecentFile("/first.wind"); // re-add first

      const files = getRecentFiles();
      expect(files).toHaveLength(2);
      expect(files[0].path).toBe("/first.wind");
    });

    it("trims list to 10 entries maximum", () => {
      for (let i = 0; i < 12; i++) {
        addRecentFile(`/file${i}.wind`);
      }
      expect(getRecentFiles()).toHaveLength(10);
    });

    it("stores a timestamp on the added entry", () => {
      const before = Date.now();
      addRecentFile("/timestamped.wind");
      const after = Date.now();

      const file = getRecentFiles()[0];
      expect(file.lastOpened).toBeGreaterThanOrEqual(before);
      expect(file.lastOpened).toBeLessThanOrEqual(after);
    });
  });

});
