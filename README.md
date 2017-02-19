# tollur - A scriptable SMTP proxy
#### Version 0.7 / "Manipulation Through The Nation"

## Introduction
Tollur is small SMTP proxy that passes each incoming message to a user specified "handler" plugin for processing.  

The "handler" plugin is able to inspect the message in order to decide whether or not it should be forwarded.  
It could also optionally be used to manipulate message properties such as recipients or the body.

These "handlers" could be used to require user confirmation of mail to external recipients, inspect the randomness in PGP MIME, minimize information leakage in headers or similar - endless possibilities! :-)

Many of these tasks could likely be performed by a plugin in the user's mail client, but Tollur is designed to work transparently in environments where the clients aren't always trusted.  

A "handler" is just a Python class with a mandatory function that returns True/False and a message object.  
The "handlers" directory contains a simple example of such a plugin, which implements a recipient white list.  


## Current status
- Still alpha, limited testing
- Should not be trusted with anything precious, but can be used to proxy mail!
- Supports strict SMTPS and START_TLS for upstream connection
- The code and the underlying components ("smtlib" and "smtpd") have not been audited for security issues
- Suffers from some parallelization issues - see issue #9 for details


## Usage
At the moment, the code and example configuration is probably the best source for usage information


## Commercial support
Triple nine SLA and professional consulting is available for owners of large sums of Bitcoins


## Dependencies
- Python 3.5 or later with the standard library
- OpenSSL version 0.9.8 or later for SMTPS and START_TLS
- A lot of self control and limited respect for future you, trying to send some mail
