# Feature Backlog (Low Priority / Speculative)

**Focus:** Speculative features with unclear value or disproportionate complexity
**Status:** Backlog - only implement with strong user demand and clear value proposition
**Priority:** Low to None
**Role:** Decision/reference log for deferred or rejected features from active roadmaps (v6, v7, and beyond)

Use this file to track intentionally deferred scope. Do not treat it as an active execution roadmap.

---

## Category 1: Complex Visualization Features

### 3D Streaming Visualization (Backlog Concept, Not Shipped)

**Description:** Real-time 3D toolpath visualization during Marlin streaming using Three.js (future concept only).

**Why Rejected:**

- Current PNG preview + progress bar/log provides sufficient feedback
- "Eye candy" feature without functional value (32+ tasks for marginal benefit)
- Three.js adds ~600KB bundle size
- Poor complexity-to-value ratio

**If Reconsidered:** Would require Three.js integration, G-code parser, real-time rendering pipeline, performance optimization for large files. Only implement with explicit user demand and evidence current visualization is insufficient.

---

### WebGL-based Toolpath Rendering

**Description:** Hardware-accelerated toolpath rendering for Main tab visualization

**Why Low Priority:**

- Current PNG-based preview works fine
- Would require complete rewrite of visualization system
- Performance benefits unclear for typical use cases
- Users aren't complaining about current visualization speed

**Decision:** Not worth the effort unless performance becomes a real problem.

---

## Category 2: Internationalization

### Multi-language Support (i18n)

**Why Rejected:**

- No evidence of international user base
- G-code/winding terminology is inherently English
- High maintenance burden (500+ UI strings, native speaker translation quality)
- Would require i18next/react-intl setup, extraction workflow, ongoing maintenance

**Reconsider If:** Clear international user base, users requesting specific languages, volunteer translators available, commitment to long-term maintenance.

---

## Category 3: Advanced UX Features

### Panel Resize Handles

**Why Rejected:**

- Attempted in previous development cycle, didn't work well
- Layout is already well-balanced for the workflow
- Complex implementation (drag handlers, state persistence, layout constraints)
- Low value for high complexity

### Keyboard Shortcut Customization

**Why Deferred:**

- Current shortcuts are well-designed and sufficient (Ctrl+S, Ctrl+O, Alt+1/2, etc.)
- Niche feature requested by power users only
- Would require: shortcut registry, conflict detection, UI for rebinding, storage persistence
- Most users never customize shortcuts

**Reconsider If:** Users report shortcut conflicts with other software, accessibility needs emerge.

### Workspace Layout Presets

**Why Deferred:**

- Premature optimization - current single layout works well
- Would require: layout serialization, preset storage, restore logic, UI for preset management
- Unclear use case - who needs multiple layouts?

**Reconsider If:** Clear use cases emerge (different layouts for different workflows).

### Undo/Redo System

**Why Deferred:**

- Complex implementation (command pattern, state snapshots, undo stack management)
- Current workflow is forward-only (add layers, export), undo rarely needed
- File save/load provides "undo" via reverting to saved state
- High maintenance burden for unclear benefit

**Reconsider If:** Users frequently request ability to undo layer changes or configuration updates.

### Layer Presets System

**Why Deferred:**

- Advanced feature with unclear use case
- Would require: preset schema, storage, UI for save/load/manage presets
- Current workflow (duplicate existing layers) is sufficient
- No evidence users need to save layer configurations

**Reconsider If:** Users request ability to reuse layer configurations across projects.

---

## Category 4: Advanced Data Features

### Coverage Analysis and Visualization

**Why Out of Scope:**

- Extremely complex (requires composite physics expertise, 3D engine)
- Academic research territory, not practical tool
- Users trust math without visualization and can export to specialized analysis tools

### Real-time G-code Preview

**Why Rejected:**

- Current plan→preview→export workflow is sufficient
- PNG preview already very fast
- Would require streaming generation architecture for unclear benefit

---

## Category 5: Integration Features

### REST API Enhancements

**Why Low Priority:**

- CLI and GUI sufficient for current users
- API exists but unused (no known integrations)
- Would require versioning, documentation, support overhead

**Reconsider If:** Users request specific API features, third-party tools want integration, clear use cases emerge.

### CAD Software Plugins

**Why Rejected:**

- Extremely high effort per platform (SolidWorks, Fusion 360, etc.)
- Different plugin APIs, multiple CAD version maintenance
- Users can export geometry manually
- Not feasible without dedicated plugin team

---

## Category 6: Workflow Automation

### AI/ML Pattern Optimization

**Why Out of Scope:**

- Research-level feature requiring deep composites expertise, ML infrastructure, training data collection, pattern validation
- Users can use existing research tools separately

### Automatic Parameter Tuning

**Why Rejected:**

- Requires sophisticated simulation with long computation times
- Users prefer predictable manual control over "magic" automation
- Risk of unexpected results

---

## Category 7: Cloud & Infrastructure Features

### Cloud Sync & Sharing

**Why Rejected:**

- Requires backend infrastructure, complex conflict resolution, offline support, security/privacy measures
- Users can manage files with OneDrive/Dropbox/Git
- High operational complexity and maintenance burden
- No evidence users want this feature

**Reconsider If:** Multiple users request it, evidence local file management insufficient, willingness to host/maintain infrastructure, clear collaboration use case.

### Batch Processing GUI

**Why Rejected:**

- Niche production use case (most users work on one part at a time)
- CLI already supports all operations via scripting
- GUI batch UI adds complexity without clear value

**Alternative:** Document CLI batch scripting:

```bash
for file in *.wind; do
  fiberpath plan "$file" --output "${file%.wind}.gcode"
done
```

**Reconsider If:** Multiple users request batch GUI, CLI scripting insufficient, clear high-volume production use case.

---

## Category 8: Technical Debt & Refactoring

### Rust Async Timeout for Subprocess Operations

**Issue:** `MarlinSubprocess.read_response()` uses synchronous `BufReader::read_line()` which can block indefinitely if Python subprocess hangs.

**Why Deferred:**

- Python subprocess already has timeout protection (non-critical)
- Requires tokio async/await refactor (3-4 hours: convert all Tauri commands to async, add tokio dependencies, update error types)
- Current implementation works in practice

**Solution:** Convert to tokio async with `timeout(Duration::from_secs(5), stdout_reader.read_line())`. Only implement if blocking becomes a real issue.

---

## Summary

**Total Backlog Items:** ~84+ tasks across 7 categories

**Implementation Policy:**

- ❌ Do NOT implement without strong user demand and clear value proposition
- ❌ Do NOT implement if complexity >> value
- ✅ Re-evaluate only if multiple users request feature with clear use case

**Evaluation Criteria:**

1. Multiple users requesting feature
2. Current functionality demonstrably insufficient
3. Clear, measurable value
4. Reasonable complexity
5. Acceptable maintenance burden
6. Aligns with FiberPath's core mission (practical G-code generation for composite fiber winding)

**Last Updated:** 2026-01-13
