# Analysis Methodology

MailTrace records facts first, then reported authentication claims, derived comparisons, and contextual observations. Assessment labels follow the strongest supported evidence; confidence reflects evidence completeness and parser warnings. Risk and confidence are separate.

“No clear concern found” means no material concern was observed in supplied evidence. It is not a safe verdict. “Insufficient evidence” is used when the message lacks enough context. Reported SPF, DKIM, DMARC, and ARC results are never presented as independently verified.

Entity correlation uses parsed mailbox fields and structured authentication properties before generic text extraction. Authentication property names are not entities, while valid property values retain property-level provenance. Message-IDs remain message identifiers; their domains may participate in domain correlation without converting the identifier into a mailbox.

IP reporting separates RFC1918/IPv6 ULA private space from loopback, link-local, documentation, multicast, unspecified, reserved, and globally routable addresses. The compatibility `is_private_ip` field means RFC1918 or IPv6 ULA only; documentation prefixes are explicitly labelled `documentation`.
