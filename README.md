# CleyxOS v2.0 — Terminal Edition

CleyxOS is a Python 3.14 terminal environment simulation for Windows 10/11. It is an application, not an operating system, and only dispatches its documented command set; aliases never invoke a platform shell.

## Start

Double-click `CleyxOS.bat`. The existing launcher creates `.venv` with Python 3.14 and installs `requirements.txt` if needed. Internet is required for initial installation and online commands. Run `python main.py` inside the environment to start directly. Set `CLEYXOS_NO_ANIMATION=1` to skip the boot delay.

## v2 command groups

- System: `whoami`, `hostname`, `disk`, `ram`, `cpu`, `gpu`, `battery`, `top [seconds] [cpu|ram|name]`, `env`, `which`, `kill <pid>`, `reboot-shell`.
- Files: `tree`, `find`, `grep`, `head`, `tail`, `wc`, `du`, `df`, `hash`, `zip`, `unzip`, `edit`, `backup`, `restore`.
- Network: `ip`, `publicip`, `dns`, `http`, `download`, `netstat`, `speedtest`.
- Productivity: `todo`, `note`, `timer`, `stopwatch`, `remind`, `alias`.
- Special: `matrix [speed]` and `cleyx`.

Run `help` for descriptions and `help`/Tab completion for command and subcommand suggestions. `language en` and `language tr` set the persistent interface language. Arrow keys retain sequential command history navigation.

## Safety

- `kill` displays process details, requires an explicit `yes`, and refuses protected processes or processes owned by another user. No force-kill is attempted.
- `env` masks values for environment variable names associated with passwords, secrets, tokens, keys, credentials, authentication, and connection strings.
- `download` accepts HTTPS only, asks for confirmation, limits downloads to 512 MiB, refuses overwrites, cleans up interrupted partial files, and never executes downloaded content.
- ZIP extraction validates archive paths, blocks traversal and symlink traversal, limits archive entries/expanded size, and asks before overwriting existing files.
- `backup` creates a new ZIP; `restore` validates it and confirms collisions. `rm`, task/note removal, and other destructive commands retain confirmations.
- `app remove` removes only a CleyxOS registration and never uninstalls a Windows application.
- `speedtest` requires confirmation before its approximate 6 MiB Cloudflare test. `publicip`, DNS, HTTP, weather, and downloads contact their documented network services.

## Persistence and tests

Configuration, app registrations, history, tasks, notes, and aliases are stored under `%APPDATA%\\CleyxOS`. Aliases can target only a safe, documented built-in command; shell chaining and privileged/destructive targets are rejected, and recursive expansion is bounded.

Run `python -m unittest discover -s tests` from the project directory.

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
