# Release checklist

- Stage only the files explicitly listed in release-files.json; never package a research workspace.
- Reject symbolic links and paths outside staging. Include no recordings, voice packs, APKs, captures, keys, account data or device identifiers.
- Scan source and the extracted final archive against privately held owner references and generic address, credential and personal-path patterns. Keep reference values private.
- Normalize archive metadata and timestamps. Include no Git history, personal author metadata or machine paths.
- Run synthetic archive-safety checks and a synthetic audio conversion check. Device testing is separate and requires explicit approval.
- This preview is source only. Review and scan any future executable, dependencies, installer metadata and debug symbols separately.
- Review the publishing account and any commits before uploading. Preparing this archive does not publish it.
