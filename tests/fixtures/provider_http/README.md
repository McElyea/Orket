# Public TLS test fixtures

These certificates and the deliberately public server key are ONLY for controlled
loopback tests. They do not authorize any production endpoint. Validity is fixed
2020-2040; tests exercise actual certificate verification, not verify=False.
The trust-directory filename is the OpenSSL subject hash of ca.pem.

The legacy/ chain intentionally lacks strict X.509 extensions. It is retained
only as a negative handshake control for Python 3.13-style strict verification.
