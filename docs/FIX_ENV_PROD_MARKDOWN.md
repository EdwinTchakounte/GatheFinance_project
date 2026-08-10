# Fix — `.env.prod` invalide (balises Markdown collées)

## ✅ Où on en est
Le mur SSH est franchi (« Upload infra/ → **success** »). Le déploiement échoue maintenant au `docker compose pull`, sur une vraie erreur simple :

```
failed to read /home/gathe/gathe-finance/infra/.env.prod:
line 1: unexpected character "`" in variable name "```dotenv"
```

## 🔴 Cause
En copiant le contenu depuis un bloc de code, les **balises Markdown** ont été collées dans le fichier :
- ` ```dotenv ` en haut (ligne 1)
- ` ``` ` en bas

Docker compose ne sait pas les lire → il s'arrête à la ligne 1.

---

## 🔧 Correction (sur le serveur)

```bash
cd /home/gathe/gathe-finance/infra

# 1) Constater (tu verras ```dotenv en ligne 1)
head -3 .env.prod

# 2) Retirer TOUTES les lignes de balises ``` (haut et bas)
sed -i '/^```/d' .env.prod

# 3) Vérifier : ligne 1 = vraie variable (ex. SITE_DOMAIN=...), pas de ``` en fin
head -3 .env.prod
tail -3 .env.prod
```

---

## 🔎 Vérifier que le fichier est entièrement propre

```bash
# chaque ligne doit être VAR=valeur, un commentaire #, ou vide
grep -nvE '^\s*($|#|[A-Za-z_][A-Za-z0-9_]*=)' .env.prod || echo "OK : .env.prod propre"
```
- Si la commande affiche des lignes → ce sont des restes à supprimer (autre texte Markdown, puces, etc.).
- Si elle affiche `OK : .env.prod propre` → parfait.

---

## 🩹 Variante si le `sed` ne suffit pas (autres restes Markdown)

```bash
# éditer à la main
nano .env.prod
# supprimer : ```dotenv, ```, lignes de titre, puces, etc.
# garder UNIQUEMENT les lignes VAR=valeur et les commentaires #
```

---

## 🔁 Si l'erreur revient sur une AUTRE ligne (ex. ligne 43)

Symptôme après un 1er nettoyage :
```
line 43: unexpected character "`" in variable name "```"
```
→ La balise du **haut** est partie, mais il **reste le ` ``` ` de fermeture en bas**. Le `sed` précédent n'a enlevé qu'une ligne. Solution : supprimer **toute** ligne contenant des backticks.

```bash
cd /home/gathe/gathe-finance/infra

# supprime TOUTE ligne contenant ```  (haut ET bas, même avec espaces)
sed -i '/```/d' .env.prod

# vérifier la fin + autour de la ligne signalée
tail -5 .env.prod
sed -n '40,45p' .env.prod
```

### Contrôle final (2 gardes)
```bash
grep -n '`' .env.prod && echo "⚠️ il reste des backticks ci-dessus" || echo "OK : plus aucun backtick"
grep -nvE '^\s*($|#|[A-Za-z_][A-Za-z0-9_]*=)' .env.prod || echo "OK : que des VAR=valeur / commentaires"
```
- 1re commande → **aucun backtick** ne doit rester.
- 2e commande → doit afficher `OK …` (sinon les lignes listées sont d'autres restes Markdown à retirer).

---

## ▶️ Ensuite

Dire **« nettoyé »** → relance :
```bash
gh workflow run deploy.yml -f image_tag=main
```

Le `pull` puis le `up` des 5 apps devraient passer. Prochaines erreurs possibles (si elles surviennent) :
- `pull access denied` → `docker login ghcr.io` pas fait (PAT `read:packages`).
- `network edge/data not found` → nom de réseau DMZ inexact dans `.env.prod` (cf. `OBTENIR_VALEURS_DMZ.md`).
- backend `unhealthy` → `DATABASE_URL` / base `gathe_prod` incorrecte.

---

## Rappel — état des blocages
| Étape | État |
|---|---|
| Clé SSH (`gathe`) | ✅ réglé |
| `CLIENT_VPS_USER=gathe` | ✅ réglé |
| Upload infra/ (scp) | ✅ passe |
| **`.env.prod` propre** | 🔧 ce document |
| `docker login ghcr.io` | à confirmer |
| réseaux DMZ corrects | à confirmer |
