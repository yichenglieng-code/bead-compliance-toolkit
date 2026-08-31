# What and why

<!-- What changes, and what problem it solves. If it fixes an issue, link it. -->

## Type

<!-- Delete what does not apply. -->

- Bug fix
- New feature
- Schema change
- Documentation
- Correction to an encoded federal requirement

## If this touches a schema

- [ ] Every new field has a `description` saying what it is **and why BEAD reporting
      needs it**
- [ ] The pydantic model in `src/bead_data/models.py` matches
- [ ] Any cross-field rule is implemented in **both** bindings (Python and TypeScript)
- [ ] Conformance vectors added or updated in `tools/gen_conformance.py`
- [ ] `python tools/gen_schema_reference.py` and `python tools/gen_conformance.py` run,
      output committed
- [ ] Compatibility considered: is this additive, or does it need a new `vN/` directory?
      See [CONTRIBUTING.md](../CONTRIBUTING.md)

## If this encodes or changes a federal requirement

- [ ] Cited in [docs/sources.md](../docs/sources.md) with the source version and date
- [ ] If a threshold changed, it changed in `src/bead_data/thresholds.py` — the only
      place a federal number lives
- [ ] The changelog entry says whether compliance outcomes change for existing data

## Checks

- [ ] `ruff check .` and `ruff format --check .` pass — run them directly, not piped
      through anything, since a pipe returns the pipe's exit code
- [ ] `pytest` passes (the console script, not `python -m pytest`; they differ on
      `sys.path`)
- [ ] New behaviour has a test that fails without the change
- [ ] `CHANGELOG.md` updated under `## Unreleased`

## Data hygiene

- [ ] No real subscriber, location, or customer data anywhere in this change,
      including fixtures and examples

---

<!--
New here? ARCHITECTURE.md explains how the pieces fit and the two invariants that
should not be broken. docs/extending.md has step-by-step recipes for the common
kinds of change. Neither is long.

Partial work is welcome. Open it as a draft and say what you are unsure about.
-->
