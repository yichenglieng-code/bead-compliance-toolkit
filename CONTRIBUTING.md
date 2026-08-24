# Contributing

Thanks for looking. This project is early, and the most valuable contribution right
now is not code.

## Most useful: tell us where the schemas are wrong

If you file BEAD reports, build equipment that feeds them, or review submissions at
a state broadband office, you know things this project does not. Open an issue if:

- a field is missing that your reporting actually needs
- a field here does not match how your state office asks for it
- an encoded threshold or enum disagrees with current NTIA, FCC, or USAC guidance
- your existing export format cannot be mapped onto these schemas without loss

Concrete disagreement with a citation beats a general suggestion. Every requirement
encoded here is traced to a primary source in [docs/sources.md](docs/sources.md), so
if something is wrong, there is a specific claim to argue with.

## Ground rules for data in issues and pull requests

**Never attach real subscriber, subscriber-location, or customer data.** Not in an
issue, not in a test fixture, not in an example. Use synthetic values with obviously
fake identifiers, in the style of the `BSL-1002003004` ids and "Example Rural ISP"
names already in `examples/`. Pull requests carrying real location or subscriber
data will be closed rather than merged and edited.

Do not attach material you are not free to publish, including anything covered by an
employer confidentiality obligation or a customer NDA.

## Schema changes

The JSON Schemas in `schemas/` are normative. The pydantic models in
`src/bead_data/models.py` are a binding to them, and a test asserts the two stay in
step, so a schema change means changing both.

Compatibility rules while v0 is current:

- Adding an optional field is a minor change.
- Adding a required field, removing a field, renaming a field, tightening a
  constraint, or removing an enum value is a breaking change. It needs a new schema
  version directory (`v1/`), not an edit to `v0/`.
- New enum values are additive but still need a version bump if consumers would
  reject an unrecognized value.

Every field needs a `description` explaining what it is **and why BEAD reporting
needs it**, with the requirement cited in `docs/sources.md`. A test fails on
undocumented fields. This is deliberate: a field nobody can explain is a field
nobody else will adopt.

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest                  # tests
ruff check .            # lint
ruff format .           # format
```

CI runs the same three on Python 3.11 and 3.12, plus a fresh-clone install that
validates every example. All of it must be green.

Adding a validation rule means adding a test that fails without it. Cross-field
rules in particular should assert the field path and the message, since those are
what a submitter actually reads when fixing data.

## Commit messages

Conventional commits, e.g. `feat(schemas):`, `fix(validate):`, `docs:`, `test:`,
`ci:`, `chore:`. Keep the subject under 72 characters and say what changed and why.

## Licensing

Contributions are accepted under [Apache-2.0](LICENSE), the project's license. By
opening a pull request you confirm you have the right to contribute the work under
that license.

## Conduct

Be straightforward and civil. Assume the person on the other end is trying to ship
broadband to somewhere that does not have it.
