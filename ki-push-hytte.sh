#!/bin/bash
# Bruk: bash ~/ki-push-hytte.sh 1.0.0
set -e
V=$1
[ -z "$V" ] && { echo "Bruk: ki-push-hytte.sh 1.0.0"; exit 1; }
REPO=~/Documents/HomeAssistant/ki-hyttebes-k
cd ~/Downloads
rm -rf "ki-hyttebesok-$V" && unzip -oq "ki-hyttebesok-$V.zip" -d "ki-hyttebesok-$V"
[ -d "$REPO/.git" ] || git clone -q https://github.com/SebastianKristo/ki-hyttebes-k.git "$REPO"
cp -r "ki-hyttebesok-$V/ki-hyttebesok/." "$REPO/"
cd "$REPO"
perl -pi -e "s/\"version\": \"[^\"]*\"/\"version\": \"$V\"/" custom_components/ki_hyttebesok/manifest.json
git add .
git commit -m "KI Hyttebesøk v$V" || true
git push origin main
git tag -f "v$V" && git push -f origin "v$V"
echo "Ferdig. Lag release: https://github.com/SebastianKristo/ki-hyttebes-k/releases/new?tag=v$V"
