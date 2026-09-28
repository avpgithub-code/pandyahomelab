# Self-hosted front-end libraries

Served at `/vendor/…` by pandya-nginx (this folder is bind-mounted into the web root), so
visitors' browsers never contact a third-party code server. All three are MIT-licensed;
each folder keeps its `LICENSE`.

| Library | Version | File | SHA-256 |
|---|---|---|---|
| Mermaid | 10.9.8 | `mermaid-10.9.8/mermaid.min.js` | `8d607d7ef1d077a8aa202e18e62212bfa992c68bfeabc5cf45d51a128fe6675d` |
| Chart.js | 4.4.0 | `chart.js-4.4.0/chart.umd.min.js` | `0e2326c6868072bec1592760c6729043caeea2960a2b46cee6a2192aac6abff0` |
| chartjs-adapter-date-fns | 3.0.0 | `chartjs-adapter-date-fns-3.0.0/chartjs-adapter-date-fns.bundle.min.js` | `ea7ab30d26c38dcf1f2d26bb43e73a94537b58f1906f55e1a546dd09321b5615` |

Downloaded from the npm packages' `dist/` folders (via cdn.jsdelivr.net) on 2026-09-28.
To upgrade: add a new versioned folder next to the old one, point the pages at it,
rebuild the demo images, then delete the old folder.
