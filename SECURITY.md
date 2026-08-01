# Security Policy

## Reporting a Vulnerability

Please use [GitHub private vulnerability reporting](https://github.com/ShoGinn/tax-tracker/security/advisories/new) to report a suspected vulnerability. Do not open a public issue for an undisclosed security problem.

Include enough detail to reproduce and assess the issue, but use synthetic data. Never submit real tax records, credentials, financial account information, Social Security numbers, addresses, or other personally identifiable information.

You can expect an initial acknowledgement within seven days. Confirmed issues will be prioritized based on impact and exploitability, and disclosure will be coordinated through the private advisory.

## Supported Versions

Security fixes target the latest release and the current `main` branch. Older releases may not receive backports.

## Scope Notes

Tax Tracker stores personal records in browser IndexedDB and sends calculation inputs transiently to a stateless API. Reports involving browser-storage isolation, unintended server persistence, sensitive-data exposure, dependency vulnerabilities, or deployment configuration are in scope.

Questions about calculation correctness that do not involve a security or privacy issue should use the public bug-report form with synthetic inputs.
