# Clé de déploiement `gathe` — de zéro (génération → autorisation → test)

Objectif : que **GitHub Actions** puisse se connecter en SSH au serveur cliente en tant qu'utilisateur **`gathe`**, pour déployer.

Principe : **1 paire de clés dédiée**
- la **publique** → dans `authorized_keys` de `gathe` (sur le serveur)
- la **privée** → dans le secret GitHub `CLIENT_VPS_SSH_PRIVATE_KEY`

On génère la paire **directement sur le serveur** (le plus simple, pas de transfert).

---

## 0. Se connecter au serveur et devenir `gathe`

```bash
ssh deploy@169.58.69.78          # ta connexion qui marche déjà
sudo -u gathe -i                 # devenir gathe  (ou : su - gathe)
whoami                           # doit afficher : gathe
```

---

## 1. Générer la paire de clés (en tant que `gathe`)

```bash
mkdir -p ~/.ssh && chmod 700 ~/.ssh
ssh-keygen -t ed25519 -N "" -f ~/.ssh/gathe_ci_cd_deploy -C "github-actions-deploy"
```
Produit :
- `~/.ssh/gathe_ci_deploy`      → clé **privée** (pour GitHub)
- `~/.ssh/gathe_ci_deploy.pub`  → clé **publique** (pour le serveur)

`-N ""` = **aucune passphrase** (obligatoire pour la CI).

---

## 2. Autoriser cette clé publique pour `gathe` (sur le serveur)

```bash
cat ~/.ssh/gathe_ci_cd_deploy.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
chmod 700 ~/.ssh
```
*(en tant que `gathe`, les fichiers appartiennent déjà à `gathe:gathe`.)*

---

## 3. Donner à `gathe` les droits nécessaires au déploiement

```bash
exit          # revenir à deploy/root (sudo)
sudo usermod -aG docker gathe                       # lancer Docker
sudo chown -R gathe:gathe /home/gathe/gathe-finance # posséder le repo
```
*(le groupe docker s'applique à la prochaine session `gathe`.)*

---

## 4. TEST — la clé fonctionne-t-elle pour `gathe` ?

Depuis le serveur (test en boucle locale) :
```bash
ssh -o StrictHostKeyChecking=no -i /home/gathe/.ssh/gathe_ci_deploy gathe@127.0.0.1 'echo OK'
```
→ doit afficher **`OK`**.
- `OK` = la paire + `authorized_keys` + permissions sont **correctes** → la CI passera.
- `Permission denied (publickey)` = revoir §2 (clé pas dans authorized_keys) ou permissions.

---

## 5. Copier la clé PRIVÉE dans le secret GitHub

```bash
cat /home/gathe/.ssh/gathe_ci_cd_deploy
```
Copie **TOUT** le contenu (de `-----BEGIN OPENSSH PRIVATE KEY-----` à `-----END OPENSSH PRIVATE KEY-----`) et colle-le dans :

**GitHub → Settings → Environments → `production` → Secrets → `CLIENT_VPS_SSH_PRIVATE_KEY`** (remplace la valeur actuelle).

---

## 6. Vérifier les 3 autres secrets (env `production`)

| Secret | Valeur |
|---|---|
| `CLIENT_VPS_USER` | `gathe` |
| `CLIENT_VPS_HOST` | `169.58.69.78` |
| `CLIENT_VPS_DEPLOY_PATH` | `/home/gathe/gathe-finance` |

---

## 7. Relancer le déploiement

Dis-moi « clé testée OK », je lance :
```bash
gh workflow run deploy.yml -f image_tag=main
```

---

## 8. Pièges à éviter (checklist)

- [ ] **Passphrase** : aucune (`-N ""`).
- [ ] Clé publique dans `authorized_keys` de **`gathe`** (pas `deploy`, pas `root`), sur **une seule ligne**.
- [ ] Permissions : `~/.ssh` = `700`, `authorized_keys` = `600`, propriétaire `gathe:gathe`.
- [ ] `CLIENT_VPS_USER` = `gathe` (correspond au home où est la clé).
- [ ] `CLIENT_VPS_SSH_PRIVATE_KEY` = clé privée **paire** de la publique (le `cat` du §5).
- [ ] `sshd` autorise le publickey : `sudo grep -Ei "PubkeyAuthentication|AllowUsers" /etc/ssh/sshd_config` → `yes` ; si `AllowUsers` existe, y ajouter `gathe` puis `sudo systemctl reload sshd`.
- [ ] (RHEL/CentOS) SELinux : `sudo restorecon -R -v /home/gathe/.ssh`.

---

## 9. Vérifier que privée et publique forment bien une paire

```bash
ssh-keygen -y -f /home/gathe/.ssh/gathe_ci_deploy    # doit == contenu de gathe_ci_deploy.pub
```

---

## Ordre global rappelé
1. `.env.prod` rempli (réseaux DMZ + base + MinIO).
2. **Clé `gathe` en place + test §4 = `OK`** (ce document).
3. `docker login ghcr.io` fait sur le serveur (PAT `read:packages`).
4. `gh workflow run deploy.yml -f image_tag=main` → vérification des endpoints.
