# Security

MailTrace never executes attachments, opens links, fetches remote images, or renders active message HTML. Upload, header, MIME-depth, MIME-part, attachment, decoded-size, URL-count, and processing-time boundaries limit hostile input. Storage names are generated, paths are confined, null bytes are rejected, exports escape content, CSV formulas are neutralised, and internal exceptions are replaced by safe request IDs.

Optional DNS is disabled until explicitly enabled. Report suspected vulnerabilities privately and do not upload sensitive evidence to third-party issue trackers.
