# Correction — échec SSH du déploiement cliente

## 🔄 Mise à jour — 2e tentative (progrès)

L'erreur a **évolué** entre les deux tentatives — c'est bon signe :

| Tentative | Message | Interprétation |
|---|---|---|
| 1ʳᵉ | `attempted methods [none]` | clé privée **inexploitable** (format/passphrase) |
| 2ᵉ | `attempted methods [none publickey]` | clé privée **valide** (elle est proposée) mais **refusée par le serveur** |

➡️ **Le format de la clé privée est corrigé.** Il reste **un seul problème** : la **clé publique correspondante n'est pas (bien) autorisée** sur le serveur.

### Cause du refus `publickey`
- la clé publique **n'est pas dans** `authorized_keys` de l'utilisateur ciblé, **ou**
- les **permissions** de `.ssh` sont trop ouvertes (sshd ignore alors le fichier), **ou**
- `CLIENT_VPS_USER` ne pointe pas sur le bon home.

### Correctif (serveur)
```bash
# 1) ajouter la clé PUBLIQUE correspondant à CLIENT_VPS_SSH_PRIVATE_KEY (ex. gathe_deploy.pub)
mkdir -p /home/gathe/.ssh
echo "<contenu de gathe_deploy.pub>" >> /home/gathe/.ssh/authorized_keys

# 2) permissions (CRUCIAL — sinon sshd ignore le fichier)
chown -R gathe:gathe /home/gathe/.ssh
chmod 700 /home/gathe/.ssh
chmod 600 /home/gathe/.ssh/authorized_keys
```

### Vérifier que privée et publique sont bien une PAIRE
```bash
ssh-keygen -y -f gathe_deploy    # doit afficher exactement le contenu de gathe_deploy.pub
```

### Test qui prouve que c'est réglé
```bash
ssh -i gathe_deploy gathe@169.58.69.78 'echo OK'    # doit afficher : OK
```
Dès que ce test affiche `OK`, relancer :
```bash
gh workflow run deploy.yml -f image_tag=main
```

---

## 🔴 Le problème

Le déploiement `deploy.yml` (cliente) a échoué à l'étape **« Upload infra/ vers le serveur cliente »** (envoi des fichiers par SSH) :

```
ssh: handshake failed: ssh: unable to authenticate, attempted methods [none], no supported methods remain
```

→ **GitHub Actions n'a pas pu s'authentifier en SSH** sur le serveur cliente.
Ce n'est **pas** lié à `.env.prod` ni aux réseaux DMZ — c'est purement la **clé SSH du déploiement**.

## 🧭 Signification

- `attempted methods [none]` = le runner **n'avait aucune clé exploitable** → il n'a même pas pu proposer de clé au serveur.
- Test depuis une autre machine → `Permission denied (publickey)` → **aucune clé n'est autorisée pour `gathe`** sur le serveur.

Les 4 secrets `CLIENT_VPS_*` sont bien présents. Le souci est donc **la paire de clés**, 2 causes possibles (souvent les deux) :

1. **`CLIENT_VPS_SSH_PRIVATE_KEY` malformée** dans GitHub — collée sans les lignes `-----BEGIN…-----` / `-----END…-----`, ou avec des `\n` au lieu de vrais retours à la ligne, ou une clé **protégée par passphrase** (interdit ici). Le `[none]` pointe fortement vers ça.
2. La **clé publique correspondante n'est pas** dans `/home/gathe/.ssh/authorized_keys` du serveur.

---

## ✅ Correction — paire de clés dédiée (propre)

### 1) Générer une paire dédiée SANS passphrase (sur ta machine)

```bash
ssh-keygen -t ed25519 -N "" -f gathe_deploy -C "gathe-ci-deploy"
# → produit : gathe_deploy (privée)  +  gathe_deploy.pub (publique)
```

### 2) Clé PUBLIQUE → sur le serveur cliente (utilisateur `gathe`)

```bash
mkdir -p /home/gathe/.ssh && chmod 700 /home/gathe/.ssh
echo "<contenu de gathe_deploy.pub>" >> /home/gathe/.ssh/authorized_keys
chmod 600 /home/gathe/.ssh/authorized_keys
chown -R gathe:gathe /home/gathe/.ssh
```

### 3) Clé PRIVÉE → dans GitHub

`Settings → Environments → production → Secrets → CLIENT_VPS_SSH_PRIVATE_KEY`

- Colle **tout le contenu** du fichier privé `gathe_deploy`, **y compris** :
  ```
  -----BEGIN OPENSSH PRIVATE KEY-----
  ...
  -----END OPENSSH PRIVATE KEY-----
  ```
  avec les **vrais retours à la ligne**. Remplace la valeur actuelle.

### 4) Vérifier les autres secrets

| Secret | Valeur |
|---|---|
| `CLIENT_VPS_USER` | `gathe` |
| `CLIENT_VPS_HOST` | `169.58.69.78` |
| `CLIENT_VPS_DEPLOY_PATH` | `/home/gathe/gathe-finance` |

### 5) Tester (depuis ta machine, avec la clé privée)

```bash
ssh -i gathe_deploy gathe@169.58.69.78 'echo OK'   # doit afficher : OK
```

Si `OK` s'affiche → la clé est bonne des deux côtés.

### 6) Relancer le déploiement

```bash
gh workflow run deploy.yml -f image_tag=main
```

---

## 🔎 Pièges fréquents

- **Passphrase** : la clé ne doit PAS en avoir (`-N ""` le garantit). Une clé avec passphrase → `attempted methods [none]`.
- **Copier-coller GitHub** : ne pas ajouter d'espaces/lignes vides ; garder BEGIN/END et les sauts de ligne.
- **Type de clé** : `ed25519` recommandé. Si le serveur est très ancien, `rsa` (`ssh-keygen -t rsa -b 4096 -N "" -f gathe_deploy`).
- **Permissions serveur** : `.ssh` en `700`, `authorized_keys` en `600`, propriété `gathe:gathe` — sinon sshd ignore le fichier.
- **Utilisateur** : le `CLIENT_VPS_USER` doit matcher le home où est `authorized_keys` (`gathe` → `/home/gathe/.ssh/`).

---

## Ordre global (rappel)

1. `.env.prod` rempli (réseaux DMZ + base + MinIO) — cf. `OBTENIR_VALEURS_DMZ.md` + `COMMANDES_MINIO_DOCKER.md`.
2. **Clé SSH du déploiement réglée** (ce document).
3. `docker login ghcr.io` fait sur le serveur (PAT `read:packages`).
4. Relance `gh workflow run deploy.yml -f image_tag=main` → vérif des endpoints.
