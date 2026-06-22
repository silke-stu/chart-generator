#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"

osascript - "$DIR" <<'OSASCRIPT'
on run argv
    set d to item 1 of argv

    set backendCmd to "cd '" & d & "/backend'" & \
        " && python3 -m venv venv" & \
        " && source venv/bin/activate" & \
        " && pip install --upgrade pip -q" & \
        " && pip install -r requirements-local.txt" & \
        " && uvicorn src.main:app --reload --port 5001"

    -- Suche Node.js in üblichen Installationspfaden (Homebrew, nvm, fnm, official installer)
    set nodeSetup to "export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH" & \
        "; [ -s \"$HOME/.nvm/nvm.sh\" ] && source \"$HOME/.nvm/nvm.sh\"" & \
        "; [ -s \"$HOME/.fnm/fnm\" ] && eval \"$(\"$HOME/.fnm/fnm\" env)\""
    set frontendCmd to nodeSetup & \
        "; cd '" & d & "/frontend'" & \
        " && npm install && npm run dev"

    tell application "Terminal"
        activate
        do script backendCmd
        delay 2
        do script frontendCmd
    end tell
end run
OSASCRIPT
