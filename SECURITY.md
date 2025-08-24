# Security Policy

## Reports

If you discover a vulnerability or privacy issue, please open a GitHub issue with **SECURITY** in the title.
Avoid publishing exploit details; a maintainer will coordinate next steps.

## Data & privacy

- The app stores **preferences only** in `qr_generator_config.json` (colors, sizes, last save path). No payload history or network scans are persisted.
- Optional Wi‑Fi detection/scanning executes **local OS tools** to read SSID/security info; results are used in-app only.

## Risk notice

QR codes can embed links or Wi‑Fi credentials. Review content before sharing. The maintainers are not liable for misuse or data loss.
