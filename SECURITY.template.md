# Security Policy

> **Template notice:** This is a template file. Replace all `{{PROJECT_NAME}}`,
> `[INSERT CONTACT EMAIL]`, and `[INSERT CONTACT METHOD]` placeholders before publishing.
> Update the version table to reflect your project's actual release lines.
> Remove this notice once the file reflects your project's actual policy.

## Supported Versions

Only the versions listed below currently receive security fixes. Vulnerabilities reported
against unsupported versions will not be patched.

| Version | Supported |
| ------- | --------- |
| x.x.x   | Yes       |
| x.x.x   | No        |

Replace the table rows with your project's actual release lines.

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Report vulnerabilities privately by emailing: `[INSERT CONTACT EMAIL]`

Alternatively, you may use: `[INSERT CONTACT METHOD]` (e.g., GitHub private vulnerability
reporting, a dedicated security form, or another private channel).

## What to Include

A useful report contains:

- A clear description of the vulnerability and its potential impact
- The affected {{PROJECT_NAME}} version(s)
- Step-by-step reproduction instructions
- Proof-of-concept code or a minimal example (if available)
- Any suggested remediation (optional but appreciated)

The more detail you provide, the faster we can triage and fix the issue.

## What to Expect

| Milestone                              | Target timeframe          |
| -------------------------------------- | ------------------------- |
| Acknowledgment of receipt              | Within 48 hours           |
| Initial triage and severity assessment | Within 5 business days    |
| Patch or mitigation plan               | Depends on severity       |
| Public disclosure                      | Coordinated with reporter |

We will keep you informed throughout the process. If you have not received an acknowledgment
within 48 hours, follow up at the same address.

## Disclosure Policy

This project follows a **coordinated disclosure** model:

1. The reporter notifies the {{PROJECT_NAME}} maintainers privately and provides sufficient detail to reproduce the issue.
2. The maintainers acknowledge receipt and begin an investigation.
3. The maintainers develop and test a fix, aiming to resolve critical issues within 90 days.
4. A patched release is prepared. The reporter is notified before public release.
5. The fix is released and a public security advisory is published simultaneously.

We ask reporters to refrain from publicly disclosing the vulnerability until a fix has been
released or until we have mutually agreed on a disclosure date. We will not ask for an
embargo longer than 90 days without the reporter's agreement.

## Scope

The following are generally considered in scope:

- Source code in this repository
- Official releases published under this project

The following are generally out of scope:

- Third-party dependencies (report those to the upstream project)
- Vulnerabilities requiring physical access to a device
- Social engineering attacks
- Issues in unsupported versions

If you are unsure whether an issue is in scope, report it anyway and we will advise.
