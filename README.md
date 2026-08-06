<p align="center">
  <img src="docs/images/banner.jpg" alt="Eidolon Bootstrap Framework">
</p>

# Eidolon Bootstrap Framework

> Engineering framework for reproducible deployment of the Eidolon local AI ecosystem.
>
> Built for engineers who believe local AI should be reproducible.
>
> Current Status: **Alpha**

## Contents

- [What is EBF?](#what-is-ebf)
- [Why EBF?](#why-ebf)
- [Engineering Principles](#engineering-principles)
- [Framework Architecture](#framework-architecture)
- [Bootstrap Standards](#bootstrap-standards)
- [Naming Conventions](#naming-conventions)
- [Roadmap](#roadmap)
- [Component Structure](#component-structure)
- [Deployment Workflow](#deployment-workflow)
- [Relationship with Project Eidolon](#relationship-with-project-eidolon)

## What is EBF?

The **Eidolon Bootstrap Framework (EBF)** is a modular deployment framework designed to transform a fresh Debian installation into a fully reproducible Eidolon platform.

Rather than being a collection of installation scripts, EBF defines a set of engineering standards, deployment conventions, validation procedures and reusable components that ensure every Eidolon node is deployed consistently and predictably.

Each component performs a single responsibility while following a common architecture, allowing the entire platform to evolve without sacrificing maintainability or reproducibility.

EBF is the foundation of the entire Eidolon ecosystem and provides the same deployment methodology for every future component of the platform.

## Why EBF?

Deploying a local AI platform involves much more than installing a language model.

A complete local AI ecosystem requires a consistent operating system, GPU drivers, container runtimes, inference engines, memory services, networking, storage, monitoring and automation. Installing these components manually is often time-consuming, difficult to reproduce and prone to configuration drift.

EBF was created to solve this problem.

By decomposing the deployment process into independent components, every installation follows the same engineering methodology, making the platform predictable, maintainable and reproducible.

Each component is responsible for a single task:

- Preparing the operating system
- Installing GPU drivers
- Configuring container services
- Deploying AI runtimes
- Initializing memory services
- Validating the environment
- Preparing future extensions

This modular approach allows every component to evolve independently while remaining fully compatible with the rest of the framework.

## Engineering Principles

EBF follows a small set of engineering principles applied consistently across every component.

- **Single Responsibility** — Each component performs one well-defined task.
- **Validation First** — Requirements are verified before any modification is performed.
- **Reproducibility** — Every deployment should produce the same result.
- **Modularity** — Components remain independent and reusable.
- **Maintainability** — Clear architecture and coding standards take precedence over short-term convenience.
- **Local First** — No cloud dependency is required to deploy or operate the platform.

## Framework Architecture

The Eidolon Bootstrap Framework is organized as a sequence of independent deployment components.

Each component is responsible for one stage of the installation process and can rely on the work completed by the previous components.

```text
01-system
      │
      ▼
02-nvidia
      │
      ▼
03-docker
      │
      ▼
04-ollama
      │
      ▼
05-python
      │
      ▼
06-memory
      │
      ▼
...
```

Every component follows the same engineering standards, coding conventions and validation methodology, ensuring a consistent deployment experience across the entire framework.

## Bootstrap Standards

The Bootstrap Standards define the mandatory structure shared by every deployment component within the framework.

Every EBF component follows the same internal architecture.

```text
Configuration
      │
      ▼
Display
      │
      ▼
Checks
      │
      ▼
Validation
      │
      ▼
Execution
      │
      ▼
Utilities
      │
      ▼
Sections
      │
      ▼
Summary
```

This standardized architecture provides several advantages:

- Consistent code organization
- Easier maintenance
- Predictable execution flow
- Component independence
- Improved readability
- Simplified debugging

## Naming Conventions

EBF uses explicit function naming to clearly separate responsibilities.

| Prefix | Purpose |
|---------|----------|
| `check_*` | Low-level system checks |
| `validate_*` | Functional validation |
| `configure_*` | System configuration |
| `install_*` | Software installation |
| `create_*` | Resource creation |
| `update_*` | System updates |
| `cleanup_*` | Cleanup operations |

This convention makes every component immediately understandable, regardless of its purpose.

## Roadmap

The framework is developed as a sequence of modular deployment components.

| Component | Description | Status |
|-----------|-------------|--------|
| 🚧 01-system | Base operating system preparation | 🚧 In development |
| 02-nvidia | NVIDIA driver and CUDA installation | Planned |
| 03-docker | Docker engine configuration | Planned |
| 04-ollama | Ollama deployment | Planned |
| 05-python | Python runtime and virtual environments | Planned |
| 06-memory | Memory services | Planned |
| ... | Additional components | Planned |


## Repository Structure

```text
components/
templates/
standards/
docs/
```

The repository is organized to clearly separate deployment components, framework standards, reusable templates and technical documentation.

## Component Structure

Every deployment component follows the same internal organization.

```text
01-system.sh

Configuration
      │
      ▼
Display Functions
      │
      ▼
Check Functions
      │
      ▼
Validation Functions
      │
      ▼
Execution Functions
      │
      ▼
Utility Functions
      │
      ▼
Deployment Sections
      │
      ▼
Main()
```

This structure is shared across every EBF component, ensuring a consistent development experience throughout the framework.


## Deployment Workflow

Each component follows the same execution pipeline.

```text
Display Header
      │
      ▼
Environment Checks
      │
      ▼
Functional Validation
      │
      ▼
Deployment
      │
      ▼
Verification
      │
      ▼
Summary
      │
      ▼
Next Component
```

Every execution produces the same deployment flow, making troubleshooting and maintenance significantly easier.

## Eidolon Ecosystem

```text
                     Project Eidolon
                      (Ecosystem)
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
Bootstrap Framework     Eidolon Core     Eidolon Memory
        │                                      │
        └──────────────┬───────────────────────┘
                       ▼
                    Robotics

```

## Relationship with Project Eidolon

The Eidolon Bootstrap Framework (EBF) is one of the foundational projects within the Project Eidolon ecosystem.

While Project Eidolon documents the vision, research and long-term evolution of a fully local AI platform, EBF provides the engineering framework used to deploy, validate and reproduce every component of that ecosystem.

Together, they combine engineering methodology with practical implementation, making the entire platform reproducible, maintainable and designed to evolve over time.

---

## License

Released under the MIT License.
