# Security policy

## Supported versions

Security fixes target the latest 1.x version. Older major versions are not
maintained. Keep Repowise and MarkItDown up to date as well as this plugin.

## Reporting a vulnerability

Do not disclose vulnerabilities, exploit PDFs or sensitive logs in public issues
or pull requests. Use
[GitHub private vulnerability reporting](https://github.com/digimangos/repowise-markitdown-plugin/security/advisories/new)
when available. If it is unavailable, contact the repository owner privately
through a contact channel listed on their [profile](https://github.com/digimangos)
to arrange a secure reporting channel before sending details.

Include affected versions, impact, reproduction steps and a minimal non-sensitive
example. Do not send credentials or confidential documents. Reporting and fixes
are handled on a best-effort basis; no response or remediation SLA is promised.

## Processing untrusted PDFs

PDF parsing processes untrusted binary input. The plugin uses MarkItDown's PDF
converter without third-party converter plugins or cloud services. Repowise owns
worker isolation, timeouts and size limits. These controls are not a guarantee
that a malicious PDF is safe. Use an appropriately isolated environment and
least-privilege access when processing untrusted files.
