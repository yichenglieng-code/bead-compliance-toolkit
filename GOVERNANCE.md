# Governance

Small and honest rather than aspirational. This describes how the project is actually
run today, and how someone else can take it over.

## Current state

One maintainer: **Yicheng (Ethan) Li** ([@yichenglieng-code](https://github.com/yichenglieng-code)).

That is a single point of failure, and the sections below exist because pretending
otherwise would be worse than admitting it. If you are evaluating whether to depend on
this project, read [If the maintainer goes away](#if-the-maintainer-goes-away) before
you decide.

## How decisions get made

Right now: the maintainer decides, in public, on issues and pull requests.

Two things constrain that discretion, and they are the reason this is not simply
"one person's preferences":

1. **Federal requirements are not open to opinion.** Anything encoding an NTIA, FCC,
   or USAC rule is settled by citation, not by argument. If a citation in
   [docs/sources.md](docs/sources.md) is wrong, correcting it is not a matter of
   taste. If a rule is genuinely ambiguous, the ambiguity gets documented rather than
   resolved by fiat — see the known-gaps section there.

2. **The schemas are a contract.** Once a version is published, its meaning is fixed.
   Breaking changes require a new version directory, not a redefinition. See the
   compatibility rules in [CONTRIBUTING.md](CONTRIBUTING.md).

Within those constraints, the maintainer's judgement applies to scope, design, and
what to say no to.

## What gets accepted

**Readily:**

- A correction to an encoded requirement, with a citation
- A schema gap a practitioner has actually hit
- A bug fix with a test that fails without it
- A new language binding that passes the conformance suite
- Documentation that makes something less confusing

**With discussion first:**

- New fields or fact families. The bar is a real reporting need, not a plausible one.
- Changes affecting compliance outcomes for existing data
- New dependencies

**Unlikely:**

- Features serving one organization's internal workflow. This is an interchange
  format; the test is whether multiple independent parties need it.
- Anything requiring a hosted service, a credential, or telemetry
- Vendor-specific vocabulary in the schemas
- Convenience that weakens either invariant in [ARCHITECTURE.md](ARCHITECTURE.md)

## Adding maintainers

The project would be healthier with more than one. The path is unglamorous and
deliberately so: contribute a few substantive changes, demonstrate you understand why
the two invariants exist, then ask. Commit-bit follows demonstrated judgement about
what *not* to change.

There is no probationary period or committee. If you have done the work, you are in.

## If the maintainer goes away

Realistic planning for a one-person project that other organizations may come to
depend on.

**The schemas outlive the maintainer.** They are Apache-2.0, plain JSON, and the
[conformance suite](conformance/README.md) defines correct behaviour independently of
any implementation. A second implementation already exists in TypeScript. So the
format is forkable and independently verifiable without anyone's cooperation — which
is the single most important property for anything meant to be adopted sector-wide,
and the reason the suite exists.

**If this repository goes unmaintained**, in order of preference:

1. Open an issue asking about status. Life happens; a maintainer may simply be busy.
2. If there is no response for **90 days**, consider the project dormant and fork it.
   You have the licence to. Please rename the fork so users are not confused about
   which is maintained, and say in your README that it is a fork and why.
3. If you fork and intend to maintain it, say so in an issue here. If the maintainer
   returns, that makes it possible to point users at you rather than duplicate effort.

**A fork is not a hostile act.** It is what the licence is for, and a format that
cannot be forked is not really open.

**What a successor should preserve:**

- The two invariants in [ARCHITECTURE.md](ARCHITECTURE.md). They are the reason the
  project is worth anything.
- Citations for every federal requirement. Never assert a rule on the project's own
  authority.
- Synthetic example data only. No real subscriber or location data, ever.
- Honest documentation of gaps and limits. The known-gaps section and the
  "indicative, not binding" framing on compliance verdicts are load-bearing, not
  hedging.

## Relationship to agencies and vendors

None. The project is not affiliated with, endorsed by, or sponsored by NTIA, the FCC,
USAC, or any equipment manufacturer or service provider, and states so in the NOTICE,
the README, and the docs.

It does not claim to be a standard, to be on track to become one, or to be endorsed
by any standards body. It is a proposal that exists and works. If it ever becomes
something more formal, that will be through a process this file will need rewriting to
describe.

## Code of conduct

[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Enforced by the maintainer, which given the
project's size means: be straightforward and civil, and assume the person on the other
end is trying to get broadband to somewhere that does not have it.
