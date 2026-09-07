---
hide:
  - navigation
  - toc
---

<!-- markdownlint-disable -->
<!--
  Material for MkDocs landing page

  IMPORTANT:
  - DO NOT apply formatting tools (Prettier, etc) to this file
  - Card grids MUST NOT contain horizontal rules (`---` or `***`)
  - Spacing is handled automatically via paragraphs and lists
  - Do not insert <hr> inside cards
-->

<div style="text-align: center; padding: 3rem 0 2rem 0;" markdown>

# FiberPath

### Modern filament winding planner, simulator, and tooling

[Get Started](getting-started.md){ .md-button .md-button--primary }
[View on GitHub :fontawesome-brands-github:](https://github.com/fiberpath/fiberpath){ .md-button target=_blank }

</div>

---

## Quick Start

<div class="grid cards" markdown>

-   :material-download:{ .lg .middle } **Download & Install**

    ---

    **Latest Release:** [v0.11.0](https://github.com/fiberpath/fiberpath/releases/latest){ target=_blank }

    - **Desktop GUI** – Windows, macOS, Linux installers (no Python required)
    - **Python Package** – `pip install fiberpath`
    - **Source** – Clone and build from GitHub

    [:octicons-arrow-right-24: Installation Guide](getting-started.md)

-   :material-new-box:{ .lg .middle } **What's New in v0.11.0**

    ---

    This release takes FiberPath off developable surfaces for the first time:

    - **Von Kármán nosecone** — a curved surface of revolution can now be wound via an optional `mandrelParameters.profile`. Helical layers follow a *numeric* geodesic (the Clairaut relation integrated over the meridian) rather than the cone's closed form.
    - **Non-geodesic, friction-assisted winding** — an optional `frictionLambda` (λ) lets a pass deviate from the geodesic and climb past the turnaround toward the tip, shrinking the bare polar cap. It is bounded by a new machine `slipLimit` (μ), and the planner rejects a wind that would slip.
    - **Calibrated machine limits** — `fiberpath plan --profile <path>` supplies a measured μ for your winder.
    - **Desktop fidelity** — Von Kármán and friction winds now open, edit and save losslessly in the app.

    [:octicons-arrow-right-24: `.wind` Format Guide](guides/wind-format.md)

-   :material-book-open-page-variant:{ .lg .middle } **User Guides**

    ---

    Learn how to work with FiberPath's core features:

    - [Wind Format](guides/wind-format.md) – File schema & validation
    - [Axis Mapping](guides/axis-mapping.md) – Coordinate systems
    - [Marlin Streaming](guides/marlin-streaming.md) – Hardware control
    - [Visualization](guides/visualization.md) – Preview & plotting

-   :material-code-json:{ .lg .middle } **API Reference**

    ---

    Technical documentation and specifications:

    - [Concepts](reference/concepts.md) – Terminology glossary
    - [API Reference](reference/api.md) – REST endpoints
    - [Planner Math](reference/planner-math.md) – Algorithms & formulas

-   :material-layers-triple:{ .lg .middle } **Architecture**

    ---

    Understand the system design and internals:

    - [System Overview](architecture/overview.md) – Stack & data flow
    - [Axis System](architecture/axis-system.md) – Logical vs physical

    [:octicons-arrow-right-24: Architecture Docs](architecture/overview.md)

-   :material-hammer-wrench:{ .lg .middle } **Development**

    ---

    Contribute to FiberPath development:

    - [Contributing](development/contributing.md) – Guidelines & setup
    - [Tooling](development/tooling.md) – Dev environment
    - [CI/CD](development/ci-cd.md) – Build workflows

    [:octicons-arrow-right-24: Developer Docs](development/contributing.md)

</div>

---

## Features

<div class="grid cards" markdown>

-   :material-file-code: **Wind File Format**

    ---

    Define winding patterns with a simple, validated YAML schema

-   :material-axis-arrow: **Multi-Axis Control**

    ---

    Native XAB rotational-axis output with clear logical axis mapping

-   :material-connection: **Marlin Streaming**

    ---

    Direct hardware control with real-time progress and state management

-   :material-chart-line: **Visualization**

    ---

    Preview and plot toolpaths before manufacturing

-   :material-puzzle: **Modular Architecture**

    ---

    CLI, API, and GUI components work standalone or together

-   :material-cog-refresh: **Layer Strategies**

    ---

    Configurable winding algorithms with mathematical precision

</div>
