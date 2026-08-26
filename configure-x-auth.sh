#!/usr/bin/env bash
set -Eeuo pipefail

CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/x-ai-brief"
CREDENTIALS_FILE="${X_AI_BRIEF_CREDENTIALS:-$CONFIG_DIR/credentials.env}"

printf '%s\n' 'In Zen, open x.com, press F12, then open Storage > Cookies > https://x.com.'
printf '%s\n' 'Copy only the auth_token and ct0 cookie values into the hidden prompts below.'
read -rsp 'auth_token: ' AUTH_TOKEN_VALUE
printf '\n'
read -rsp 'ct0: ' CT0_VALUE
printf '\n'

if [[ ! "$AUTH_TOKEN_VALUE" =~ ^[A-Za-z0-9._~+-]+$ ]] || [[ ! "$CT0_VALUE" =~ ^[A-Za-z0-9._~+-]+$ ]]; then
  echo 'Credentials were empty or contained unexpected characters; nothing was saved.' >&2
  exit 1
fi

install -d -m 700 "$CONFIG_DIR"
umask 077
{
  printf 'AUTH_TOKEN=%s\n' "$AUTH_TOKEN_VALUE"
  printf 'CT0=%s\n' "$CT0_VALUE"
} >"$CREDENTIALS_FILE"
chmod 600 "$CREDENTIALS_FILE"
unset AUTH_TOKEN_VALUE CT0_VALUE

echo "Saved X session credentials to $CREDENTIALS_FILE (mode 600)."
echo 'Log out of X to revoke them, or delete this file to remove the remote copy.'
