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

normalize_cookie() {
  local name="$1"
  local value="$2"
  value="${value//$'\r'/}"
  if [[ "$value" =~ ^[[:space:]]*${name}[[:space:]]*[:=][[:space:]]*(.*)$ ]]; then
    value="${BASH_REMATCH[1]}"
  fi
  value="${value#\"}"
  value="${value%\"}"
  value="${value#\'}"
  value="${value%\'}"
  printf '%s' "$value"
}

AUTH_TOKEN_VALUE="$(normalize_cookie auth_token "$AUTH_TOKEN_VALUE")"
CT0_VALUE="$(normalize_cookie ct0 "$CT0_VALUE")"

if [[ -z "$AUTH_TOKEN_VALUE" || -z "$CT0_VALUE" || "$AUTH_TOKEN_VALUE" == *$'\n'* || "$CT0_VALUE" == *$'\n'* ]]; then
  echo 'Credentials were empty or malformed; nothing was saved.' >&2
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
