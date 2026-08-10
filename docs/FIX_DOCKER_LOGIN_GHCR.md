# Fix — `unauthorized` au pull des images (docker login GHCR)

## ✅ Où on en est
`.env.prod` propre (« Current tag: main »), le `pull` s'est réellement lancé. Nouvelle erreur :
```
Image ghcr.io/edwintchakounte/gathefinance_project/site:main
Error response from daemon: error from registry: unauthorized
```

## 🔴 Cause
Les images GHCR sont **privées** → il faut `docker login ghcr.io`.
Le déploiement se connecte en **`gathe`**, et les identifiants Docker sont **par utilisateur** (`~/.docker/config.json`).
Si `docker login` a été fait en `deploy` ou `root`, **`gathe` ne l'a pas** → `unauthorized`.

---

## 🔧 Correction — se logger à GHCR EN TANT QUE `gathe`

```bash
# 1) devenir gathe (l'utilisateur que le déploiement utilise)
sudo -u gathe -i          # ou : su - gathe
whoami                    # doit afficher : gathe

# 2) se connecter à GHCR (PAT avec scope read:packages)
echo "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" | docker login ghcr.io -u EdwinTchakounte --password-stdin
# -> attendu : Login Succeeded

# 3) vérifier que le pull marche maintenant, en gathe
docker pull ghcr.io/edwintchakounte/gathefinance_project/site:main
# -> doit télécharger sans "unauthorized"
```

- `<TON_PAT>` = PAT GitHub avec **`read:packages`** (réutilisable si celui du clone a ce scope).
- Le login écrit `/home/gathe/.docker/config.json` → c'est ce fichier que lit le déploiement.

---

## ⚠️ Si `docker` refuse pour `gathe` (permission denied sur docker.sock)

`gathe` n'est pas (encore) effectif dans le groupe `docker` :
```bash
exit                                  # revenir root/deploy
sudo usermod -aG docker gathe
# IMPORTANT : ouvrir une NOUVELLE session gathe pour que le groupe s'applique
sudo -u gathe -i
id gathe | grep -o docker             # doit contenir "docker"
# puis refaire le docker login (étape 2)
```

---

## 🔎 Vérifs utiles
```bash
# le fichier d'auth existe pour gathe ?
ls -l /home/gathe/.docker/config.json
# il contient bien ghcr.io ?
grep ghcr.io /home/gathe/.docker/config.json
```

---

## ▶️ Ensuite
Dire **« loggé »** → relance :
```bash
gh workflow run deploy.yml -f image_tag=main
```

---

## Rappel — progression des blocages
| Étape | État |
|---|---|
| Clé SSH (`gathe`) | ✅ |
| `CLIENT_VPS_USER=gathe` | ✅ |
| Upload infra/ (scp) | ✅ |
| `.env.prod` propre | ✅ |
| **`docker login ghcr.io` (gathe)** | 🔧 ce document |
| réseaux DMZ (`edge`/`data`) corrects | à confirmer au prochain run |
| backend `healthy` (DATABASE_URL) | à confirmer au prochain run |
