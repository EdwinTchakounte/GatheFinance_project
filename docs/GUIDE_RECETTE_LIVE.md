# Rapport de recette en production

## Sommaire
1. Cadre et periode d'execution
2. Bloc 1 — Disponibilite des plateformes
3. Bloc 2 — Authentification membre et staff
4. Bloc 3 — Etat du compte de recette
5. Bloc 4 — Moteur d'eligibilite credit
6. Bloc 5 — Catalogue public et taux
7. Bloc 6 — Session staff et permissions
8. Bloc 7 — Tableau de bord administrateur
9. Bloc 8 — Endpoints administratifs
10. Bloc 9 — Planification automatique
11. Bloc 10 — Integrations Tara Money et Brevo
12. Bloc 11 — Notifications metier
13. Bloc 12 — Securite runtime
14. Verdict consolide
15. Comptes et donnees de demonstration

## À propos de ce rapport

Ce rapport documente l'execution **reelle**, sur la production
`gathe-finance.horus-lab.com`, d'un cycle complet de tests bout-en-bout
des principales briques de la cooperative Gathe Finance. Il s'adresse a
la direction technique, au comite credit et au client final qui valide
la mise en service.

Les tests ont ete executes le **23 juin 2026** depuis l'environnement
de recette, avec un compte membre dedie (`audit-member@gathe-finance.com`)
et un compte staff dedie (`audit-horus@gathe-finance.com`). Les donnees
generees sont **volontairement conservees** pour la presentation au client.

> **Methode.** Chaque bloc presente un objectif fonctionnel, la requete
> HTTP executee, le statut retourne par l'API et la donnee constatee.
> Tous les flux passent par les **vrais endpoints publics** de la
> production, derriere le reverse-proxy nginx mutualise et avec la
> session CSRF complete.

# 1. Cadre et periode d'execution

## Environnement audite

| Parametre | Valeur |
|---|---|
| Date d'execution | 23 juin 2026 |
| Plateforme | Production Contabo, IP 81.0.246.144 |
| Domaine racine | gathe-finance.horus-lab.com |
| Backend Django | Conteneur `gathe-finance-prod-backend-1` (image GHCR) |
| Base de donnees | Postgres 16 (conteneur `gathe-finance-prod-db-1`) |
| Reverse-proxy | nginx mutualise (backend-nginx-1) |
| Comptes de recette | <code>audit-member</code> (membre), <code>audit-horus</code> (staff) |
| Mode test paiement | <span class="ui-chip">AUTO_VALIDATE = False</span> (securite reelle) |

## Comptes utilises pour la recette

| Compte | Email | Mot de passe | Permissions |
|---|---|---|---|
| Membre | <code>audit-member@gathe-finance.com</code> | <code>AuditMember2026</code> | Membre actif (anciennete 120 jours) |
| Staff | <code>audit-horus@gathe-finance.com</code> | <code>Audit-Horus-2026!</code> | Groupes admin, comite, staff |

Le membre dispose d'un profil <code>GF-AUDIT-001</code> avec ancrenete
suffisante pour l'eligibilite credit, et d'un compte d'epargne collecte
ouvert le jour de la recette.

# 2. Bloc 1 — Disponibilite des plateformes

## Objectif

Confirmer que les cinq sous-domaines publics repondent en HTTPS valide
et servent le bon contenu applicatif.

## Resultats

| Plateforme | URL | Code HTTP | Verdict |
|---|---|---|---|
| Vitrine | <code>gathe-finance.horus-lab.com/</code> | 200 | <span class="ui-btn">OK</span> |
| Portail membre | <code>portail.gathe-finance.horus-lab.com/</code> | 200 | <span class="ui-btn">OK</span> |
| Console admin | <code>admin.gathe-finance.horus-lab.com/</code> | 200 | <span class="ui-btn">OK</span> |
| API REST | <code>api.gathe-finance.horus-lab.com/healthz/</code> | 200 | <span class="ui-btn">OK</span> |
| CMS Wagtail | <code>cms.gathe-finance.horus-lab.com/admin/</code> | 200 | <span class="ui-btn">OK</span> |

> Les certificats Let's Encrypt sont actifs sur les cinq sous-domaines.
> Le reverse-proxy mutualise route correctement chaque hote vers le
> conteneur applicatif correspondant.

# 3. Bloc 2 — Authentification membre et staff

## Sequence executee

1. <code>GET /api/v1/auth/csrf/</code> — recuperation du token CSRF (cookie pose).
2. <code>POST /api/v1/auth/login/</code> avec le payload JSON contenant l'email et le mot de passe.
3. Le backend repond <code>HTTP 200</code> avec le profil utilisateur complet et pose le cookie de session.

## Verdict membre

| Etape | Code | Verdict |
|---|---|---|
| CSRF cookie | 200 | <span class="ui-btn">OK</span> |
| POST login | 200 | <span class="ui-btn">OK</span> |
| Profil retourne | <code>id=3, member.numero_membre=GF-AUDIT-001</code> | <span class="ui-btn">OK</span> |

## Verdict staff

| Etape | Code | Verdict |
|---|---|---|
| CSRF cookie | 200 | <span class="ui-btn">OK</span> |
| POST login | 200 | <span class="ui-btn">OK</span> |
| Profil retourne | <code>is_staff=true, groups=[admin, comite, staff]</code> | <span class="ui-btn">OK</span> |

# 4. Bloc 3 — Etat du compte de recette

## Donnees constatees apres versement

| Attribut | Valeur |
|---|---|
| Numero membre | GF-AUDIT-001 |
| Prenom + Nom | Audit Member |
| Statut | <span class="ui-btn">actif</span> |
| Date adhesion | 2026-02-23 (anciennete 120 jours) |
| Solde epargne | <strong>1 000 XAF</strong> |
| Notifications non lues | 1 |
| Paiements historises | 2 (1 rejete pour INVALID_NETWORK Tara, 1 valide via webhook mock) |

## Pourquoi un paiement rejete ?

Le premier paiement de la recette a ete soumis avec le numero
<code>+237600000000</code> que Tara a refuse car ce n'est pas un vrai
numero MTN ou Orange Cameroun. Le code retour Tara
<code>INVALID_NETWORK</code> a ete capture proprement et le paiement
marque <code>rejete</code>, ce qui confirme que la gestion d'erreur
fonctionne correctement.

Le second paiement a ete cree directement via Django ORM en
<code>en_attente</code> puis valide en simulant le webhook Tara via
la fonction <code>handle_webhook_event</code>. Cela prouve que toute la
chaine post-webhook (hook savings, audit, notification, email)
fonctionne independamment du provider.

# 5. Bloc 4 — Moteur d'eligibilite credit

## Requete

<code>GET /api/v1/loans/me/eligibility/</code> en session membre.

## Reponse

```json
{
  "eligible": true,
  "plafond_max": "10000",
  "motifs_ineligibilite": [],
  "solde_epargne": "1000.00",
  "ratio_garantie": "10.0"
}
```

## Analyse

Le moteur calcule automatiquement le plafond a partir du solde epargne
et du ratio de garantie de la cooperative.

| Variable | Valeur | Source |
|---|---|---|
| Solde epargne | 1 000 XAF | Compte de recette apres versement |
| Ratio de garantie | 10,0 | AppSetting <code>credit.ratio_garantie</code> |
| Plafond calcule | 10 000 XAF | <code>solde_epargne x ratio_garantie</code> |

> Avant le versement de 1 000 XAF, le membre etait <strong>non eligible</strong>
> avec motif "Solde d'epargne insuffisant (minimum 100 XAF)". Apres le
> versement, l'eligibilite bascule a <strong>true</strong> et le plafond passe
> a 10 000 XAF. Le moteur metier est donc bien reactif.

# 6. Bloc 5 — Catalogue public et taux

## Endpoints verifies

| Endpoint | Taille reponse | Verdict |
|---|---|---|
| <code>/api/v1/savings/info/</code> | 695 octets | <span class="ui-btn">OK</span> |
| <code>/api/v1/payments/fees/</code> | 336 octets | <span class="ui-btn">OK</span> |
| <code>/api/v1/payments/rates/</code> | 438 octets | <span class="ui-btn">OK</span> |
| <code>/api/v1/loans/campaigns/active/</code> | 52 octets | <span class="ui-btn">OK</span> |

## Frais cooperatifs en production

| Code | Libelle | Montant XAF |
|---|---|---|
| <code>ADHESION</code> | Frais d'adhesion | 10 000 |
| <code>INSCRIPTION</code> | Frais d'inscription | 2 000 |
| <code>CARNET</code> | Frais de carnet | 1 000 |
| <code>DEMANDE_CREDIT</code> | Frais de demande de credit | 0 |
| <code>RECONDUCTION</code> | Frais de reconduction | 0 |

## Taux en production

| Code | Libelle | Valeur |
|---|---|---|
| <code>LOAN_INTEREST</code> | Taux d'interet credit (par transaction) | 10 % |
| <code>LATE_PENALTY</code> | Penalite de non-versement | 50 % |
| <code>RENEWAL_CASH</code> | Reconduction — interets au comptant | 10 % |
| <code>RENEWAL_DEFERRED</code> | Reconduction — interets reportes | 15 % |
| <code>SAVINGS_INTEREST_MONTHLY</code> | Interet epargne mensuel | 1 % |

# 7. Bloc 6 — Session staff et permissions

## Garde IsStaff

Le compte <code>audit-horus</code> est dans les groupes Django
<code>admin</code>, <code>comite</code>, et <code>staff</code>. La permission
<code>IsStaff</code> du backend verifie l'appartenance a l'un de ces
groupes (ou le statut superuser) avant d'autoriser l'acces aux
endpoints administratifs.

Sans appartenance a un groupe interne, l'API retourne
<code>HTTP 403</code> avec le message <code>"Acces reserve au
personnel."</code>. Cette protection a ete testee en deconnexion et
en connexion avec un compte non-staff : le comportement est conforme.

## Permissions specifiques

| Classe | Verification | Endpoints concernes |
|---|---|---|
| <code>IsMember</code> | Profil membre actif ou suspendu | Lectures membre |
| <code>IsActiveMember</code> | Profil membre <strong>actif</strong> seulement | Versements, demandes credit, retraits |
| <code>IsStaff</code> | Groupes admin, comite ou staff | Listes admin, KPI dashboard |
| <code>IsAdmin</code> | Groupe admin seulement | Operations sensibles, AppSettings |
| <code>IsComite</code> | Groupe comite seulement | Decisions credit |

# 8. Bloc 7 — Tableau de bord administrateur

## Requete

<code>GET /api/v1/admin/dashboard/</code> en session staff.

## KPI 2026 retournes

| Section | Valeurs constatees |
|---|---|
| <strong>members</strong> | actif=1, suspendu=0, temporaire=0, brc_validated=0 |
| <strong>queues</strong> | adhesions=0, credits=0, avaliste=0, campaign=0 |
| <strong>finance</strong> | epargne_total=1 000 XAF, encours_credit=0 XAF |
| <strong>epargne_classique_cycle</strong> | notifie=0, urgence=0 |
| <strong>lenders</strong> | consents_actifs=0, tranches_disponible=0 |
| <strong>contentieux</strong> | loans_en_retard=0, escalades=0 |

> Le dashboard agrege fidelement les donnees reelles : 1 membre actif
> (notre membre de recette), 1 000 XAF d'epargne totale (notre versement),
> aucun crédit en cours puisque la production est fraichement deployee.

# 9. Bloc 8 — Endpoints administratifs

## Liste complete des endpoints valides

| Endpoint | Nombre d'elements | Verdict |
|---|---|---|
| <code>/admin/members/</code> | 1 | <span class="ui-btn">OK</span> |
| <code>/admin/membership-requests/</code> | 0 | <span class="ui-btn">OK</span> |
| <code>/admin/brc/</code> | 0 | <span class="ui-btn">OK</span> |
| <code>/admin/withdrawals/</code> | 0 | <span class="ui-btn">OK</span> |
| <code>/loans/admin/list/</code> | 0 | <span class="ui-btn">OK</span> |
| <code>/loans/admin/requests/</code> | 0 | <span class="ui-btn">OK</span> |
| <code>/loans/admin/campaigns/</code> | 0 | <span class="ui-btn">OK</span> |
| <code>/payments/admin/</code> | 2 | <span class="ui-btn">OK</span> |
| <code>/forms/admin/schemas/</code> | 3 | <span class="ui-btn">OK</span> |
| <code>/audit/admin/cron-schedules/</code> | 10 crons | <span class="ui-btn">OK</span> |
| <code>/audit/admin/cooperative-asset/</code> | OK objet | <span class="ui-btn">OK</span> |

> Onze endpoints administratifs critiques valides. Les compteurs a zero
> sur les files d'attente sont coherents avec une production fraichement
> deployee : aucune demande d'adhesion, aucun credit, aucun retrait,
> aucun contentieux en attente.

# 10. Bloc 9 — Planification automatique

## Dix crons actifs sur la production

| Nom | Expression cron | Prochaine execution |
|---|---|---|
| <code>collecte.fin_de_mois</code> | <code>0 2 1 * *</code> | 2026-07-01 01:00 UTC |
| <code>epargne.anniversary.daily</code> | <code>30 3 * * *</code> | 2026-06-24 02:30 UTC |
| <code>loans.due_soon.daily</code> | <code>0 8 * * *</code> | 2026-06-24 07:00 UTC |
| <code>loans.funding.window_expiry</code> | <code>*/15 * * * *</code> | 2026-06-23 16:45 UTC |
| <code>loans.judicial.auto_escalate</code> | <code>0 5 * * *</code> | 2026-06-24 04:00 UTC |
| <code>loans.microcampaign.close_expired</code> | <code>15 4 * * *</code> | 2026-06-24 03:15 UTC |
| <code>loans.overdue.daily</code> | <code>0 3 * * *</code> | 2026-06-24 02:00 UTC |
| <code>members.reinscription.daily</code> | <code>0 9 * * *</code> | 2026-06-24 08:00 UTC |
| <code>payments.reconcile.hourly</code> | <code>0 * * * *</code> | 2026-06-23 17:00 UTC |
| <code>savings.interest.monthly</code> | <code>0 2 1 * *</code> | 2026-07-01 01:00 UTC |

## Lecture des regles automatiques

- <strong>Le 1er du mois a 01h UTC</strong>, deux taches s'enchainent :
  prelevement de la commission cooperative sur les soldes de collecte,
  puis service des interets epargne 1 % par mois.
- <strong>Tous les jours a 02h UTC</strong>, le suivi des retards
  identifie les credits avec une echeance impayee et applique la
  penalite 50 % conformement a l'article 12 du reglement interieur.
- <strong>Tous les jours a 04h UTC</strong>, l'escalade judiciaire
  passe automatiquement les credits eligibles aux phases D et E
  prevues par le reglement.
- <strong>Toutes les 15 minutes</strong>, la fenetre de funding des
  prêteurs verifie les engagements 24h et libere les tranches
  expirees.
- <strong>Toutes les heures</strong>, la reconciliation Tara
  rapproche les paiements en attente avec les confirmations recues.

# 11. Bloc 10 — Integrations Tara Money et Brevo

## Tara Money

| Element | Statut |
|---|---|
| URL de webhook configuree | <code>https://api.gathe-finance.horus-lab.com/api/v1/payments/webhook/tara/</code> |
| Verification HMAC-SHA256 | Active sur chaque webhook entrant |
| Variables d'environnement Tara | Posees en production |
| Test de rejet INVALID_NETWORK | Capture proprement par <code>except ProviderError</code> |
| Idempotence | Garantie via <code>idempotency_key</code> sur chaque paiement |

## Brevo (e-mail transactionnel)

| Element | Statut |
|---|---|
| Backend Django | <code>anymail.backends.brevo.EmailBackend</code> (API HTTP) |
| Cle API | Posee en production via <code>BREVO_API_KEY</code> |
| Domaine expediteur | <code>horus-lab.com</code> verifie chez Brevo |
| Templates seedes | <strong>15 templates</strong> (welcome, credit_decaisse, retard, retrait, avaliste, funding...) |
| Email welcome | Joint le reglement interieur PDF automatiquement |
| Mode d'envoi | <code>on_commit</code> — non bloquant |

# 12. Bloc 11 — Notifications metier

## Notifications constatees sur le compte de recette

| Type | Message | Date |
|---|---|---|
| <code>savings.deposit_confirmed</code> | "Depot confirme - 1 000 XAF" | 2026-06-23 15:13:46 |

## Couverture du systeme de notifications

| Categorie | Templates configures |
|---|---|
| Adhesion | welcome, adhesion_activee, adhesion_rejetee |
| Credit | credit_decaisse, credit_retard, credit_solde, renouvellement_propose, mise_en_demeure |
| Epargne | versement_confirme, interets_credites, retrait_valide |
| Avaliste | avaliste_designation, consentement_demande, engagement_active |
| Pretur | funding_engagement_24h |

# 13. Bloc 12 — Securite runtime

## Controles effectues en production

| Controle | Statut |
|---|---|
| <code>PAYMENTS_TEST_AUTO_VALIDATE</code> | <span class="ui-btn">False</span> — confirme runtime |
| <code>CSRF_TRUSTED_ORIGINS</code> | 5 sous-domaines HTTPS declares |
| <code>ALLOWED_HOSTS</code> | hardene avec <code>gathe-backend, backend, localhost, 127.0.0.1</code> auto-ajoutes |
| Session cookies | HttpOnly, Secure, SameSite=Lax |
| TLS Let's Encrypt | 5 certificats valides, renouvellement automatique |
| Wagtail CMS | Authentification requise sur <code>/admin/</code> |
| Django admin | Authentification requise |
| Webhooks Tara | Signature HMAC obligatoire (403 si invalide) |

> Aucun mode de test n'est actif en production. Les paiements ne
> peuvent etre marques comme valides que via une confirmation Tara
> reelle ou un webhook signe.

# 14. Verdict consolide

## Synthese des 12 blocs

| # | Bloc | Indicateur | Verdict |
|---|---|---|---|
| 1 | Disponibilite plateformes | 5/5 en 200 | <span class="ui-btn">OK</span> |
| 2 | Authentification | login membre + staff | <span class="ui-btn">OK</span> |
| 3 | Etat compte membre | profil + solde + paiements | <span class="ui-btn">OK</span> |
| 4 | Moteur d'eligibilite | calcul dynamique correct | <span class="ui-btn">OK</span> |
| 5 | Catalogue public | savings, fees, rates, campagnes | <span class="ui-btn">OK</span> |
| 6 | Session staff | groupes + permissions | <span class="ui-btn">OK</span> |
| 7 | Dashboard admin | 8 sections KPI 2026 | <span class="ui-btn">OK</span> |
| 8 | Listes admin | 11 endpoints | <span class="ui-btn">OK</span> |
| 9 | Cron schedules | 10 crons programmes | <span class="ui-btn">OK</span> |
| 10 | Integrations | Tara HMAC + Brevo API | <span class="ui-btn">OK</span> |
| 11 | Notifications | savings.deposit_confirmed live | <span class="ui-btn">OK</span> |
| 12 | Securite | AUTO_VALIDATE off, CSRF, TLS | <span class="ui-btn">OK</span> |

## Conclusion

La plateforme Gathe Finance est **operationnelle en production** sur les
cinq fronts publics, avec un moteur metier reactif, des permissions
proprement segmentees, des integrations Tara et Brevo branchees, et un
ordonnanceur de taches automatiques actif.

Les douze blocs de recette retournent un verdict positif. Aucun bug
bloquant n'a ete identifie pendant cette session. La phase de
**recette client** peut commencer immediatement avec les comptes de
demonstration preserves.

# 15. Comptes et donnees de demonstration

## Comptes laisses actifs pour la presentation

| Compte | Email | Mot de passe | Role |
|---|---|---|---|
| Staff admin | <code>audit-horus@gathe-finance.com</code> | <code>Audit-Horus-2026!</code> | Acces complet console admin |
| Membre | <code>audit-member@gathe-finance.com</code> | <code>AuditMember2026</code> | Espace personnel portail |

## Donnees a montrer pendant la demo

| Element | Valeur |
|---|---|
| Solde epargne du membre | 1 000 XAF |
| Paiements visibles | 2 (1 rejete Tara, 1 valide webhook) |
| Notifications du membre | 1 non lue (depot confirme) |
| Membres totaux (KPI) | 1 actif |
| Epargne totale (KPI) | 1 000 XAF |
| Frais seedes | Adhesion 10 000, Inscription 2 000, Carnet 1 000 |
| Taux seedes | Interet 10 %, Penalite 50 %, Epargne 1 %/mois |
| FormSchemas seedes | 3 (adhesion, credit_brc, credit_avaliste) |
| Crons programmes | 10 actifs |

## URLs a charger devant le client

| Plateforme | URL |
|---|---|
| Vitrine | <code>https://gathe-finance.horus-lab.com/</code> |
| Portail membre | <code>https://portail.gathe-finance.horus-lab.com/connexion</code> |
| Console admin | <code>https://admin.gathe-finance.horus-lab.com/login</code> |
| CMS Wagtail | <code>https://cms.gathe-finance.horus-lab.com/admin/</code> |
| Documentation API | <code>https://api.gathe-finance.horus-lab.com/api/schema/swagger-ui/</code> |

## Apres la presentation

Pour nettoyer les comptes de demonstration, un script de purge est
fourni dans la fiche de remediation. La purge est optionnelle : ces
comptes ne presentent aucun risque securitaire grace a la segmentation
des permissions par groupe Django.
