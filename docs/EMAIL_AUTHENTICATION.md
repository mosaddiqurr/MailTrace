# Email Authentication

SPF evidence is associated with the reported envelope or HELO identity; DKIM evidence uses the signing `d=` domain; DMARC relates RFC5322 From to aligned SPF or DKIM. MailTrace parses these values and compares domains. It does not retrieve historical DNS keys or cryptographically verify signatures.

ARC instances, seals, message signatures, and ARC authentication results are inventoried. Recorded chain status and sequence problems are evidence, not independent ARC validation.
