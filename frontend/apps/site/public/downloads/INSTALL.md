# Downloads — APK mobile

Ce dossier est servi par Next.js sur `https://gathe-finance.horus-lab.com/downloads/`.

La page vitrine `/telecharger-app/` propose le bouton "Télécharger l'APK Android"
qui pointe vers `/downloads/gathe-finance.apk` (ce dossier).

## Mettre à jour l'APK en prod

Le fichier `gathe-finance.apk` n'est PAS commité (gitignored) car il pèse ~74 Mo.
Le déploiement Docker construit l'image vitrine sans le fichier — l'admin doit le
poser manuellement sur le VPS après chaque release.

### En local (test)

```bash
# Build l'APK release
cd mobile && flutter build apk --release

# Copie-le dans public/downloads/
cp build/app/outputs/flutter-apk/app-release.apk \
   ../frontend/apps/site/public/downloads/gathe-finance.apk

# npm run dev → accessible sur http://localhost:3000/downloads/gathe-finance.apk
```

### En prod (VPS Contabo)

1. Build l'APK release localement (voir ci-dessus).
2. SCP vers le VPS :

```bash
scp mobile/build/app/outputs/flutter-apk/app-release.apk \
    user@gathe-finance.horus-lab.com:/srv/gathe-finance/apk/gathe-finance.apk
```

3. Le `docker-compose.prod.yml` monte `/srv/gathe-finance/apk/` dans le container
   vitrine sur `/app/public/downloads/`. Le fichier est immédiatement servi sans
   redéploiement.

## Versionnage

Si tu veux servir plusieurs versions, nomme les fichiers :

```
gathe-finance.apk             # toujours la version courante (lien stable)
gathe-finance-v1.0.0.apk      # archive
gathe-finance-v1.1.0.apk      # archive
```

Et update `APK_VERSION` + `APK_SIZE` dans la page vitrine :
`app/[locale]/(marketing)/telecharger-app/page.tsx`.
