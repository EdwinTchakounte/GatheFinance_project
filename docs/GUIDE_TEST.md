# Guide de test — Gathé Finance

> Document de référence pour les sessions de test manuelles (web + mobile).
> Tous les comptes ci-dessous sont **uniquement valables en environnement local
> ou de recette** (configuration `dev.py`). À ne **jamais** porter en production.

---

## 1. Comptes de test pré-seedés

Mot de passe partagé : **`test1234`**

### 1.1 Comptes staff (admin Next.js + Django admin)

| Login | Rôle | Permissions principales |
|---|---|---|
| `admin@gathe.test` | Superuser | Voit tout, peut tout (config, KPIs, décisions) |
| `comite@gathe.test` | Comité crédit | Décide les demandes de crédit |
| `staff@gathe.test` | Lecture | Consulte les KPIs et listes, ne décide pas |

### 1.2 Membres (portail + mobile)

| Login | Statut | Données pré-câblées |
|---|---|---|
| `jean.kamga@test.local` | Actif | 5 dépôts d'épargne · solde **65 000 XAF** · n° `GF-2026-0001` |
| `marie.tankam@test.local` | Actif | 2 dépôts épargne + **crédit 500 000 XAF en cours** (12 échéances) · n° `GF-2026-0002` |
| `paul.suspendu@test.local` | Suspendu | Doit régler sa 1re cotisation pour devenir actif · n° `GF-2026-0003` |

### 1.3 Demandes d'adhésion en attente (à approuver depuis l'admin)

| Demandeur | Email | Ville |
|---|---|---|
| Aline Tchamba | `aline.tchamba@test.local` | Yaoundé |
| Bertrand Nguemo | `bertrand.nguemo@test.local` | Bafoussam |

### 1.4 Réinitialiser / rejouer le seed

```bash
docker compose exec backend python manage.py seed_test_accounts
```

> La commande est **idempotente** : elle remet à zéro les soldes/dépôts et
> reset les mots de passe. Aucun risque de duplication.

---

## 2. URLs d'accès

### 2.1 Depuis le poste (machine locale)

| Service | URL | Login attendu |
|---|---|---|
| Vitrine publique | <http://localhost:3200> | — |
| Portail membre | <http://localhost:3201> | Membres |
| Admin (Next.js) | <http://localhost:3202> | Staff |
| Django admin | <http://localhost:8200/admin/> | Staff |
| API v1 | <http://localhost:8200/api/v1/> | — |
| OpenAPI / Swagger | <http://localhost:8200/api/schema/swagger-ui/> | — |

### 2.2 Depuis un téléphone connecté au même wifi

L'IP du poste sur le wifi est **`10.133.4.210`** (ifconfig peut le confirmer).
Le backend dev autorise les origines `10.x.x.x`, `192.168.x.x` et `172.16-31.x.x`
sur les ports 3200-3299, donc rien de plus à configurer.

| Service | URL téléphone | Notes |
|---|---|---|
| Vitrine publique | <http://10.133.4.210:3200> | Lecture seule |
| Portail membre | <http://10.133.4.210:3201> | Tester depuis le navigateur du tel |
| Admin (Next.js) | <http://10.133.4.210:3202> | Login staff |
| Backend API | <http://10.133.4.210:8200/api/v1/> | Pour l'app mobile native |

> ⚠️ Si l'IP du poste change (wifi public, redémarrage), un simple `ip a` ou
> `ifconfig` redonne la valeur ; rien à modifier côté backend.

---

## 3. App mobile Flutter

### 3.1 Lancement sur émulateur Android

```bash
cd mobile
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8200
```

`10.0.2.2` est l'alias de l'émulateur Android qui pointe vers l'hôte.

### 3.2 Lancement sur device physique connecté au même wifi

```bash
cd mobile
flutter run --dart-define=API_BASE_URL=http://10.133.4.210:8200
```

### 3.3 Mode mocks (zéro backend requis)

```bash
flutter run --dart-define=USE_MOCKS=true
```

### 3.4 Identifiants à saisir dans l'app

Utilise n'importe quel compte **membre** (section 1.2). L'admin et le comité ne
peuvent pas se loguer sur le mobile (il faut une fiche Member rattachée).

### 3.5 Tests automatiques sans paiement réel

Pour valider l'ensemble des flows métier (épargne, crédit, retrait) sans
dépendre du provider Tara, active le flag :

```bash
docker compose exec backend bash -c \
  "PAYMENTS_TEST_AUTO_VALIDATE=true python manage.py runserver 0.0.0.0:8000"
```

Ou ajoute `PAYMENTS_TEST_AUTO_VALIDATE=true` dans `.env`. Chaque
`POST /payments/init/` est alors **immédiatement validé** comme si Tara
avait répondu OK — les hooks métier se déclenchent normalement.

---

## 4. Scénarios de test recommandés

### 4.1 Parcours membre simple (Jean Kamga)

1. Connexion portail (`http://10.133.4.210:3201`) en tant que `jean.kamga@test.local`
2. Vérifier le **solde 65 000 XAF** et les 5 transactions historiques
3. Verser une cotisation via le bouton "Verser ma cotisation"
4. Aller dans `/notifications` (nouveau onglet) — la notif "dépôt validé" doit apparaître

### 4.2 Parcours crédit en cours (Marie Tankam)

1. Connexion portail en tant que `marie.tankam@test.local`
2. Onglet Crédit → voir le crédit `500 000 XAF` actif avec 12 échéances
3. Tester un remboursement d'échéance (avec `PAYMENTS_TEST_AUTO_VALIDATE=true`)
4. L'échéance bascule en "Payée" et le solde restant diminue

### 4.3 Activation d'un membre suspendu (Paul Mbida)

1. Connexion portail en tant que `paul.suspendu@test.local`
2. CTA "Activer mon compte" → frais d'adhésion 10 000 XAF
3. Payer (en mode auto-validate) → le statut bascule en "actif"

### 4.4 Approbation d'une demande (côté staff)

1. Admin (`http://10.133.4.210:3202`) en tant que `admin@gathe.test`
2. Section "Adhésions" → 2 demandes en attente (Aline, Bertrand)
3. Cliquer "Approuver" → un compte Member est créé en statut "suspendu"
4. Email welcome envoyé (visible dans la console backend en dev)

### 4.5 Décision d'un crédit (comité)

1. Connexion admin en tant que `comite@gathe.test`
2. Soumettre une demande de crédit depuis le portail (avec Jean)
3. Côté comité : accepter/refuser → décaissement Tara (auto-validate si flag actif)

### 4.6 Annonce broadcast admin → membres

1. Admin → `/announcements` → créer une annonce audience "Tous"
2. Connexion portail en tant que Jean ou Marie → onglet Notifications
3. L'annonce apparaît avec icône "Annonce" + corps complet
4. Idem côté mobile (onglet notifications)

---

## 5. Captures pour la documentation

### 5.1 Captures web — script Playwright automatique

```bash
node scripts/capture-web.mjs
```

Le script :
- Lance Playwright en mode headless
- Login staff + membre
- Capture les pages clés (dashboard admin, portail home, notifications, crédits, etc.)
- Sortie : `docs/captures/web/`

### 5.2 Captures mobile

Sur device physique : maintenir `Power + Volume Down` (Android) ou
`Power + Home` (iOS). Les images se retrouvent dans la galerie.

Sur émulateur Android : `adb exec-out screencap -p > capture.png` ou
le bouton appareil photo dans la sidebar de l'émulateur.

> Pour des captures mobiles automatisées et reproductibles, on peut ajouter un
> test Flutter integration qui exporte des PNG via
> `binding.takeScreenshot()`. À voir si besoin.

---

## 6. Liens utiles backend

| Action | Commande |
|---|---|
| Redémarrer le backend | `docker compose restart backend` |
| Voir les logs | `docker compose logs -f backend` |
| Shell Django | `docker compose exec backend python manage.py shell` |
| Migrations | `docker compose exec backend python manage.py migrate` |
| Re-seed les test accounts | `docker compose exec backend python manage.py seed_test_accounts` |
| Re-seed la demo dashboard | `docker compose exec backend python manage.py seed_demo_dashboard` |
