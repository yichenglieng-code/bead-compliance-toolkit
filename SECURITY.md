# Security policy

## Reporting

Report vulnerabilities through GitHub's private vulnerability reporting on this
repository: **Security → Report a vulnerability**. That keeps the report private
until there is a fix.

Please do not open a public issue for anything exploitable.

Expect an acknowledgement within a week. This is a small project maintained by one
person, so it is not a 24-hour operation, and saying so plainly is more useful than
promising otherwise.

## What is in scope

This is a local command line tool and a set of schemas. It has no server, no
network listeners, and no authentication, so the realistic threat is malicious
*input*: an evidence file from a counterparty that does something worse than fail
validation.

In scope:

- Path traversal or arbitrary writes from a crafted filename, particularly through
  `bead-data submit`, which writes a directory of files
- Resource exhaustion from a crafted JSON, CSV, or Parquet input
- Code execution through any input path
- A validation bypass that lets a record violating the documented rules be accepted

Out of scope:

- The compliance verdict being wrong on valid data. That is a correctness bug, and
  it belongs in a normal issue, though it is a serious one
- A federal requirement being misread in `docs/sources.md`. Also a normal issue, and
  a valuable one
- Dependency advisories with no reachable path in this codebase

## Notes on handling data

Two things worth knowing if you use this on real evidence.

**Never put real subscriber data in a bug report.** All example and test data here is
synthetic, deliberately. If you are reporting an issue found on real data, reproduce
it with synthetic values.

**`subscriber_ref` is a submission requirement, not an invitation.** The USAC
templates require a subscriber identifier, so `performance_test` carries one. Use a
pseudonymous key. NTIA's own measurement methodology is designed so that testing
collects no user data, and a compliance record that leaks personal information
undermines the reason it can be published at all.

## Supply chain

Dependencies are pinned to ranges in `pyproject.toml` and to exact versions in the
TypeScript binding. Releases are published through PyPI trusted publishing, so no
long-lived API token exists in this repository to steal.
