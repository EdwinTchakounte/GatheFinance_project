# Téléchargement APK — hébergement Google Drive

L'APK Android est **hébergé sur Google Drive**, plus servi par la vitrine.

- File ID Drive : `1CqqRehipMPZOwk28oZ9q2DYJtgSqVlPQ`
- URL share (preview) : https://drive.google.com/file/d/1CqqRehipMPZOwk28oZ9q2DYJtgSqVlPQ/view?usp=sharing
- URL direct download : https://drive.google.com/uc?export=download&id=1CqqRehipMPZOwk28oZ9q2DYJtgSqVlPQ

Le bouton "Télécharger l'APK Android" sur `/fr/telecharger-app` pointe vers
l'URL direct download. Le QR code encode l'URL share (meilleure UX mobile :
ouvre l'app Drive native qui propose un bouton Télécharger).

## Mettre à jour l'APK

1. Build l'APK release :
   ```bash
   cd mobile && flutter build apk --release
   ```
2. Upload `mobile/build/app/outputs/flutter-apk/app-release.apk` sur Drive en
   **remplaçant** le fichier existant (clic droit → Gérer les versions →
   Importer une nouvelle version). Le file ID reste inchangé.
3. Si nouveau file ID nécessaire (suppression + upload), update la constante
   `APK_DRIVE_FILE_ID` dans
   `app/[locale]/(marketing)/telecharger-app/page.tsx` puis déployer.

## Permissions Drive

Le fichier doit être en partage **"Tous les utilisateurs avec le lien"**
(rôle Lecteur). Sinon le téléchargement renvoie une 401/403.

## Pourquoi Drive plutôt que self-hosted ?

- APK = 74 Mo. Évite de gonfler le container Docker ou un volume VPS.
- Pas de SCP nécessaire pour chaque release — l'upload Drive suffit.
- Drive gère le bandwidth gratuitement.

Le dossier `public/downloads/` est conservé pour `.gitkeep`. Le volume Docker
`${GATHE_APK_DIR}:/app/public/downloads:ro` a été retiré du compose prod. Pour
revenir en self-hosted, restaurer le volume et héberger l'APK dans
`/srv/gathe-finance/apk/`.
