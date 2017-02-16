# tollur - A scriptable SMTP proxy
#### Version 0.6 / "Cryptic Struggles"

## Introduction
Tollur is small SMTP proxy that requires each outgoing message to be "verified" before it's forwarded.  
The verification is performed by a user specified "verifier" plugin, which is basically a Python class with a function that returns True or False for each message based on arbitrary critiera - in other words endless possibilities!

These verifiers could be used to require user confirmation of external mail, inspect the randomness in PGP MIME or similar.  

The "verifiers" directory contains a simple example of such a plugin, which checks if recipients domains are white list.  


## Current status
- Still very alpha, limited testing
- Should not be trusted with anything precious, but can be used to proxy mail!
- The code and the underlying components ("smtlib" and "smtpd") have not been audited for security issues
- Suffers from some parallelization issues


## Usage
At the moment, the code and example configuration is probably the best source for usage information


## Commercial support
Triple nine SLA and professional consulting is available for Fortune 500 companies


## Dependencies
- Python 3.5 or later with the standard library
- OpenSSL version 0.9.8 or later for SMTPS and START_TLS
- A lot of self control and limited respect for future you, trying to send some mail
