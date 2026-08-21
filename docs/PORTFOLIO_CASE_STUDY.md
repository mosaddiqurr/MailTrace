# Portfolio Case Study

MailTrace addresses a common investigation gap: raw email headers are technically rich but difficult to interpret. The application gives students, analysts, and responders a simple local workflow while preserving forensic detail.

Its FastAPI/SQLite backend performs bounded RFC email parsing, authentication-context extraction, identity alignment, delivery reconstruction, MIME/attachment hashing, URL inventory, and deterministic explainability. A responsive React interface presents the strongest observations first and keeps raw evidence available. Security choices prevent content execution and default network access. Automated backend, API, security, frontend, and real-stack tests provide reproducible evidence. The main limitations are the absence of independent cryptographic verification, malware scanning, historical DNS, and receiver trust proof.
