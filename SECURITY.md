# Security policy

ResearchPilot is experimental single-user software intended for localhost. Only the latest source on the default branch receives fixes. It is not designed for public or shared hosting.

## Reporting a vulnerability

Use the repository's GitHub **Security → Report a vulnerability** option if private reporting is enabled. If it is unavailable, open an issue asking the maintainer for a private contact channel without including exploit details, credentials, or private documents. Do not disclose sensitive material in public issues.

Include the affected revision, a minimal reproduction with synthetic data, expected impact, and any proposed mitigation. No response-time guarantee is currently offered.

## Data handling

Custom provider keys are held in browser memory and passed to the local server. Configured provider requests can transmit questions and source excerpts to that provider. Keep local environment files private and rotate any exposed credentials. Git ignore rules do not remove files from older Git history.
