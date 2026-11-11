# TOOLING

Every tool used by this project, its version and how it was installed. Nothing
paid, nothing that needs a trial.

| Tool | Version | Install / source |
| --- | --- | --- |
| Node.js | v24.22.1 | preinstalled on the owner machine |
| pnpm | 12.15.0 | preinstalled |
| Python | 3.14.7 (local), 3.12 (Space image) | local preinstalled; Space image pins 3.12 |
| git | preinstalled | — |
| GitHub CLI | 2.103.3 | preinstalled, authenticated as `ibrahimSumon47` |
| Vercel CLI | 65.4.0 | preinstalled, authenticated |
| Supabase CLI | 2.118.0 | preinstalled, authenticated |
| Hugging Face CLI | `hf` (replaces `huggingface-cli`) | preinstalled, authenticated as `NoobMaster005` |
| Docker | not installed | not required: the Space builds the image |

## Installed during the build

| Tool | Install command | Reason |
| --- | --- | --- |
| project deps | `pnpm install` | web app |
| API deps | `pip install -r api/requirements.txt` (inside Docker) | FastAPI service |

Notes

- Dependabot version-update PRs are intentionally **off**: there is no
  `.github/dependabot.yml`, so GitHub never opens update branches. Security
  alerts stay enabled. This keeps `main` the only branch.
- The Space image installs its own Python wheels; no local Docker is needed.
