#!/usr/bin/env bash
# Captures automatiques des écrans mobiles via adb.
# Pré-requis :
#   - App Gathé Finance installée sur le device (USE_MOCKS=true recommandé)
#   - Téléphone déverrouillé, app **fraîchement relancée** (kill puis lancer)
#
# Le script navigue à l'aveugle via `adb shell input tap` aux coordonnées
# calculées pour un device 720x1600 (TECNO KM5). Pour un autre device :
#   ./capture-mobile.sh --device <ID> [--out docs/captures/mobile]
#
# Usage :
#   ./scripts/capture-mobile.sh
#
set -euo pipefail

DEVICE="${1:-14413155AL013920}"
OUT="${2:-docs/captures/mobile}"
PKG="com.gathefinance.gathe_finance"
ADB="${HOME}/Android/Sdk/platform-tools/adb"

mkdir -p "$OUT"

# Helpers
shot() {
  local name="$1"
  local file="$OUT/${name}.png"
  echo "  📸 $file"
  "$ADB" -s "$DEVICE" exec-out screencap -p > "$file"
}
tap() { "$ADB" -s "$DEVICE" shell input tap "$1" "$2"; sleep 1.5; }
swipe_left()  { "$ADB" -s "$DEVICE" shell input swipe 600 800 100 800 250; sleep 1.5; }
swipe_up()    { "$ADB" -s "$DEVICE" shell input swipe 360 1200 360 400 250; sleep 1.5; }
type_text()   { "$ADB" -s "$DEVICE" shell input text "$1"; sleep 0.5; }
key_enter()   { "$ADB" -s "$DEVICE" shell input keyevent 66; sleep 1.5; }
key_back()    { "$ADB" -s "$DEVICE" shell input keyevent 4; sleep 1.5; }

# ------------------------------------------------------------------
# Coordonnées TECNO KM5 720x1600 (à adapter si autre device)
# ------------------------------------------------------------------
# Bottom-nav (4 onglets) — y autour de 1530, x = 90 / 270 / 450 / 630
NAV_HOME_X=90;    NAV_HOME_Y=1530
NAV_CREDIT_X=270; NAV_CREDIT_Y=1530
NAV_BOOK_X=450;   NAV_BOOK_Y=1530
NAV_PROF_X=630;   NAV_PROF_Y=1530
# CTA "Continuer" onboarding / Login → fond d'écran, bouton central
CTA_X=360; CTA_Y=1450
# Champs login
EMAIL_X=360; EMAIL_Y=620
PASS_X=360;  PASS_Y=770

echo "▶ Préparation : redémarre l'app à zéro pour partir du Splash"
"$ADB" -s "$DEVICE" shell am force-stop "$PKG"
sleep 1
"$ADB" -s "$DEVICE" shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 > /dev/null
sleep 4   # attendre que le splash s'affiche

# ------------------------------------------------------------------
# 1) Splash
# ------------------------------------------------------------------
shot "01-splash"
sleep 3   # attendre la transition vers onboarding

# ------------------------------------------------------------------
# 2-5) Onboarding (4 slides — slide 1 capturée, puis on swipe)
# ------------------------------------------------------------------
shot "02-onboarding-1"
swipe_left
shot "03-onboarding-2"
swipe_left
shot "04-onboarding-3"
swipe_left
shot "05-onboarding-4"

# Tap CTA "Commencer" pour passer au login (en bas centre)
tap $CTA_X $CTA_Y

# ------------------------------------------------------------------
# 6) Login
# ------------------------------------------------------------------
sleep 2
shot "06-login"

# Saisie credentials (mock → n'importe quoi marche)
tap $EMAIL_X $EMAIL_Y
type_text "jean.kamga@test.local"
tap $PASS_X $PASS_Y
type_text "test1234"
"$ADB" -s "$DEVICE" shell input keyevent 4   # fermer le clavier
sleep 1
tap $CTA_X $CTA_Y   # bouton "Se connecter"

# ------------------------------------------------------------------
# 7) PIN setup (1er login)
# ------------------------------------------------------------------
sleep 3
shot "07-pin-setup"

# Saisie PIN "1234" — coordonnées pavé numérique TECNO 720x1600
# Pavé 3 colonnes x 4 lignes, centré, x ≈ 180/360/540, y ≈ 1000/1150/1300/1450
PIN1_X=180; PIN1_Y=1000   # touche 1
PIN2_X=360; PIN2_Y=1000   # touche 2
PIN3_X=540; PIN3_Y=1000   # touche 3
PIN4_X=180; PIN4_Y=1150   # touche 4

# Confirmation PIN demande de retaper → on tape 8 fois pour couvrir setup + confirm
for i in 1 2 3 4 1 2 3 4; do
  case $i in
    1) tap $PIN1_X $PIN1_Y ;;
    2) tap $PIN2_X $PIN2_Y ;;
    3) tap $PIN3_X $PIN3_Y ;;
    4) tap $PIN4_X $PIN4_Y ;;
  esac
done

# ------------------------------------------------------------------
# 8) Home (shell tab 0)
# ------------------------------------------------------------------
sleep 3
shot "08-home"

# Scroll pour voir le bas de la Home
swipe_up
shot "09-home-bas"

# Revenir en haut
"$ADB" -s "$DEVICE" shell input swipe 360 400 360 1200 250
sleep 1

# ------------------------------------------------------------------
# 9-12) Onglets bottom-nav
# ------------------------------------------------------------------
tap $NAV_CREDIT_X $NAV_CREDIT_Y
sleep 2
shot "10-credit"

tap $NAV_BOOK_X $NAV_BOOK_Y
sleep 2
shot "11-carnet"

tap $NAV_PROF_X $NAV_PROF_Y
sleep 2
shot "12-profil"

# ------------------------------------------------------------------
# 13) Notifications (via cloche en haut depuis Home)
# ------------------------------------------------------------------
tap $NAV_HOME_X $NAV_HOME_Y
sleep 2
# La cloche est en haut à droite, autour de (660, 180)
tap 660 180
sleep 2
shot "13-notifications"
key_back

# ------------------------------------------------------------------
# 14) Historique épargne (depuis Home)
# ------------------------------------------------------------------
tap $NAV_HOME_X $NAV_HOME_Y
sleep 2
# Tap sur "Voir tout" ou icône historique — approx (660, 800)
tap 660 800
sleep 2
shot "14-historique-epargne"
key_back

echo "✓ Captures sauvegardées dans $OUT/"
ls -la "$OUT"
