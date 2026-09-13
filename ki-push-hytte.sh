#!/bin/bash
# Bruk: bash ~/ki-push-hytte.sh 2.3.2
set -e
V=$1
[ -z "$V" ] && { echo "Bruk: ki-push-hytte.sh 2.3.2"; exit 1; }
REPO=~/Documents/HomeAssistant/ki-hyttebes-k
U=${V//./_}                      # 2.3.2 -> 2_3_2

cd ~/Downloads
# Godta begge navnestiler: ki-hyttebesok-2.3.2.zip og ki-hyttebesok-2_3_2.zip
ZIP=""
for kandidat in "ki-hyttebesok-$V.zip" "ki-hyttebesok-$U.zip"; do
  [ -f "$kandidat" ] && ZIP="$kandidat" && break
done
[ -z "$ZIP" ] && { echo "Fant ingen ki-hyttebesok-$V.zip eller ki-hyttebesok-$U.zip i ~/Downloads"; exit 1; }

rm -rf "ki-hyttebesok-$V" && unzip -oq "$ZIP" -d "ki-hyttebesok-$V"

# Pakka kan ha innholdet i en mappe «ki-hyttebesok/» eller rett på rota
KILDE="ki-hyttebesok-$V"
[ -d "$KILDE/ki-hyttebesok" ] && KILDE="$KILDE/ki-hyttebesok"
[ -d "$KILDE/custom_components" ] || { echo "Fant ingen custom_components i pakka"; exit 1; }

[ -d "$REPO/.git" ] || git clone -q https://github.com/SebastianKristo/ki-hyttebes-k.git "$REPO"
cp -r "$KILDE/." "$REPO/"
cd "$REPO"
perl -pi -e "s/\"version\": \"[^\"]*\"/\"version\": \"$V\"/" custom_components/ki_hyttebesok/manifest.json
git add .
git commit -m "KI Hyttebesøk v$V" || true
git push origin main
git tag -f "v$V" && git push -f origin "v$V"

# Release rett fra RELEASE.md, så du slipper å lage den i nettleseren
NOTAT=""
[ -f RELEASE.md ] && NOTAT="--notes-file RELEASE.md"
if gh release view "v$V" >/dev/null 2>&1; then
  gh release edit "v$V" $NOTAT
  echo "Ferdig. Release v$V oppdatert."
else
  gh release create "v$V" --title "v$V" $NOTAT
  echo "Ferdig. Release v$V opprettet."
fi
