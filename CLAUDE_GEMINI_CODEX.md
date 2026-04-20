# Agent Coordination: Modularization & Housekeeping

This document serves as a handoff and coordination point for agents working on Exousia.

## **Architectural Shift: Tool Modularization (April 2026)**

We have moved away from monolithic Python scripts in the `tools/` directory. All core logic has been refactored into modular packages.

### **1. Package Structure**

- **`tools/package_loader/`**: Manages YAML-based package definitions.
  - `loader.py`: Core logic (keep under 600 lines).
  - `validator.py`: Schema validation and normalization.
  - `cli.py`: CLI interface.
  - `__main__.py`: Entrypoint for `uv run python -m package_loader`.
- **`tools/generator/`**: Transpiles YAML blueprints to Containerfiles.
  - `generator.py`: Main orchestrator.
  - `processors.py`: `ModuleProcessorsMixin` containing logic for individual module types (e.g., `chezmoi`, `git-clone`).
  - `cli.py`: CLI interface and image determination.
  - `__main__.py`: Entrypoint for `uv run python -m generator`.

### **2. Development Standards**

- **No Monoliths**: Keep individual `.py` files under 600 lines.
- **No Legacy Wrappers**: Do not recreate `tools/package_loader.py` or `tools/yaml-to-containerfile.py`. Use `uv run python -m <package>`.
- **Pure TDD (Shift-Left)**:
  - Implementation MUST start with a failing test.
  - Use `uv run` for all Python invocation in local development and CI.
  - Use **Dependency Injection** for testing. **NEVER monkeypatch core classes** if you can inject directories or instances via the constructor or `main()` entrypoint.
- **SDDM is Deprecated**: The system uses `greetd-tuigreet`. All SDDM theme logic has been removed from the generator.

## **Active Plan: ZFS Implementation**

- **Task 1.2 (Gemini)**: **Done**. `KernelProfile` support is implemented in `PackageLoader` with full DI-based testing.
- **Next Unblocked Task**: **Task 1.3**. Wire `KernelProfile` into the blueprint and transpiler (`tools/generator/`).

## **Current Health**

- **Coverage**: ~86%
- **Pre-commit**: Clean.
- **Philosophy**: Red -> Green -> Refactor.
