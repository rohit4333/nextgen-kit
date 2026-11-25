# DEPRECATED — SAPI/Zira was replaced by Indian-English neural TTS because it
# mispronounced IIIT, Allahabad, Bhanzu and "B.Tech" ("B dot tech").
#
# The real generator is exports\make-reel-voiceover.py (en-IN-NeerjaNeural, edge-tts).
# This wrapper keeps old commands working without regressing the voice.
#
# Run: powershell -ExecutionPolicy Bypass -File .\exports\make-reel-voiceover.ps1

$ErrorActionPreference = 'Stop'
& py (Join-Path $PSScriptRoot 'make-reel-voiceover.py')
