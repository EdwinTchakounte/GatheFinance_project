# Résolution — clé SSH `gathe` pour le déploiement

## Le nœud du problème

Plusieurs clés ont été générées à des endroits différents → confusion :

| Clé | Emplacement | Autorisée pour | Utile ? |
|---|---|---|---|
| `gathe_ci_cd_deploy` | `/root/.ssh/` | **root** (ajoutée à root/authorized_keys) | ❌ non — mauvais user |
| **`gathe_ci_deploy`** | **`/home/gathe/.ssh/`** | **gathe** | ✅ **OUI — c'est LA bonne** |

**Preuve que `gathe_ci_deploy` fonctionne pour `gathe`** (test réussi) :
```bash
root@vmi3462967:# ssh -i /home/gathe/.ssh/gathe_ci_deploy gathe@127.0.0.1 'echo OK'
OK
```

Le déploiement échoue en `[none publickey]` parce que le **secret GitHub** `CLIENT_VPS_SSH_PRIVATE_KEY` contient **une autre clé** que `gathe_ci_deploy` → sa publique n'est pas dans l'`authorized_keys` de `gathe`.

---

## ✅ Le fix : mettre la clé qui marche dans le secret

La bonne clé privée = **`/home/gathe/.ssh/gathe_ci_deploy`**.

### Méthode fiable — écrire le secret depuis le fichier (zéro copier-coller)
À exécuter **en tant que root** (il peut lire le fichier de `gathe`) :
```bash
gh secret set CLIENT_VPS_SSH_PRIVATE_KEY \
  --env production \
  --repo EdwinTchakounte/GatheFinance_project \
  < /home/gathe/.ssh/gathe_ci_deploy
```
*(nécessite `gh` installé + `gh auth login` sur le serveur, en tant qu'EdwinTchakounte.)*

### Méthode alternative — afficher et coller dans l'UI GitHub
```bash
cat /home/gathe/.ssh/gathe_ci_deploy
```
→ copier **TOUT** (de `-----BEGIN OPENSSH PRIVATE KEY-----` à `-----END OPENSSH PRIVATE KEY-----`)
→ GitHub → **Settings → Environments → production → Secrets → `CLIENT_VPS_SSH_PRIVATE_KEY`** → remplacer la valeur.

---

## Vérifications

```bash
# 1) la paire est cohérente (publique dérivée == une ligne de authorized_keys)
ssh-keygen -y -f /home/gathe/.ssh/gathe_ci_deploy
cat /home/gathe/.ssh/authorized_keys      # doit contenir la ligne ci-dessus

# 2) permissions
ls -la /home/gathe/.ssh                    # .ssh=700, authorized_keys=600, owner gathe:gathe
```

Dans l'UI GitHub (env `production`), confirmer :

| Secret | Valeur |
|---|---|
| `CLIENT_VPS_USER` | `gathe` |
| `CLIENT_VPS_HOST` | `169.58.69.78` |
| `CLIENT_VPS_DEPLOY_PATH` | `/home/gathe/gathe-finance` |
| `CLIENT_VPS_SSH_PRIVATE_KEY` | = contenu de `/home/gathe/.ssh/gathe_ci_deploy` |

---

## (Optionnel) nettoyer la clé créée par erreur

```bash
# la clé gathe_ci_cd_deploy a été mise dans /root — inutile pour le déploiement gathe
rm -f /root/.ssh/gathe_ci_cd_deploy /root/.ssh/gathe_ci_cd_deploy.pub
# et retirer sa ligne de /root/.ssh/authorized_keys si tu veux (repère "github-actions-deploy")
```

---

## Ensuite

1. Secret `CLIENT_VPS_SSH_PRIVATE_KEY` = clé `gathe_ci_deploy` (méthode ci-dessus).
2. `CLIENT_VPS_USER = gathe`.
3. Dire « secret mis à jour » → relance :
   ```bash
   gh workflow run deploy.yml -f image_tag=main
   ```

Cette fois, le secret et l'`authorized_keys` de `gathe` sont **la même paire** → l'étape « Upload infra/ » passera.
