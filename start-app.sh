#!/usr/bin/env bash
# Open the Kitsnap phone app in Expo Go.
#
# Needs Node.js 22 (nodejs.org) on this computer and the Expo Go app on your
# phone. The app talks to the hosted Kitsnap server, so nothing else has to run
# here. When the QR code appears: on iPhone, scan it with the Camera app; on
# Android, scan it from inside Expo Go.
#
# Phone and computer on the same Wi-Fi is the fast way. If they are not, run
# `./start-app.sh --tunnel` instead and say yes when it offers to install the
# tunnel.
set -e
cd "$(dirname "$0")/app"
echo "Installing the app (first run takes a few minutes)..."
npm install --no-audit --no-fund
echo
echo "Starting Kitsnap. Scan the QR code below with your phone."
exec npx expo start "$@"
