# CLAUDE.md — AI Development Guidelines

This file provides system instructions for AI coding assistants (like Claude, Cursor, Aider) working on this project.

## Build and Run Commands
- Build project: `pip install -e .` or setup dependencies.
- Run project: `anneal --help`

## Test Command
- Run unit tests: `pytest`

## Code Style and Guidelines
- Use clean, readable code with comments where necessary.
- Ensure all tests pass before proposing changes.
- Log new error patterns and context using `anneal log` when debugging hard-to-solve issues.
