# Releasing

## Version scheme

`MAJOR.MINOR.PATCH` on the package. The **schema version is separate** and moves far
more slowly, which is the point: a consumer pinning `schema_version: "0.1.0"` should
not have to care that the Python package went from 0.1.0 to 0.4.2.

| Change | Package | Schema |
|---|---|---|
| Bug fix, docs, internal refactor | patch | unchanged |
| New optional schema field, new CLI command, new output format | minor | unchanged |
| Breaking CLI change, dropped Python version | major (or minor while 0.x) | unchanged |
| Removed or renamed field, new required field, tightened constraint, changed field meaning | minor or major | **new `vN/` directory** |

A schema version is never edited after release. Add `v1/` alongside `v0/` and keep
both. Somebody's committed data claims conformance to what `v0` said on the day they
wrote it.

## Before tagging

Run the full gate. Do not pipe these anywhere — a pipe returns the pipe's exit status,
which is how unformatted code once reached CI from here.

```bash
ruff check .
ruff format --check .
pytest -q
python -m pytest -q                          # both invocations; they differ on sys.path
python tools/gen_schema_reference.py --check
python tools/gen_conformance.py --check
(cd bindings/typescript && npm install --silent && npm run conformance)
```

Then the things CI does not check:

- [ ] `CHANGELOG.md` has an entry, and `## Unreleased` has been renamed to the version
      with today's date.
- [ ] `version` in `pyproject.toml` matches.
- [ ] If a schema changed: `SCHEMA_VERSION` in `src/bead_data/schemas.py`, the `const`
      in every affected schema, and the conformance manifest all agree.
- [ ] If a federal threshold changed: `docs/sources.md` reflects it, including the
      date the sources were last read.
- [ ] A fresh clone installs and validates. CI's acceptance job covers this, but
      confirm it ran on the commit you are about to tag.

## Tagging

```bash
git tag -a v0.2.0 -m "v0.2.0

<what changed and why it matters to someone consuming the format>"
git push origin v0.2.0
```

Annotated, not lightweight — the message is where a consumer looks first, and it
should say what changed for *them*, not list commits.

Pushing a `v*` tag triggers `.github/workflows/release.yml`, which:

1. Builds the sdist and wheel.
2. Asserts the wheel contains all five normative schemas. A package that installs cleanly
   and cannot validate anything is worse than a failed build.
3. Installs the wheel into a clean environment and confirms the schemas resolve from
   the package rather than a source checkout. An editable install never exercises that
   path, so nothing else catches it.
4. Publishes SHA-256 checksums and signed build-provenance attestations tied to the
   repository, workflow, tag, and commit.
5. Creates a public GitHub Release carrying the wheel, sdist, and checksum file.
6. Publishes to PyPI only when the repository variable `PYPI_PUBLISH` is set to `true`.
   Until trusted publishing is configured, that job is visibly skipped rather than
   turning an otherwise valid GitHub release red.

## PyPI, first time only

Publishing uses [trusted publishing](https://docs.pypi.org/trusted-publishers/), so no
API token exists in this repository to leak.

1. Create the PyPI account.
2. At <https://pypi.org/manage/account/publishing/>, add a pending publisher:
   - Owner: `yichenglieng-code`
   - Repository: `bead-compliance-toolkit`
   - Workflow: `release.yml`
   - Environment: `pypi`
3. In GitHub → Settings → Environments, create an environment named `pypi`.
4. In GitHub → Settings → Secrets and variables → Actions → Variables, create
   `PYPI_PUBLISH` with value `true`.
5. Push the tag.

The distribution name is `bead-data`. Confirm it is still available before relying on
it.

## After releasing

- [ ] Confirm the release workflow went green.
- [ ] Download the wheel and verify its provenance with the command in `README.md`.
- [ ] Confirm `pip install bead-data==<version>` works in a clean environment, and
      that `bead-data validate` works on an example from a fresh download.
- [ ] Confirm `CHANGELOG.md` has a fresh `## Unreleased` section for the next cycle.

## If a release is broken

Do not delete or move a published tag; someone may already have it.

- **PyPI:** yank the release rather than deleting it. Yanking stops new installs from
  resolving to it while leaving it available to anyone who pinned it.
- **Git:** tag a fixed version. `v0.2.1` immediately after `v0.2.0` is not
  embarrassing; a silently altered `v0.2.0` is.
- **If a schema shipped wrong:** this is the serious case. If the wrong version was
  published, do not redefine it. Publish the correction as a new schema version and
  document plainly in the changelog what the broken one got wrong, so anyone who
  consumed it can tell whether they are affected.
