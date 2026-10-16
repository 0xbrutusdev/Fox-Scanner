# Security Policy

## Reporting a vulnerability

Please report vulnerabilities privately through **GitHub Security Advisories**:
open the [Security tab](https://github.com/0xPunisher/crawlscan/security/advisories/new) of this repository and choose *Report a vulnerability*.

Please do not open public issues for security problems. Include steps to reproduce and the impact you see; we will reply as soon as we can and credit you in the fix unless you prefer otherwise.

## Scope

FoxScanner is **read-only**:

- it holds no private keys and never signs or sends transactions;
- it never asks users to connect a wallet;
- the only secrets are the RPC endpoints, read from the `BNB_RPC`, `CRAWLER_RPC` (Robinhood Chain) and `SOLANA_RPC` environment variables and never stored in the repository.

Relevant reports include anything that could leak an RPC endpoint, let a request run arbitrary code or read files on the server (including through `/static/`), or make the service unavailable to others.
