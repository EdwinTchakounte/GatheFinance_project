# Note de correction — SSH `attempted methods [none publickey]`

**Symptôme (déploiement `deploy.yml` cliente, étape « Upload infra/ ») :**
```
ssh: handshake failed: unable to authenticate, attempted methods [none publickey], no supported methods remain
```
**Signification :** la clé **privée** (secret GitHub) est valide et proposée, mais le **serveur refuse la clé publique** → la publique n'est pas (bien) autorisée pour l'utilisateur ciblé.

> ⚠️ Relancer `deploy.yml` ne corrige RIEN tant que le test final (§3) n'affiche pas `OK`.

---

## ✅ Procédure infaillible (à faire dans l'ordre)

```bash
# 1) Générer une paire fraîche, sans passphrase, dans ~/.ssh
ssh-keygen -t ed25519 -N "" -f ~/.ssh/gathe_deploy -C "gathe-ci-deploy"

# 2) Installer la clé PUBLIQUE sur le serveur (demande le mdp de gathe une fois)
ssh-copy-id -i ~/.ssh/gathe_deploy.pub gathe@169.58.69.78

# 3) TEST — doit afficher OK AVANT de continuer
ssh -i ~/.ssh/gathe_deploy gathe@169.58.69.78 'echo OK'

# 4) SEULEMENT si §3 = OK : copier la clé PRIVÉE dans le secret GitHub
cat ~/.ssh/gathe_deploy
#   -> Settings > Environments > production > Secrets > CLIENT_VPS_SSH_PRIVATE_KEY
#   (coller TOUT, de -----BEGIN----- à -----END-----)

# 5) Relancer le déploiement
gh workflow run deploy.yml -f image_tag=main
```

---

## 🔧 Les points à corriger (checklist)

| # | Point | Comment corriger / vérifier |
|---|---|---|
| 1 | **Paire non correspondante** (cause n°1) | `ssh-keygen -y -f ~/.ssh/gathe_deploy` doit être **identique** à la ligne dans `authorized_keys` du serveur. |
| 2 | **Clé au mauvais home / mauvais user** | `CLIENT_VPS_USER=gathe` → clé dans `/home/gathe/.ssh/authorized_keys`. Si `root` → `/root/.ssh/authorized_keys`. |
| 3 | **Permissions** (sshd ignore le fichier si trop ouvert) | `chmod 700 /home/gathe/.ssh` · `chmod 600 /home/gathe/.ssh/authorized_keys` · `chown -R gathe:gathe /home/gathe/.ssh` |
| 4 | **Clé publique cassée en plusieurs lignes** (copier-coller) | Elle doit être **UNE seule ligne** : `ssh-ed25519 AAAA... commentaire`. |
| 5 | **Clé privée malformée dans GitHub** | Coller le fichier privé ENTIER, avec `-----BEGIN...-----`/`-----END...-----` et vrais retours à la ligne. Pas de passphrase. |
| 6 | **Passphrase sur la clé** | Interdit ici (`-N ""` la garantit). Une passphrase → échec silencieux côté runner. |
| 7 | **`CLIENT_VPS_HOST` incorrect** | Doit être `169.58.69.78`. |
| 8 | **sshd interdit publickey ou le user** | `sudo grep -Ei "PubkeyAuthentication|AllowUsers|AuthorizedKeysFile" /etc/ssh/sshd_config` → `PubkeyAuthentication yes` ; si `AllowUsers` existe, `gathe` doit y figurer. Recharger : `sudo systemctl reload sshd`. |
| 9 | **SELinux** (RHEL/CentOS) | `restorecon -R -v /home/gathe/.ssh` (contexte des fichiers .ssh). |

---

## 🩺 Diagnostic express (à me coller — ce ne sont PAS des secrets)

```bash
# (A) la publique dérivée de la clé privée locale
ssh-keygen -y -f ~/.ssh/gathe_deploy

# (B) ce qui est réellement autorisé sur le serveur
ssh gathe@169.58.69.78 'cat ~/.ssh/authorized_keys'   # (ou via Broad Range)

# (C) permissions côté serveur
ssh gathe@169.58.69.78 'ls -la ~/.ssh'
```
Si **(A) ≠ (B)** → paire non correspondante (point 1). Si perms ≠ 700/600 → point 3.

---

## 💡 Cas DMZ (fréquent)

Si `gathe` n'a **pas de mot de passe** ou que l'auth mot de passe est **désactivée**, `ssh-copy-id` ne marchera pas → **c'est Broad Range** qui doit :
1. coller le contenu de `gathe_deploy.pub` dans `/home/gathe/.ssh/authorized_keys`,
2. appliquer les permissions (point 3),
3. te confirmer que `PubkeyAuthentication yes` (point 8).

---

## Ordre global rappelé
1. `.env.prod` rempli (réseaux DMZ + base + MinIO) — cf. `OBTENIR_VALEURS_DMZ.md`, `COMMANDES_MINIO_DOCKER.md`.
2. **Clé SSH réglée + test §3 = `OK`** (cette note).
3. `docker login ghcr.io` fait sur le serveur (PAT `read:packages`).
4. `gh workflow run deploy.yml -f image_tag=main` → vérification des endpoints.
