!macro customInstallMode
  ; Keep the install-dir wizard, but force a per-user install so runtime files
  ; stay under a user-writable location next to the packaged executable.
  StrCpy $isForceCurrentInstall 1
!macroend
