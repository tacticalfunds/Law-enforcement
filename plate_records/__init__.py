"""plate_records: look up vehicle records from public sources.

This package implements the *legal, public* parts of a plate-lookup pipeline:

  * VIN decoding via NHTSA vPIC (no key, no permissible purpose required)
  * Recall lookups via NHTSA (public)

Restricted data (title/history via NMVTIS, or owner/registration info that is
protected by the Driver's Privacy Protection Act) is exposed only through a
pluggable provider interface. No such provider is implemented here: you must
supply one backed by an account you are legally authorized to use.
"""

__version__ = "0.1.0"
