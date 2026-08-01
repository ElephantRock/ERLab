# Security Policy

## Secrets management

- API keys are stored in `.env` (gitignored)
- `.env.example` contains placeholders only
- `.env.docker` and `.env.test.example` contain no real credentials
- No secrets are committed to the repository

## Data handling

- Runtime databases (`data/elephant_rock.db`) are gitignored
- Generated datasets are gitignored unless redistributable
- The UCI Wine Quality and Concrete Strength datasets are CC BY 4.0
- The Iris dataset is public domain
- No sensitive attributes are used in any registered dataset

## Provider responses

- Provider responses are not persisted to the repository
- The typed claim composer sanitizes provider output before paper assembly
- The LLM cannot generate RESULT markers or empirical values

## Reporting vulnerabilities

Report security issues by contacting the repository maintainers directly.
Do not open public issues for security vulnerabilities.
