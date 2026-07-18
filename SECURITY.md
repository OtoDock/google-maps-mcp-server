# Security Policy

This repository is a standalone MCP server exposing Google Maps APIs
(Places, Directions, Geocoding, Roads) to AI agents. It handles a Google API
key and constructs requests from model-supplied tool arguments, so credential
handling and input handling are the surfaces that matter.

## Reporting a vulnerability

Please report vulnerabilities **privately** — do not open a public issue for
anything security-sensitive.

- **Preferred:** GitHub private vulnerability reporting — go to this
  repository's **Security** tab → **Report a vulnerability**. Reports land
  directly with the maintainer, privately.
- **Email:** [security@otodock.io](mailto:security@otodock.io)

You'll get an acknowledgment within **72 hours** and a status update as the
report is triaged. Confirmed issues are fixed ahead of feature work, with
credit to the reporter (if you'd like it).

Reports are assessed against the current `main` branch. Vulnerabilities in
the OtoDock **platform** itself belong on
[OtoDock/oto-dock](https://github.com/OtoDock/oto-dock/security) instead.

There is no paid bounty program at this time — just fast fixes, honest
credit, and our thanks.

## Scope

Especially interesting to us:

- API-key exposure — the key leaking into logs, error messages, or tool
  output returned to the model
- Injection through tool arguments (request smuggling, SSRF via
  attacker-controlled parameters)
- Dependency vulnerabilities with a demonstrated impact on the server
