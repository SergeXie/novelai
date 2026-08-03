@echo off
title novelAi MySQL Backup Monitor
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0show-backup-status.ps1" -TaskName "novelAi-MySQL-Backup" -BackupRoot "%~dp0..\..\novelAi" -RefreshSeconds 5
