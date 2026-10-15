# Privacy

No voices, stock archives, account credentials, device connection records, captures or personal research material are included. The app has no telemetry, cloud account login, automatic discovery scan or diagnostic upload.

Network activity occurs only after a user requests a connection check or explicitly approves installation. It is limited to the specified private-LAN device and, during installation, a temporary HTTP server bound to the route's local interface. The server exposes one generated random path, permits the target source address only, records no request logs and closes after the bounded observation. It is not a general file server. HTTP carries the voice archive without transport encryption; use a trusted LAN. Source-address filtering is not strong authentication.

The device ID, address and local key are entered locally or read from a file the user explicitly selects. They are not saved by this program, passed as command arguments or included in error messages. The key field clears when an installation attempt starts. Clear credentials and close the app when finished. Python and operating-system memory are not guaranteed securely erased; users should protect crash dumps and process access.

User-selected audio is processed locally through FFmpeg, with network input protocols disabled. Audio paths appear in local process arguments and can be seen by local process inspection. Temporary previews/conversions are cleaned up after normal completion; interrupted processes or storage may retain remnants. FFmpeg installation through the optional setup script contacts its package sources only when the user runs and approves it.

Original stock files and package configuration are preserved in generated archives. Inputs and outputs are not certified anonymous. Do not share connection JSON, stock archives, generated audio, raw device responses or screenshots of private settings. The program does not create a troubleshooting export.

Public releases are assembled from an explicit source allowlist and separately audited runtime assets. No owner-specific addresses, keys, serial/device identifiers, personal paths or owner software-build details are included. Third-party libraries can contain public author contacts and generic networking examples; these are not private device information. Publisher account details and future commits can independently identify a publisher and require separate review.
