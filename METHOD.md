# Experimental installation approach

Research established that a local voice-update request can direct a compatible vacuum to fetch an archive from a temporary local HTTP server. A modified audio clip was heard after a successful update. This is a limited observation, not a general compatibility guarantee. Device-specific evidence and identifiers are intentionally excluded from this distribution.

The observed transport used a Tuya local control operation, a voice-update data point and a length-prefixed protobuf description carrying a package selection, download location, MD5, version and byte count. MD5 is a transfer checksum, not a manufacturer signature. Ordinary language selection and actual package transfer must be distinguished. A success status alone is insufficient; confirm the changed audio and normal operation.

An installation tool must first independently establish model and firmware compatibility, obtain the user's own local connection material privately, validate the original package layout, preserve a stock recovery option and obtain explicit confirmation before writing. Serve only the selected file for a bounded interval, verify complete transfer, observe status and close the server. Never expose a general filesystem server or assume increasing a version is safe. Do not invent protocol fields or infer compatibility from a related model.

Official language selection restored stock audio after successful experimental updates. Recovery following a rejected or interrupted update remains unproven. Power-loss behavior, persistence across updates and long-term operation require further testing. No physical-device actions are performed by this release.

A complete public installer is pending compatibility and recovery validation. The offline builder is the independently usable part of this preview.
