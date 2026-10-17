# Ownership-change review security

Ownership changes require evidence and **two approvals from two different staff
accounts**. Each reviewer must independently confirm the deed, applicant identity,
and current ownership record, and leave a review note. A rejection takes effect
immediately; one approval alone never changes the owner.

## Configure staff accounts and document encryption

Do not use shared accounts. Add the following settings to the private
`.streamlit/secrets.toml` file (never commit that file):

```toml
ownership_document_key = "<Fernet key>"

[staff_accounts]
reviewer_one = "pbkdf2_sha256$600000$<salt hex>$<password hash hex>"
reviewer_two = "pbkdf2_sha256$600000$<salt hex>$<password hash hex>"
```

Generate a separate password hash for each staff member with Python:

```python
import getpass
import hashlib
import secrets

password = getpass.getpass("Staff password: ").encode("utf-8")
salt = secrets.token_bytes(16)
rounds = 600_000
digest = hashlib.pbkdf2_hmac("sha256", password, salt, rounds)
print(f"pbkdf2_sha256${rounds}${salt.hex()}${digest.hex()}")
```

Generate the document-encryption key once with:

```python
from cryptography.fernet import Fernet

print(Fernet.generate_key().decode("ascii"))
```

Keep the secrets file and its backups private. The app encrypts uploaded evidence
before storing it in SQLite and verifies its SHA-256 digest when staff download
or review it. The encrypted file is erased when the application is approved or
rejected; its SHA-256 digest and review notes remain in the audit history.
Back up the encryption key separately from the database: losing the key makes
open applications' evidence unreadable. Do not rotate the key without first
re-encrypting evidence for open applications.

Applications left over from before evidence was required cannot be approved.
Reject those applications with a note and ask the applicant to submit again with
supporting evidence.

This workflow is a safeguard, not an automated legal verification system. Staff
must compare evidence with authoritative records and verify the original documents
and applicant identity through the appropriate official process. The app changes
only its local GeoJSON data, not a government registry.
