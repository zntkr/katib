# Domain Documentation

This project uses a single-context documentation layout.

## Locations

- **Context**: `CONTEXT.md` at the repository root. This file defines the project's domain language, core concepts, and high-level architecture.
- **Architectural Decision Records (ADRs)**: `docs/adr/`. This directory contains numbered ADRs documenting significant technical decisions.

## Consumer Rules

- **Reading**: Agents should read `CONTEXT.md` before performing architectural changes or deep diagnosis.
- **Writing**: New architectural decisions should be recorded as ADRs in `docs/adr/`.
