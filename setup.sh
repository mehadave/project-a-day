#!/usr/bin/env bash
# One-time setup for the Project-a-Day Agent.
# Run this once after cloning / first checkout.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #
ok()   { echo "   ✓ $*"; }
err()  { echo "Error: $*" >&2; exit 1; }
info() { echo ""; echo "==> $*"; }

# ------------------------------------------------------------------ #
# 0. Pre-flight checks                                                 #
# ------------------------------------------------------------------ #
info "Pre-flight checks"

[ -f ".env" ] || err ".env not found. Copy .env.example to .env and add your GITHUB_TOKEN."
[ -f "config.toml" ] || err "config.toml not found."

# Load environment variables from .env
# The `|| true` in the while condition handles files with no trailing newline
set -a
while IFS='=' read -r key value || [ -n "$key" ]; do
    # Skip comments and blank lines
    [[ "$key" =~ ^[[:space:]]*# ]] && continue
    [[ -z "${key// }" ]] && continue
    # Strip inline comments and surrounding quotes from value
    value="${value%%#*}"
    value="${value%"${value##*[![:space:]]}"}"
    value="${value#\"}" value="${value%\"}"
    value="${value#\'}" value="${value%\'}"
    export "$key"="$value"
done < .env
set +a

[ -n "$GITHUB_TOKEN" ] || err "GITHUB_TOKEN not set in .env"

# Check Claude Code CLI
command -v claude &>/dev/null || err "'claude' CLI not found. Install it from the Claude desktop app menu (Claude → Install CLI) or via: npm install -g @anthropic-ai/claude-code"
ok "Claude Code CLI: $(claude --version 2>/dev/null | head -1)"

# Find Python 3.11+
PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3; do
    if command -v "$candidate" &>/dev/null; then
        version=$("$candidate" -c 'import sys; print(sys.version_info[:2])')
        if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
            PYTHON="$candidate"
            break
        fi
    fi
done
[ -n "$PYTHON" ] || err "Python 3.11+ not found. Install it from https://python.org"
ok "Using Python: $PYTHON ($($PYTHON --version))"

# Read config values via Python (handles TOML parsing correctly)
GITHUB_USERNAME=$($PYTHON -c "import tomllib; c=tomllib.load(open('config.toml','rb')); print(c['github']['username'])")
REPO_NAME=$($PYTHON -c "import tomllib; c=tomllib.load(open('config.toml','rb')); print(c['github']['repo_name'])")
BUILD_HOUR=$($PYTHON -c "import tomllib; c=tomllib.load(open('config.toml','rb')); print(c['agent']['build_hour'])")
BUILD_MINUTE=$($PYTHON -c "import tomllib; c=tomllib.load(open('config.toml','rb')); print(c['agent']['build_minute'])")

[ "$GITHUB_USERNAME" != "YOUR_GITHUB_USERNAME" ] || err "Set your GitHub username in config.toml"
ok "GitHub: $GITHUB_USERNAME/$REPO_NAME"
ok "Scheduled build: ${BUILD_HOUR}:$(printf '%02d' "$BUILD_MINUTE") daily"

# ------------------------------------------------------------------ #
# 1. Python virtual environment                                        #
# ------------------------------------------------------------------ #
info "Python virtual environment"

if [ ! -d "venv" ]; then
    $PYTHON -m venv venv
    ok "Created venv/"
fi

# shellcheck disable=SC1091
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
ok "Dependencies installed"

# ------------------------------------------------------------------ #
# 2. Git repository                                                    #
# ------------------------------------------------------------------ #
info "Git repository"

if [ ! -d ".git" ]; then
    git init -b main
    git config user.email "projectaday@local"
    git config user.name "Project-a-Day Agent"
    ok "Initialized git repo"
fi

# Initial commit if repo is empty
if ! git rev-parse HEAD > /dev/null 2>&1; then
    git add -A
    git commit -m "chore: initial commit — project-a-day agent"
    ok "Created initial commit"
else
    ok "Git repo already has commits"
fi

# ------------------------------------------------------------------ #
# 3. GitHub repository                                                 #
# ------------------------------------------------------------------ #
info "GitHub repository"

HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github.v3+json" \
    "https://api.github.com/repos/$GITHUB_USERNAME/$REPO_NAME")

if [ "$HTTP_STATUS" = "404" ]; then
    curl -s -X POST "https://api.github.com/user/repos" \
        -H "Authorization: token $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github.v3+json" \
        -H "Content-Type: application/json" \
        -d "{\"name\": \"$REPO_NAME\", \"description\": \"A project a day — built with Claude AI\", \"private\": false}" \
        > /dev/null
    ok "Created: https://github.com/$GITHUB_USERNAME/$REPO_NAME"
elif [ "$HTTP_STATUS" = "200" ]; then
    ok "Already exists: https://github.com/$GITHUB_USERNAME/$REPO_NAME"
else
    echo "   Warning: GitHub API returned HTTP $HTTP_STATUS (token may lack 'repo' scope)"
fi

# ------------------------------------------------------------------ #
# 4. Git remote                                                        #
# ------------------------------------------------------------------ #
info "Git remote"

if ! git remote get-url origin > /dev/null 2>&1; then
    git remote add origin "https://github.com/$GITHUB_USERNAME/$REPO_NAME.git"
    ok "Remote 'origin' added"
else
    ok "Remote 'origin' already set"
fi

# ------------------------------------------------------------------ #
# 5. Initial push                                                      #
# ------------------------------------------------------------------ #
info "Initial push to GitHub"

GIT_TERMINAL_PROMPT=0 git push \
    "https://$GITHUB_TOKEN@github.com/$GITHUB_USERNAME/$REPO_NAME.git" main \
    2>&1 || \
GIT_TERMINAL_PROMPT=0 git push --set-upstream \
    "https://$GITHUB_TOKEN@github.com/$GITHUB_USERNAME/$REPO_NAME.git" main \
    2>&1 || \
ok "Push skipped (will push on first project build)"

ok "GitHub repo ready"

# ------------------------------------------------------------------ #
# 6. launchd daily trigger                                             #
# ------------------------------------------------------------------ #
info "macOS launchd daily trigger (${BUILD_HOUR}:$(printf '%02d' "$BUILD_MINUTE"))"

PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$PLIST_DIR/com.mehadave.projectaday.plist"
mkdir -p "$PLIST_DIR"

cat > "$PLIST_PATH" << PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.mehadave.projectaday</string>
    <key>ProgramArguments</key>
    <array>
        <string>${SCRIPT_DIR}/run.sh</string>
        <string>--headless</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>${BUILD_HOUR}</integer>
        <key>Minute</key>
        <integer>${BUILD_MINUTE}</integer>
    </dict>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
        <key>HOME</key>
        <string>${HOME}</string>
    </dict>
    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>
    <key>StandardOutPath</key>
    <string>${SCRIPT_DIR}/logs/run.log</string>
    <key>StandardErrorPath</key>
    <string>${SCRIPT_DIR}/logs/error.log</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
PLIST_EOF

# Reload the plist
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"
ok "Installed and loaded: $PLIST_PATH"

# ------------------------------------------------------------------ #
# Done                                                                 #
# ------------------------------------------------------------------ #
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║           Project-a-Day Agent is ready!              ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "  GitHub:   https://github.com/$GITHUB_USERNAME/$REPO_NAME"
echo "  Schedule: Every day at ${BUILD_HOUR}:$(printf '%02d' "$BUILD_MINUTE") AM (headless)"
echo ""
echo "  Commands:"
echo "    bash run.sh              → Build a project right now (interactive)"
echo "    bash run.sh --queue      → Queue an idea for tomorrow's scheduled build"
echo "    bash run.sh --headless   → Build using queued idea (or auto-generate)"
echo ""
echo "  Check schedule:"
echo "    launchctl list | grep projectaday"
echo ""
echo "  View logs:"
echo "    tail -f logs/run.log"
echo ""
