# Corrections voies de crédit + formulaire mobile — 2026-07-22

Audit puis correction de 4 points remontés sur la demande de crédit (mobile +
backend). Aucune régression : **139 tests backend + 50 tests mobile verts**,
`flutter analyze` 0 issue.

---

## 1. Champs dupliqués « Votre parcours » → « Rattachement Broad Range Consulting »

**Constat** : ces sections s'affichaient **deux fois** dans le sheet de demande
de crédit — une fois codées en dur dans le Dart, une fois via le schéma
dynamique backend (`FormSchema` `loan_request`). La liste d'exclusion
`_hardcodedLoanFields` ne contenait pas les ids BRC → double rendu dès que la
prod servait le schéma.

> ⚠️ **Révision (2026-07-22, même jour)** : ces champs NE sont PAS inutiles —
> seul le **doublon** l'était. Ils doivent apparaître **une seule fois**, pour
> **TOUTES les voies**, à la soumission. On dé-duplique donc en gardant **la
> version dynamique (schéma)** et en retirant la version codée en dur.

**Correction** (dé-duplication, source unique = le schéma) :
- `backend/.../seed_form_schemas.py` — les 3 sections `profil_apprenant`
  (« Votre parcours de formation »), `profil_cga` (« Adhésion CGA »),
  `profil_brc` (« Rattachement BRC ») **restent** dans `LOAN_REQUEST_SCHEMA`
  (source unique, rendue par `DynamicFields` pour toutes les voies).
- `mobile/.../loan_request_sheet.dart` — le **bloc BRC codé en dur est supprimé**
  (état `_cgaBrcMember`/`_cfpBrcApprenant` + pickers + validation + payload), et
  les 8 ids **retirés** de `_hardcodedLoanFields` → `DynamicFields` les rend et
  `validateSchema` les valide, **une seule fois**.
- Les **pièces jointes** (preuves) remontent par le chemin générique : tout
  `PickedFile` de `_extraValues` part en upload (aucun câblage spécifique
  nécessaire — `DynamicFields` supporte `type: file`).

**Sûr** : le backend traite ces champs comme pièces **documentaires** (BRC) et
l'éligibilité `senior_brc` s'appuie sur `Member.is_brc_member` (modèle), pas sur
ces champs de formulaire.

## 2. Avaliste — étape « frais d'étude » invisible

**Constat** : côté **code**, la voie avaliste est déjà en « frais d'abord » : à
la soumission la demande naît en `EN_ATTENTE` (frais à payer), l'avaliste n'est
que mémorisé, puis sollicité **après** paiement des frais.

**À confirmer sur la prod** (2 causes possibles si l'étape n'apparaît pas) :
- **(a)** frais `DEMANDE_CREDIT` = `0` → un raccourci saute l'étape (mettre un
  montant > 0).
- **(b)** image backend prod antérieure au refactor « frais d'abord » → redéployer.

```bash
# Valeur du frais d'étude
docker compose -f infra/docker-compose.prod.yml exec backend python manage.py shell -c \
"from apps_coop.payments.models import FeeType; f=FeeType.objects.filter(code=FeeType.Code.DEMANDE_CREDIT).first(); print('montant', f.montant, 'actif', f.actif) if f else print('ABSENT')"

# Tag image backend déployée
docker compose -f infra/docker-compose.prod.yml images backend
```

> Séquence observée à re-vérifier après (a)/(b) : `EN_ATTENTE` → *(paiement
> frais)* → sollicitation avaliste (`EN_ATTENTE_AVALISTE`) → accepté →
> `EN_INSTRUCTION`.

## 3. Garantie — « Aucune voie d'éligibilité ne s'applique »

**Cause racine** : ce n'est PAS la logique garantie (`_eval_garantie_materielle`
accepte dès qu'un bien est déclaré + montant > 0). C'est un **kill-switch par
liste** : `evaluate_routes` rejette toute voie absente de
`loans.eligibility.route_priority`, et la valeur **seedée** était
`senior_brc,avaliste,campaign` → `garantie_materielle` absent → 403.

**Correction** :
- `seed_app_settings.py` — valeur passée à
  `senior_brc,avaliste,garantie_materielle,campaign` (aligne le seed sur le
  défaut codé, qui incluait déjà la garantie).

> Invisible en test (les tests n'ont pas la ligne AppSetting seedée → défaut codé
> appliqué). Bug uniquement sur une base **seedée** (= la prod).

## 4. Card « BRC » sur la page de demande

**Constat** : la card « BRC » du carrousel était en réalité la **voie par
défaut** `senior_brc` (auto-couverture épargne ou ancienneté). La supprimer
tuait la seule entrée de cette voie.

**Correction** (2 temps) :
1. D'abord renommée **« Classique »** (retrait du branding *Broad Range*).
2. Puis **carte retirée du carrousel** : elle faisait doublon avec le **FAB
   « + Nouvelle demande »**, qui ouvre déjà le formulaire **sans voie
   présélectionnée** = exactement la voie par défaut (auto-couverture /
   ancienneté). Le carrousel n'affiche plus que les 3 voies « spéciales »
   (avaliste, campagne, garantie). Le badge `senior_brc` reste **« Voie
   classique »** sur les demandes en cours. Enum interne `LoanRequestVoie.brc`
   conservé (non visible du membre).

---

## Règle métier de référence (posée le 2026-07-22)

> Toute demande de crédit passe par une **étude de dossier**, avec
> **éventuellement des frais d'étude**. Une **campagne** peut lever/annuler ces
> frais (`frais_etude_montant = 0`), mais par défaut c'est le **flow commun à
> tout le monde**.

Déjà implémenté via `status_after_prevoie` : toutes les voies franchissent la
**même porte frais** (`EN_ATTENTE` si frais > 0, sinon `EN_INSTRUCTION`).

| Voie | Frais d'étude | Statut après soumission | État |
|---|---|---|---|
| **Classique** (senior_brc) | oui | `EN_ATTENTE` → paie → `EN_INSTRUCTION` | ✅ conforme |
| **Avaliste** | oui (frais d'abord) | `EN_ATTENTE` → paie → sollicite avaliste | ✅ code OK, à confirmer prod |
| **Garantie** | oui | `EN_ATTENTE` → paie → `EN_INSTRUCTION` | ✅ débloqué par le fix |
| **Campagne** | oui, surchargeable (`0` = gratuit) | `EN_VALIDATION_CAMPAGNE` → validé → porte frais | ✅ conforme |

---

## Actions prod indispensables

`seed_app_settings` **n'écrase jamais** une valeur existante → forcer la mise à
jour de `route_priority` ; le schéma se republie avec `--force`.

```bash
# a) Débloquer la garantie (met à jour la valeur DÉJÀ en base)
docker compose -f infra/docker-compose.prod.yml exec backend python manage.py shell -c \
"from apps_coop.audit.models import AppSetting; AppSetting.objects.update_or_create(cle='loans.eligibility.route_priority', defaults={'valeur':'senior_brc,avaliste,garantie_materielle,campaign'}); print('OK', AppSetting.objects.get(cle='loans.eligibility.route_priority').valeur)"

# b) Publier le schéma AVEC les sections parcours/CGA/BRC (nouvelle version
#    active). Ces sections s'affichent pour TOUTES les voies à la soumission.
docker compose -f infra/docker-compose.prod.yml exec backend python manage.py seed_form_schemas --force --only loan_request
```

Puis **rebuild de l'APK release** pour que les corrections mobile (dédup +
libellé « Classique ») soient embarquées.

---

---

# Volet retrait d'épargne — 2 bugs corrigés

Tests verts : **57 backend + 13 mobile**, `flutter analyze` 0 issue.

## BUG 1 — Valider un retrait n'actualise pas l'état « en attente » (mobile)

**Cause** : `myWithdrawalsProvider` (`core/di/providers.dart:186`) est un
`FutureProvider.autoDispose` **jamais pollé**, et les 2 pages qui l'affichent ne
le rafraîchissaient pas :
- `home_page.dart` — les `LivePoller` (30 s) et le pull-to-refresh
  rafraîchissaient les soldes mais **pas** la liste des retraits.
- `states_page.dart` — l'`onRefresh` oubliait `myWithdrawalsProvider`.

Résultat : après approbation admin, le mobile ne re-fetch jamais
`/savings/withdrawals/me/` → le statut `en_attente` restait figé.
(`account_state_page.dart` invalidait bien les 3, lui.)

**Correction** (`FutureProvider` → `ref.invalidate` = re-fetch complet, pas de
dédup `toJson` en jeu) :
- `home_page.dart` — 3ᵉ `LivePoller` qui `invalidate(myWithdrawalsProvider)` +
  invalidation ajoutée au pull-to-refresh.
- `states_page.dart` — `invalidate(myWithdrawalsProvider)` ajouté à l'`onRefresh`.

## BUG 2 — Valider un retrait ne réduit pas le solde (épargne collecte)

**Rappel design** (`retrait-debit-au-paiement`, 2026-07-20) : le **solde brut**
n'est débité qu'au **paiement** ; à la validation, le montant est seulement
**réservé** → c'est le **disponible au retrait** qui doit baisser.

**Cause** : ça marchait pour le **classique** (`solde_disponible_retrait` =
solde − réservé, exposé par `ClassicSavingsAccountReadSerializer`), mais **pas
pour la collecte** : `SavingsAccountReadSerializer` n'exposait que `solde` brut,
sans champ net-du-réservé — alors que `reserved_withdrawals(account=...)`
existait déjà.

**Correction** :
- `backend/.../savings/serializers.py` — ajout de `solde_disponible_retrait`
  (= `solde − reserved_withdrawals(account=obj)`) au sérialiseur collecte.
- Propagation mobile **automatique** : le datasource lisait déjà
  `solde_disponible_retrait` s'il est présent ; `states_page` a déjà une ligne
  « disponible retrait » conditionnée à ce champ (elle s'allume maintenant).
- `withdraw_sheet.dart` — le plafond de retrait collecte passe de `solde` brut à
  `soldeRetirable` (disponible) → un membre ne peut plus re-demander un montant
  déjà réservé (parité avec le classique).

> ⚠️ **Point produit à confirmer** : le **hero d'accueil** affiche le `solde`
> **total** (classique ET collecte), qui — par la décision « débit au paiement »
> — ne bouge qu'au paiement. La réduction est donc visible sur le **disponible**
> (page états), pas sur le total du hero. Si tu veux que le hero reflète le
> disponible (baisse dès la validation), c'est un choix à acter (il changerait
> aussi l'affichage en présence de placement / gel garantie).

---

---

# Restitution de placement (apport) — intérêts + traçage capital

Tests verts : **46 backend** ciblés (dont non-régression). Migration
`savings/0019`.

## Constat
La restitution anticipée d'un placement prêteur (bouton admin →
`restitute_tranche_by_apport`) calculait les intérêts **au prorata des jours**
depuis `tranche.created_at`. En test (restitution peu après l'engagement),
`jours ≈ 0` → intérêt = 0 → aucune ligne créditée. De plus le **capital**
n'apparaissait nulle part (il vit déjà dans le solde, la tranche n'est qu'un
verrou → la restitution le déverrouille sans mouvement).

## Décisions (2026-07-22)
1. **Intérêt = taux FIXE** appliqué **au clic** : `intérêt = capital × taux`
   (`epargne.placement.interest_rate`, défaut **1 %**), plus de prorata jours.
2. **Tracer le capital** sur le relevé.

## Correction
- `loans/apport_services.py` — intérêt passe en taux fixe
  (`Decimal(tranche.montant) * rate`), calculé/crédité à la restitution.
- Nouveau `TypeOp.RESTITUTION_PLACEMENT` (`savings/models.py`) : ligne
  **informative** ajoutée au relevé (montant = capital), **`solde_apres`
  inchangé** (le capital était déjà dans le solde → pas de double comptage).
- `members/report_pdf.py` — `restitution_placement` classé « + » (positif).
- Mobile : **aucun changement** — dégrade gracieusement (le client lit `sens` +
  `type_display` de l'API ; type inconnu → catégorie crédit).

> ⚠️ **À savoir** : la ligne « Restitution capital » affiche `+capital` mais le
> **solde total ne saute pas** de ce montant (le capital y était déjà, il passe
> juste de « placement » à « libre/retirable »). Le libellé le précise. Seul
> l'**intérêt** augmente réellement le solde. Le **taux** est réglable via
> l'AppSetting `epargne.placement.interest_rate`.

---

## Parité portail web membre — FAIT (2026-07-22)

Audit de parité mobile↔portail → 3 écarts corrigés (`frontend/apps/portal`,
typecheck `tsc --noEmit` vert) :

1. **Doublon parcours/BRC** (`credit/demande/page.tsx`) — même bug que le mobile :
   bloc BRC codé en dur (cases + preuves + payload) **retiré** → `DynamicFields`
   rend les sections une seule fois. Les preuves remontent par le chemin
   générique `fileEntries` (champs `file` du schéma).
2. **Disponible collecte au retrait** (`epargne/retrait/page.tsx` + `api.ts`) —
   `solde_disponible_retrait` ajouté au type `SavingsSnapshot` et utilisé pour le
   « Disponible » collecte (fallback `solde`). Les dashboards gardent le **total**
   (cohérent avec le hero mobile).
3. **Ligne `restitution_placement`** (`epargne/historique/page.tsx` + `api.ts`) —
   cas ajouté (libellé « Restitution placement ») et **signe piloté par le `sens`
   backend** (corrige aussi le « − » erroné des autres crédits : intérêts,
   restitution maturité).

**Déjà OK sans changement** : la card « BRC » (le portail lit `voie_display`
backend) et la voie garantie (lit l'éligibilité backend + card présente).

## À vérifier ensuite

- **Admin** : relevé/back-office — affichage de la ligne `RESTITUTION_PLACEMENT`
  (si une vue admin liste les écritures épargne classique).
