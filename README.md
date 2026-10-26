# CleyxOS v3.0 — Terminal Edition

CleyxOS is a Python 3.14 terminal environment for Windows 10/11. It is a Python application, not an operating system. It combines a command shell with local Windows app/game discovery, media search, safe desktop controls, and productivity tools.

## Installation

Install Python 3.14, then double-click `CleyxOS.bat`. It creates `.venv` and installs `requirements.txt` on first run. Network access is required for setup. To run manually, activate `.venv` and execute `python main.py`. Set `CLEYXOS_NO_ANIMATION=1` to skip the boot animation.

## Application and Game Launching

Use `launch discord`, `launch "visual studio code"`, `searchapp spotify`, `installed`, `appinfo chrome`, or `appfolder vscode`. CleyxOS searches Start Menu shortcuts, app registry metadata, standard install folders, PATH, and existing registrations; discovery is cached briefly. A selection menu appears for ambiguous names, and launches require confirmation. `openapp` aliases `launch`. `closeapp <name>` displays matching user processes and confirms before closing them. `recentapps` and `favoriteapp add|list|remove` track CleyxOS launches and favorites.

Installed Steam app manifests and Epic local manifests are supported, alongside game shortcuts and manual registrations. Try `games`, `findgame ultrakill`, `play "people playground"`, `gameinfo minecraft`, or `favoritegame add undertale`. `registergame <name> <exe-or-platform-uri>` registers games not detected automatically. `play` asks before launching and uses Steam/Epic protocols when available; it does not bypass DRM or sign-in.

## Media and Windows

Set folders with `video setfolder "C:\\Users\\You\\Videos"` and `music setfolder "D:\\Audio"`. Then use `videos`, `findvideo family`, `watch family`, `video info "clip.mp4"`, `video recent`, `music list`, `music album`, or `playmedia "song.flac"`. Supported formats: MP4/MKV/AVI/MOV/WEBM and MP3/WAV/FLAC/OGG/M4A. Files open in the default Windows media application. `youtube <query>` and `spotify <query>` open service searches.

Windows utilities include `volume 40`, `volume up 5`, `mute`, `brightness 60`, `screenshot`, `clipboard copy <text>`, `clipboard show`, `settings sound`, `taskmanager`, `startupapps`, `lock`, and common folders such as `downloads` and `documents`. `sleep`, `shutdown`, and `restart` require typing `yes`. Volume, brightness, screenshot, and clipboard integrations use optional Windows/Python APIs; brightness depends on monitor support. The clipboard display warns before showing potentially private text.

## Files and Productivity

`findfile <name>` and `findfolder <name>` search common user folders plus paths added with `searchpath add <folder>`; they do not walk entire drives. `openfile`, `reveal`, `largestfiles`, `duplicates`, and `emptyfolders` support everyday file tasks. Duplicate detection only reports matches. `cleanup preview` lists old temporary files; `cleanup run` requires confirmation and only removes the listed, direct-child `.tmp`, `.temp`, and `.log` files from the OS temp folder.

Productivity commands include `quicknote <text>`, `quicknotes`, `calendar [next|previous]`, `convert 5 km mi`, `passwordgen [length]`, `uuid`, `random 1 100`, `qr <text>`, `focus 25m`, `pomodoro`, and `dictionary <word>`. `translate <target-language> <text>` requires a user-configured HTTPS LibreTranslate-compatible endpoint: `config translate-url https://your-provider.example`.

## Workspaces and Help

Workspaces store only typed app/game/folder/URL actions, never shell scripts. Example:

```text
workspace create coding
workspace addapp coding vscode
workspace addapp coding chrome
workspace addfolder coding C:\\Projects
workspace addurl coding https://github.com
workspace run coding
```

Other commands: `workspace list|info|remove`. Run `help`, `commands`, `searchcommand <query>`, `tutorial`, `tutorial <command>`, `examples <command>`, `tips`, `shortcuts`, `whatsnew`, `doctor`, `version`, or `updatecheck`. Tab completion includes commands, subcommands, cached app/game names, workspaces, and local paths. `language en` / `language tr` sets the saved UI language.

## Safety

- App/game launch and workspace execution show what will launch and ask for confirmation; ambiguous results require a selection.
- Windows power actions require explicit typed confirmation. No security settings are changed.
- `findfile` / `findfolder` scan common profile directories and configured roots, not entire drives. Ctrl+C stops a search.
- Workspace JSON is data-only; URLs are HTTP/HTTPS and configured translation endpoints must use HTTPS.
- Existing v2 protections remain: masked environment secrets, safe calculator, confirmed deletes, HTTPS-only size-limited downloads, and ZIP traversal/overwrite defenses.

## Persistence, Limitations, and Troubleshooting

Configuration, cached catalogs, workspaces, favorites, recents, tasks, notes, and aliases are stored under `%APPDATA%\\CleyxOS`. Installed game discovery currently reads Steam/Epic local manifests and Windows shortcuts; other launchers may require a shortcut or `registergame`. Microsoft Store/Xbox games with protected or unavailable launch targets may not start. System controls can be unavailable on unsupported hardware. `dictionary` and online networking commands need an Internet connection. No download is executed automatically.

If an app is missing, refresh its Start Menu shortcut or add it with `app add`; a game can be added with `registergame`. If controls are unavailable, rerun `CleyxOS.bat` to verify dependencies and check display/audio hardware support. Run `doctor` for local diagnostics. Tests: `python -m unittest discover -s tests`.

## ⚠️ BEFORE YOU JUMP ON ME
First of all, **YES, THIS PROJECT WAS AI-CODED.**

I used **GPT-6 Luna through GitHub Copilot Agent Mode** to help build CleyxOS. I'm not going to pretend I manually wrote thousands of lines of Python.

And before anyone starts comparing this project to Linux:

**THIS IS NOT A FUCKING LINUX RIVAL.**

Linux developers are basically **GODS OF THIS TERMINAL SHIT**, and I have nothing but respect for what they've built.

CleyxOS is just a personal project I wanted to make because I like the Linux terminal experience, but I primarily use Windows.

That's literally it.

I'm not trying to replace Linux, reinvent operating systems, or compete with decades of open-source development.

I just wanted a cool, Linux-inspired terminal environment that makes using Windows more convenient and enjoyable.

**It's a Python application, not an actual operating system.**

Please don't crucify me over the name. 💀

---

**Made with AI, curiosity, and an unreasonable amount of laziness.**
