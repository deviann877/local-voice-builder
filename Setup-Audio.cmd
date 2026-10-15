@echo off
title Install FFmpeg audio tools
echo This installs FFmpeg from the Windows Package Manager community source.
echo Review the package and license prompts before accepting.
winget install --exact --id Gyan.FFmpeg --source winget
echo Close and reopen Local Voice Studio after installation.
pause
