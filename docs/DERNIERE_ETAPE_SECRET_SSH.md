# Dernière étape — mettre la bonne clé privée dans le secret GitHub

## État : la clé est BONNE, il ne manque qu'une chose

La sortie serveur l'a **confirmé** :
```bash
ssh-keygen -y -f /home/gathe/.ssh/gathe_ci_deploy
# -> ssh-ed25519 AAAA...pIRT github-actions-deploy

cat /home/gathe/.ssh/authorized_keys
# -> contient EXACTEMENT cette ligne  ✅
```
→ `gathe_ci_deploy` est **la bonne paire** pour `gathe` (test `echo OK` déjà réussi).

**Seul reste :** le secret GitHub `CLIENT_VPS_SSH_PRIVATE_KEY` doit contenir la **clé privée** `gathe_ci_deploy`.
(Le `gh secret set` a échoué uniquement parce que `gh` n'est pas connecté sur le serveur.)

---

## ✅ Méthode 1 — une seule commande (réutilise ton PAT, zéro copier-coller)

Sur le serveur, en tant que `gathe` :
```bash
GH_TOKEN=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 gh secret set CLIENT_VPS_SSH_PRIVATE_KEY \
  --env production \
  --repo EdwinTchakounte/GatheFinance_project \
  < /home/gathe/.ssh/gathe_ci_deploy
```

> ⚠️ Le PAT doit avoir le scope **`repo`** (écriture des secrets).
> Le PAT de `docker login` n'avait que `read:packages` → si c'est le cas, crée-en un avec `repo`,
> ou utilise la Méthode 2.

---

## 🪧 Méthode 2 — copier-coller dans l'UI (une dernière fois)

```bash
cat /home/gathe/.ssh/gathe_ci_deploy
```
→ sélectionner **TOUT** (de `-----BEGIN OPENSSH PRIVATE KEY-----` à `-----END OPENSSH PRIVATE KEY-----`)
→ GitHub → **Settings → Environments → production → Secrets → `CLIENT_VPS_SSH_PRIVATE_KEY`** → **Update secret**.

---

## Vérifier (UI, env production)

| Secret | Valeur |
|---|---|
| `CLIENT_VPS_USER` | `gathe` |
| `CLIENT_VPS_HOST` | `169.58.69.78` |
| `CLIENT_VPS_DEPLOY_PATH` | `/home/gathe/gathe-finance` |
| `CLIENT_VPS_SSH_PRIVATE_KEY` | = contenu de `/home/gathe/.ssh/gathe_ci_deploy` |

---

## Ensuite

Dire **« ok »** → relance :
```bash
gh workflow run deploy.yml -f image_tag=main
```
La paire secret ↔ `authorized_keys` de `gathe` étant identique, l'étape « Upload infra/ » passera.

---

## (Optionnel) nettoyer la clé créée par erreur dans /root
```bash
rm -f /root/.ssh/gathe_ci_cd_deploy /root/.ssh/gathe_ci_cd_deploy.pub
# retirer aussi sa ligne "github-actions-deploy" de /root/.ssh/authorized_keys si souhaité
```
