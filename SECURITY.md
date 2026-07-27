# Security Policy

## Supported Versions

Codemaster-Ai is actively maintained and security updates are provided for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |
| < 1.0   | :x:                |

*(Note: Since Codemaster-Ai is a local-first, privacy-first agent running on-premise, ensure you are pulling the latest updates from the main branch for all security patches.)*

---

## Security Architecture & Best Practices

Because Codemaster-Ai handles local LLM orchestration and code generation:
* **Data Privacy:** All operations run locally via Docker and Ollama, ensuring your code and data never leave your machine.
* **Dependencies:** We utilize automated Dependabot updates to monitor Python packages (FastAPI, sentence-transformers, etc.) and GitHub Actions for vulnerabilities.

---

## Reporting a Vulnerability

We take the security of Codemaster-Ai very seriously. If you discover a security vulnerability, please follow these steps:

1. **Do Not Open Public Issues:** If you find a security flaw, please avoid disclosing it publicly until it has been safely addressed to protect all users.
2. **How to Report:** Reach out directly or report the vulnerability through GitHub's private vulnerability reporting feature on the repository.
3. **What to Expect:**
   * **Acknowledgment:** You can expect an initial response acknowledging your report within 48 to 72 hours.
   * **Updates:** Regular updates will be provided regarding the status of the investigation and fix timeline.
   * **Resolution:** If accepted, a patch will be deployed to the main branch and included in the next secure release.
