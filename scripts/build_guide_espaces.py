# -*- coding: utf-8 -*-
"""Génère le Guide détaillé des espaces web GATHE Finance (paysage, style GATHE)."""
import html, pathlib

BASE = pathlib.Path("/home/tchakounte/Desktop/Gathe_finance/docs")
OUT = BASE / "Guide-Espaces-Web-Gathe-Finance.html"

# ------------------------------------------------------------------ contenu
MEMBRE = [
 ("00-connexion.jpg","Accès","Connexion à l'espace membre","/connexion",
  "Point d'entrée du portail membre. Identification par e-mail et mot de passe, avec lien de récupération et renvoi vers la vitrine.",
  ["Design institutionnel clair (bleu + vert du logo), typographie de marque.",
   "Lien « Faire une demande » pour les non-membres (candidature en ligne).",
   "Session glissante de 30 min ; le membre est redirigé ici à l'expiration."]),
 ("01-tableau-de-bord.jpg","Accueil","Tableau de bord","/",
  "Vue synthèse du patrimoine du membre : salutation nominative, numéro de sociétaire et statut du compte.",
  ["Deux poches distinctes : « Mon épargne » (classique) et « Ma collecte journalière ».",
   "Actions rapides : verser, mes crédits, demander un retrait, actualités.",
   "Fil des transactions récentes, typé et daté."]),
 ("02-epargne-hub.jpg","Épargne","Mon épargne — deux produits","/epargne",
  "Séparation nette des deux produits d'épargne conformément à la refonte 2026 : collecte journalière et épargne classique 12 mois.",
  ["Soldes de chaque poche + date d'ouverture du compte.",
   "Part « gelée » (apport mobilisable des crédits) et disponible au retrait affichés distinctement.",
   "Accès direct « Verser une collecte » et « Verser sur épargne »."]),
 ("03-epargne-depot-classique.jpg","Épargne","Verser sur l'épargne classique","/epargne/depot",
  "Formulaire de dépôt sur l'épargne classique avec choix de la finalité de l'argent.",
  ["Choix « Libre » (retrait à tout moment) vs « Placement » (financement de crédit + intérêts).",
   "Placement grisé lorsque la fenêtre est fermée — état correctement reflété à l'écran.",
   "Montant minimum 1 000 XAF, numéro Mobile Money avec détection auto de l'opérateur."]),
 ("04-epargne-retrait.jpg","Épargne","Demander un retrait","/epargne/retrait",
  "Initiation d'un retrait avec choix de la source, du montant, du motif et du canal de remise.",
  ["Source : collecte journalière ou épargne classique (part libre), disponibles affichés.",
   "Canal : Mobile Money (payout automatique) ou espèces à l'agence.",
   "Colonne « Mes demandes récentes » avec statut (approuvée, complétée, rejetée)."]),
 ("05-epargne-historique.jpg","Épargne","Historique des transactions","/epargne/historique",
  "Relevé des opérations, produit par produit, du plus récent au plus ancien.",
  ["Bascule collecte / épargne classique (comptes dissociés).",
   "Filtres par type (dépôts, retraits, intérêts) et colonnes date / montant / solde après."]),
 ("06-credit-hub.jpg","Crédit","Mes crédits","/credit",
  "Centre de gestion du crédit du membre : éligibilité, crédits en cours et actions de remboursement.",
  ["Garde-fou d'éligibilité : un seul crédit actif à la fois.",
   "Carte crédit : n° dossier, montant, taux, solde restant, total dû, date butoir.",
   "Actions : rembourser (Mobile Money), depuis l'épargne, demander une reconduction."]),
 ("07-credit-demande.jpg","Crédit","Demande de crédit — les voies","/credit/demande",
  "Formulaire de demande qui présente les voies d'éligibilité selon le profil du membre.",
  ["Voies : sur épargne, avec avaliste, campagne micro-crédit, garantie matérielle.",
   "Montant souhaité (min 5 000 XAF) et durée de remboursement (Art. 7).",
   "Garde-fou affiché si un crédit est déjà actif."]),
 ("08-credit-campagnes.jpg","Crédit","Campagnes ouvertes","/credit/campagnes",
  "Catalogue des campagnes de micro-crédit ciblées, accessibles même sans ancienneté.",
  ["Cartes campagne : profil cible, fourchette de montant, taux, délai de recouvrement, clôture.",
   "Boutons « Postuler » et « Détails & commentaires » (espace social).",
   "Visuels (flyers) chargés correctement côté portail."]),
 ("09-credit-historique.jpg","Crédit","Mes crédits clôturés","/credit/historique",
  "Archive des crédits passés avec l'échéancier complet et l'historique des remboursements.",
  ["Chaque ligne : n° dossier, montant, durée, date de décaissement, statut « Clôturé ».",
   "Détail dépliable par crédit."]),
 ("10-credit-remboursement.jpg","Crédit","Régler une échéance","/credit/remboursement",
  "Sélection du crédit à rembourser avant saisie du montant et du numéro Mobile Money.",
  ["Rappel du solde restant et du statut du crédit.",
   "Parcours en deux temps (choix du crédit puis validation du paiement)."]),
 ("11-credit-reconduction.jpg","Crédit","Demander une reconduction","/credit/reconduction",
  "Prolongation d'un crédit d'un mois avec choix de la modalité de paiement des intérêts (Art. 10/11).",
  ["Modalité « Comptant · 10 % » ou « Reporté · 15 % » (sur capital restant).",
   "Récapitulatif Article 11 : capital restant + intérêts à régler.",
   "Reconduction autorisée une seule fois par crédit."]),
 ("12-credit-mandats-avaliste.jpg","Crédit","Mes mandats d'avaliste","/credit/mandats-avaliste",
  "Espace où le membre répond aux demandes pour lesquelles il est désigné garant.",
  ["Avertissement d'engagement non-rétractable (Q13) : acceptation définitive.",
   "Liste des mandats à traiter et historique des décisions."]),
 ("13-carnet.jpg","Carnet","Mon carnet de collecte","/carnet",
  "Commande et suivi du carnet physique, avec les documents utiles de la coopérative.",
  ["Cycle de suivi : payée → en impression → délivrée.",
   "Documents : règlement intérieur (PDF) et spécimen du carnet.",
   "Retrait en agence sous 48 h après paiement, notification à la disponibilité."]),
 ("14-preteur.jpg","Prêteur","Espace prêteur","/preteur",
  "Le membre devient prêteur en plaçant une partie de son épargne pour financer les crédits.",
  ["Le montant placé devient prêtable ; l'engagement est géré par la coopérative.",
   "Rémunération = intérêt fixé par la coop sur les montants réellement prêtés.",
   "Suivi des intérêts perçus, crédités automatiquement sur l'épargne."]),
 ("15-paiements-recus.jpg","Paiements","Mes reçus de versement","/paiements",
  "Historique des versements avec téléchargement du reçu PDF de chaque opération.",
  ["Tous types couverts : frais, remboursement, décaissement, adhésion…",
   "Statut « Validé » et lien « Reçu » par ligne."]),
 ("16-annonces.jpg","Communication","Annonces","/annonces",
  "Communications officielles de la coopérative, avec visuels et pièces jointes.",
  ["Affichage riche (image en tête, date, corps du message).",
   "Diffusées depuis le back-office vers mobile + portail."]),
 ("17-actualites.jpg","Communication","Actualités","/actualites",
  "Fil éditorial (blog) de GATHE Finance, avec interaction sociale.",
  ["Articles illustrés, gérés dans le CMS et rendus selon la langue.",
   "« Lire & commenter » : likes et commentaires en fil."]),
 ("18-notifications.jpg","Communication","Notifications","/notifications",
  "Centre de notifications : activité du compte et annonces, filtrable par catégorie.",
  ["Filtres (épargne, crédit, paiement, annonce…) et « Tout marquer comme lu ».",
   "⚠ Constat : les titres s'affichent en anglais (à franciser — voir Constats)."]),
 ("19-profil.jpg","Compte","Mon profil","/profil",
  "Édition des coordonnées et du mot de passe ; modifications tracées dans l'audit.",
  ["Bandeau « Frais d'adhésion » réglés → compte actif.",
   "Coordonnées : e-mail (non modifiable), prénom, nom, téléphone.",
   "Liens vers préférences de notifications et support en ligne."]),
 ("20-profil-preferences-notifications.jpg","Compte","Préférences de notifications","/profil/preferences-notifications",
  "Réglage fin de ce que le membre reçoit et par quel canal.",
  ["Par catégorie (épargne, crédit, carnet, reconduction…).",
   "Par canal : in-app, e-mail, SMS."]),
 ("21-support.jpg","Compte","Support en ligne","/support",
  "Messagerie de support en fil unique entre le membre et la coopérative.",
  ["Le membre écrit ; le support répond directement dans le fil.",
   "Notification à chaque réponse (in-app + push)."]),
 ("22-renouvellement-adhesion.jpg","Compte","Renouveler mon adhésion","/renouvellement-adhesion",
  "Renouvellement annuel de l'adhésion par paiement du carnet (Art. 3).",
  ["Frais carnet annuel (1 000 XAF), canal Mobile Money (Tara).",
   "Fenêtre ouverte 30 jours avant l'anniversaire.",
   "Numéro de membre, solde d'épargne et historique conservés."]),
]

ADMIN = [
 ("00-connexion-back-office.jpg","Accès","Connexion back-office","/login",
  "Portail d'accès réservé au personnel de la coopérative.",
  ["Écran dédié, séparé de l'espace membre (accès refusé à un compte non-staff).",
   "Sécurité par cookie de session, domaine partagé entre sous-domaines."]),
 ("01-tableau-de-bord.jpg","Pilotage","Tableau de bord","/dashboard",
  "Vue d'ensemble opérationnelle temps réel de la coopérative.",
  ["KPI membres, adhésions à instruire, crédits en instruction, encours crédit.",
   "Blocs éligibilité 3 voies & prêteurs, épargne & cycles, risque & contentieux.",
   "Export « Rapport PDF » de l'état courant."]),
 ("02-pipeline-adhesion.jpg","Adhésions","Pipeline d'adhésion","/adhesions",
  "Suivi du funnel d'adhésion, de la demande publique à l'activation des 3 frais.",
  ["Compteurs par étape (en attente, approuvés, actifs, temporaires, rejetés, radiés).",
   "Parcours en 4 étapes matérialisé (soumission → approbation → 3 frais → actif)."]),
 ("03-annuaire-membres.jpg","Adhésions","Annuaire des membres","/members",
  "Répertoire financier par membre avec filtres par colonne et export.",
  ["Récap épargne (collecte, libre, placement), épargne totale, crédit en cours.",
   "Filtres par statut et par seuils ; ligne de totaux."]),
 ("04-utilisateurs-acces.jpg","Adhésions","Utilisateurs & accès (RBAC)","/access",
  "Gestion des comptes staff et des rôles (bundles d'onglets autorisés).",
  ["Onglets Utilisateurs / Rôles, statut par compte.",
   "Un rôle = ensemble de ressources autorisées ; « Accès total » pour les administrateurs."]),
 ("05-demandes-credit.jpg","Crédit","Demandes de crédit","/loan-requests",
  "File d'instruction du comité crédit ; l'approbation crée le crédit et l'échéancier.",
  ["Onglets par statut : frais à percevoir, attente avaliste, validation campagne, en instruction, provisoires, approuvées, rejetées.",
   "Colonnes configurables et export."]),
 ("06-portefeuille-credits.jpg","Crédit","Portefeuille des crédits","/loans",
  "Tous les crédits décaissés ou en cours de remboursement.",
  ["Filtres statut (actifs, en retard, clôturés, contentieux).",
   "Par crédit : montant, net versé, total dû, échéances, intérêts à la source.",
   "Actions : remboursement, décaissement manuel, funding par tranches."]),
 ("07-reconductions.jpg","Crédit","Renouvellements épargne","/renewals",
  "Comptes d'épargne classique arrivés à maturité 12 mois, à ré-inscrire.",
  ["Filtres : à encaisser, échéance ≤ 7j / ≤ 30j, actifs, archivés.",
   "Encaissement des frais de ré-inscription pour démarrer un nouveau cycle."]),
 ("08-avalistes-cautions.jpg","Crédit","Avalistes / cautions","/avaliste",
  "Cartographie « qui garantit qui », caution gelée et état de chaque mandat.",
  ["Colonnes demandeur / avaliste, montant, caution gelée, couverture, pièces/motif, statut.",
   "La décision appartient à l'avaliste depuis son espace ; l'acceptation est définitive."]),
 ("09-pool-preteurs.jpg","Crédit","Pool de tranches prêteur","/lender-tranches",
  "Réserve d'épargne placement mobilisable pour financer les crédits.",
  ["Réserve mobilisable, capital engagé, capital libéré, annulées.",
   "Rémunération proportionnelle à la mise (taux prêteur configurable) — libellé à jour."]),
 ("10-escalades-judiciaires.jpg","Crédit","Escalades judiciaires","/escalations",
  "Phase D/E du contentieux 2026 (instruction huissier, décision, exécution).",
  ["Éligibilité : saisie sur épargne (R1) déjà tentée et reliquat restant dû.",
   "Filtres par phase et ouverture d'une escalade."]),
 ("11-suivi-paiements.jpg","Épargne","Suivi des paiements","/payments",
  "Tous les versements traversant la plateforme (Mobile Money, espèces, virements).",
  ["Filtres par statut et par type (collecte, épargne, remboursement, décaissement, frais…).",
   "Action « Invalider » un paiement (contre-passation tracée) — présente à l'écran.",
   "Saisie d'un versement en agence."]),
 ("12-demandes-retrait.jpg","Épargne","Demandes de retrait","/withdrawals",
  "Validation des demandes de retrait des membres.",
  ["MOMO = payout automatique ; présentiel = remise espèces à confirmer.",
   "Onglets : à traiter, remise en attente, payout en cours/échoué, terminés, rejetés.",
   "Actions Approuver / Rejeter avec motif."]),
 ("13-commandes-carnet.jpg","Carnet","Commandes de carnet","/booklet-orders",
  "Suivi des carnets : payée → en impression → délivrée.",
  ["Filtres par état, colonnes membre / téléphone / paiement / statut.",
   "Action « Mettre en impression »."]),
 ("14-campagnes.jpg","Campagnes","Campagnes micro-crédit","/campaigns",
  "Micro-crédits destinés aux non-adhérents, par profil ciblé.",
  ["Cartes campagne : fenêtre, plafond, taux, bénéficiaires, ciblés.",
   "Création, détail et clôture ; bénéficiaires créés en statut temporaire."]),
 ("15-blog-cms.jpg","Vitrine · CMS","Articles du blog","/blog",
  "Activation/désactivation d'un article, image et prévisualisation des commentaires.",
  ["Bascule langue FR / EN ; édition complète dans Wagtail.",
   "⚠ Constat : « 0 article » affiché ici alors que la vitrine en publie 3 (à vérifier)."]),
 ("16-annonces-broadcast.jpg","Communication","Annonces broadcast","/announcements",
  "Diffusion d'un message à tous les membres ou à un sous-ensemble.",
  ["Audience : tous, actifs, suspendus, ou sélection manuelle.",
   "Lien interne + image illustrative ; matérialise une notification mobile + portail."]),
 ("17-commentaires.jpg","Modération","Commentaires","/comments",
  "Modération des commentaires postés par les membres (articles et campagnes).",
  ["Masquage avec motif ; la trace reste en base pour l'audit.",
   "Filtres statut / type ; actions Répondre / Masquer."]),
 ("18-formulaires-dynamiques.jpg","Configuration","Formulaires dynamiques","/forms",
  "Configuration des champs des trois formulaires métier, versionnés.",
  ["Adhésion, demande de crédit, reconduction ; une seule version active, les autres en brouillon.",
   "Champs verrouillés (câblés au code) non supprimables."]),
 ("19-support-membres.jpg","Communication","Support membres","/support",
  "Réponse aux messages des membres en fil de discussion.",
  ["Liste des fils à gauche, conversation à droite.",
   "Chaque réponse notifie le membre (in-app + push)."]),
 ("20-journal-audit.jpg","Audit","Journal d'audit","/audit",
  "Toutes les actions tracées : mutations API automatiques et événements métier.",
  ["Colonnes date, auteur, action, cible, IP, détails.",
   "Recherche et filtres par action / type / dates (690 entrées à la capture)."]),
 ("21-regles-parametres.jpg","Configuration","Règles & paramètres","/app-settings",
  "Toutes les règles modifiables sans déploiement, tracées dans l'audit.",
  ["Format n° membre, ancienneté minimum, collecte journalière, éligibilité, garanties…",
   "Chaque valeur éditable avec retour au « Défaut »."]),
 ("22-documents-officiels.jpg","Configuration","Documents officiels","/cooperative-asset",
  "PDF officiels joints automatiquement aux mails de bienvenue.",
  ["Règlement intérieur : aperçu, téléchargement, remplacement.",
   "Consultable par les membres (mobile + portail, rubrique Carnet)."]),
 ("23-frais-taux.jpg","Configuration","Frais & taux","/costs",
  "Montants et pourcentages appliqués par la coopérative, à effet immédiat.",
  ["Frais administratifs (adhésion, carnet, demande crédit, inscription, reconduction).",
   "Taux métier (pénalité, intérêt crédit, reconductions, intérêt épargne, frais transaction).",
   "Rappel : intérêt de crédit prélevé une seule fois, à la source."]),
 ("24-saisies-antidatees.jpg","Épargne","Saisies antidatées","/antidated-entries",
  "Reprise d'historique des carnets papier à leur vraie date.",
  ["Recrée un carnet à sa date d'origine et ressaisit versements/retraits.",
   "Aucune clôture rejouée, aucun paiement réel déclenché ; solde aligné sur le carnet."]),
 ("25-fin-de-mois-collecte.jpg","Collecte","Fin de mois collecte","/collecte-preferences",
  "Choix de chaque membre à la clôture mensuelle de la collecte.",
  ["Retrait cash, versement Mobile Money (destination indiquée), ou bascule épargne.",
   "1 % retenu par la coopérative à la bascule ; compteurs par choix."]),
 ("26-taches-planifiees.jpg","Configuration","Tâches planifiées (cron)","/cron-schedules",
  "Cadence des jobs automatiques (recette) avec exécution à la demande.",
  ["Jobs : clôture collecte, intérêts épargne, échéances, contentieux, campagnes, réconciliation…",
   "Cadence éditable + « Run-now » ; « valeur par défaut » signalée."]),
]

CONSTATS = [
 ("Corrigé","Portail — Notifications francisées",
  "Constat initial : les titres des notifications du portail s'affichaient en anglais (« Loan Approved », « Payment Confirmed Remboursement »…) alors que le mobile était francisé — rupture de parité. Le backend ne renvoyant que le type d'événement, le portail humanisait le slug anglais.",
  "Corrigé : table FR des libellés par type d'événement répliquée sur le portail (parité mobile), y compris le cas dynamique « payment.* ». Déployé (commit 78016e4)."),
 ("À vérifier","Blog admin affiche « 0 article »",
  "La page /blog du back-office affiche « 0 article » (FR) alors que la vitrine et le portail publient bien 3 articles. Probable écart de récupération/locale sur cette page d'administration.",
  "Contrôler l'appel de liste (locale racine Wagtail) ; le contenu public est intact."),
 ("Cosmétique","Flyer d'une campagne cassé (admin)",
  "Dans la liste des campagnes du back-office, le visuel de la première campagne ne se charge pas, tandis que les autres s'affichent. Côté vitrine, les visuels sont corrects.",
  "Re-téléverser le flyer concerné ou vérifier son URL de stockage."),
 ("Donnée de test","Profil — champ « Nom » contenant le prénom",
  "Le champ « Nom » du profil membre contient « Edwin tchako » (le prénom y est répété). Il s'agit d'une donnée de test ; le doublon d'affichage en en-tête a déjà été corrigé.",
  "Nettoyer la donnée si besoin ; aucun défaut d'interface."),
 ("Confirmé OK","Points vérifiés conformes",
  "Placement grisé (fenêtre terminée) correctement reflété ; pool prêteurs « rémunération proportionnelle à la mise » à jour ; action « Invalider » un paiement présente ; visuels de campagnes vitrine OK ; récap reconduction (Art. 11) exact.",
  "Aucune action requise."),
]

SEV = {"À corriger":"#B4471F","À vérifier":"#8A6D0B","Cosmétique":"#0B4FE0",
       "Donnée de test":"#6B6558","Confirmé OK":"#137A0E","Corrigé":"#137A0E"}

# ------------------------------------------------------------------ gabarits
def esc(s): return html.escape(s, quote=True)

def plate(space, idx, total, item):
    f,eyebrow,title,route,desc,bullets = item
    img = f"captures/espaces/{space}/{f}"
    lis = "".join(f"<li>{esc(b)}</li>" for b in bullets)
    part = "Espace membre" if space=="membre" else "Back-office"
    return f"""
<section class="page plate">
  <div class="plate-head">
    <span class="eyebrow">{esc(eyebrow)}</span>
    <h2>{esc(title)}</h2>
    <span class="route">{esc(route)}</span>
  </div>
  <div class="shot"><img src="{img}" alt="{esc(title)}"></div>
  <div class="explain">
    <p class="desc">{esc(desc)}</p>
    <ul class="keys">{lis}</ul>
  </div>
  <div class="foot"><span>GATHE Finance · Guide des espaces web</span><span>{part} · {idx:02d}/{total:02d}</span></div>
</section>"""

def divider(num, title, intro, tone):
    return f"""
<section class="page divider {tone}">
  <div class="dvbox">
    <span class="dvnum">{num}</span>
    <h2>{esc(title)}</h2>
    <span class="accent"></span>
    <p>{esc(intro)}</p>
  </div>
</section>"""

# constats page
def constats_page():
    cards=""
    for sev,titre,corps,action in CONSTATS:
        cards+=f"""
      <div class="cst">
        <span class="chip" style="--c:{SEV[sev]}">{esc(sev)}</span>
        <h3>{esc(titre)}</h3>
        <p>{esc(corps)}</p>
        <p class="act"><b>Action :</b> {esc(action)}</p>
      </div>"""
    return f"""
<section class="page constats">
  <div class="plate-head">
    <span class="eyebrow">Contrôle en profondeur</span>
    <h2>Constats & recommandations</h2>
  </div>
  <div class="cgrid">{cards}</div>
  <div class="foot"><span>GATHE Finance · Guide des espaces web</span><span>Synthèse d'audit</span></div>
</section>"""

# TOC
def toc():
    def rows(lst, space):
        return "".join(
            f'<div class="tocrow"><span class="ti">{esc(t)}</span><span class="td">{esc(e)}</span></div>'
            for (_f,e,t,_r,_d,_b) in lst)
    return f"""
<section class="page toc">
  <div class="plate-head"><span class="eyebrow">Sommaire</span><h2>Ce que contient ce document</h2></div>
  <div class="toccols">
    <div>
      <h3 class="tcap"><span class="dot blue"></span>Partie A — Espace membre <em>(portail)</em></h3>
      {rows(MEMBRE,'membre')}
    </div>
    <div>
      <h3 class="tcap"><span class="dot green"></span>Partie B — Back-office <em>(administration)</em></h3>
      {rows(ADMIN,'admin')}
    </div>
  </div>
  <div class="foot"><span>GATHE Finance · Guide des espaces web</span><span>Sommaire</span></div>
</section>"""

# cover
COVER = f"""
<section class="page cover">
  <div class="cov-top">
    <span class="wordmark">GAT<span class="hl">H</span>E <small>FINANCE</small></span>
  </div>
  <div class="cov-mid">
    <span class="kicker">Coopérative d'épargne et de crédit · Documentation produit</span>
    <h1>Espaces web<br><span class="thin">Guide détaillé & contrôle en profondeur</span></h1>
    <div class="cards">
      <div class="cc"><span class="dot blue"></span><b>Partie A — Espace membre</b><small>Portail du sociétaire</small></div>
      <div class="cc"><span class="dot green"></span><b>Partie B — Back-office</b><small>Dashboard d'administration</small></div>
    </div>
  </div>
  <div class="cov-bot">
    <div class="meta">
      <span><em>Rédacteur & maître d'œuvre</em>Tchamba Tchakounte Edwin — Chef technique</span>
      <span><em>Environnement</em>Recette (données de démonstration)</span>
      <span><em>Captures</em>En direct, paysage · 5 août 2026</span>
    </div>
  </div>
</section>"""

# ------------------------------------------------------------------ assemblage
plates_membre = "".join(plate("membre", i+1, len(MEMBRE), it) for i,it in enumerate(MEMBRE))
plates_admin  = "".join(plate("admin",  i+1, len(ADMIN),  it) for i,it in enumerate(ADMIN))

CSS = """
:root{--cream:#FBF7EF;--ink:#1D1B16;--muted:#6B6558;--blue:#0B4FE0;--green:#137A0E;
--line:#E7DFD1;--card:#FFFFFF;}
*{margin:0;padding:0;box-sizing:border-box}
html{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{font-family:'DM Sans',system-ui,sans-serif;color:var(--ink);background:#d8d2c6}
@page{size:A4 landscape;margin:0}
.page{position:relative;width:297mm;height:210mm;background:var(--cream);
overflow:hidden;page-break-after:always;padding:14mm 16mm}
h1,h2,h3,.wordmark{font-family:'Fraunces','Georgia',serif}
.eyebrow{font-size:9.5pt;letter-spacing:.16em;text-transform:uppercase;color:var(--blue);font-weight:600}
.plate-head{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
.plate-head h2{font-size:21pt;line-height:1.05;font-weight:600}
.route{margin-left:auto;font-family:'DM Sans';font-size:9pt;color:var(--muted);
background:#efe9dd;border-radius:20px;padding:3px 11px}
.plate .shot{margin-top:7mm;border:1px solid var(--line);border-radius:12px;overflow:hidden;
box-shadow:0 10px 26px rgba(29,27,22,.10);background:#fff;
height:106mm;display:flex;align-items:center;justify-content:center}
.plate .shot img{display:block;max-width:100%;max-height:106mm;width:auto;height:auto}
.explain{margin-top:6mm;display:grid;grid-template-columns:1.15fr 1fr;gap:10mm;align-items:start}
.desc{font-size:10.5pt;line-height:1.45;color:#37332b}
.keys{list-style:none;display:grid;gap:4px}
.keys li{position:relative;padding-left:16px;font-size:9.5pt;line-height:1.35;color:#403b32}
.keys li::before{content:"";position:absolute;left:0;top:6px;width:7px;height:7px;
border-radius:2px;background:var(--green)}
.foot{position:absolute;left:16mm;right:16mm;bottom:8mm;display:flex;justify-content:space-between;
font-size:8.5pt;color:var(--muted);letter-spacing:.02em}
/* cover */
.cover{display:flex;flex-direction:column;justify-content:space-between;
background:linear-gradient(150deg,#0B3AA6 0%,#0B4FE0 52%,#0A44C4 100%);color:#fff;padding:20mm}
.wordmark{font-size:23pt;font-weight:600;letter-spacing:.02em}
.wordmark small{font-size:9pt;letter-spacing:.32em;opacity:.8;margin-left:6px}
.wordmark .hl{color:#5BE36A}
.kicker{font-size:10.5pt;letter-spacing:.14em;text-transform:uppercase;opacity:.9}
.cov-mid h1{font-size:47pt;line-height:1.02;margin-top:10px;font-weight:600}
.cov-mid h1 .thin{font-size:24pt;font-weight:400;font-style:italic;opacity:.92}
.cards{display:flex;gap:14px;margin-top:20px}
.cc{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.22);border-radius:14px;
padding:14px 18px;display:flex;flex-direction:column;gap:2px;min-width:74mm}
.cc b{font-size:12.5pt}.cc small{opacity:.85;font-size:9.5pt}
.dot{width:10px;height:10px;border-radius:50%;display:inline-block;margin-bottom:6px}
.dot.blue{background:#5BA8FF}.dot.green{background:#5BE36A}
.meta{display:flex;gap:34px;flex-wrap:wrap}
.meta span{display:flex;flex-direction:column;font-size:11pt;font-weight:600}
.meta em{font-style:normal;font-size:8.5pt;letter-spacing:.12em;text-transform:uppercase;opacity:.8;
font-weight:400;margin-bottom:3px}
/* toc */
.toccols{margin-top:7mm;display:grid;grid-template-columns:1fr 1fr;gap:14mm}
.tcap{font-size:12.5pt;margin-bottom:5px;display:flex;align-items:center;gap:8px}
.tcap .dot{margin:0}.tcap .dot.blue{background:var(--blue)}.tcap .dot.green{background:var(--green)}
.tcap em{font-style:italic;font-weight:400;color:var(--muted);font-size:10pt}
.tocrow{display:flex;justify-content:space-between;gap:10px;padding:2px 0;border-bottom:1px dotted #ddd3c2}
.tocrow .ti{font-size:9pt}.tocrow .td{font-size:7.5pt;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
/* divider */
.divider{display:flex;align-items:center}
.divider.blue{background:linear-gradient(150deg,#0B3AA6,#0B4FE0)}
.divider.green{background:linear-gradient(150deg,#0E5F35,#137A0E)}
.dvbox{color:#fff;max-width:180mm}
.dvnum{font-family:'Fraunces',serif;font-size:80pt;font-weight:600;opacity:.35;line-height:1}
.dvbox h2{font-size:38pt;font-weight:600;margin-top:-6px}
.accent{display:block;width:64px;height:5px;border-radius:4px;background:#5BE36A;margin:14px 0}
.divider.green .accent{background:#BFF7C4}
.dvbox p{font-size:12.5pt;line-height:1.55;max-width:150mm;opacity:.95}
/* constats */
.cgrid{margin-top:9mm;display:grid;grid-template-columns:1fr 1fr;gap:8mm 10mm}
.cst{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;
box-shadow:0 6px 16px rgba(29,27,22,.06)}
.cst h3{font-size:13pt;margin:8px 0 5px}
.cst p{font-size:9.7pt;line-height:1.45;color:#403b32}
.cst .act{margin-top:6px;color:#2a2721}
.chip{font-family:'DM Sans';font-size:8pt;font-weight:600;letter-spacing:.08em;text-transform:uppercase;
color:#fff;background:var(--c);border-radius:20px;padding:3px 10px}
"""

HTML = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<title>GATHE Finance — Guide des espaces web</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600&family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body>
{COVER}
{toc()}
{divider('A','Espace membre','Le portail web du sociétaire : épargne, crédit, carnet, prêteur, communication et compte. Parcours complet, écran par écran, capturé en direct.','blue')}
{plates_membre}
{divider('B','Back-office',"Le dashboard d'administration : pilotage, adhésions, crédit, épargne & versements, campagnes, CMS et configuration. Vue exhaustive du poste de travail de la coopérative.",'green')}
{plates_admin}
{constats_page()}
</body></html>"""

OUT.write_text(HTML, encoding="utf-8")
print("écrit:", OUT, len(HTML), "octets")
print("membre:", len(MEMBRE), "admin:", len(ADMIN), "total plates:", len(MEMBRE)+len(ADMIN))
