# Checklist publication Google Play Store

> Auteur : Tchamba Tchakounte Edwin
> Date : 2026-06-20
> Cible : production Android v1.0.0

---

## 1. Artefact technique

| Item                | Valeur                                                              |
| ------------------- | ------------------------------------------------------------------- |
| Fichier             | `audit/release/gathe_finance_v1.0.0_1.aab`                          |
| Taille              | 52 Mo                                                               |
| applicationId       | `com.gathefinance.gathe_finance`                                    |
| versionName         | `1.0.0`                                                             |
| versionCode         | `1`                                                                 |
| compileSdk          | piloté par Flutter (Android 14+)                                    |
| minSdk              | piloté par Flutter (Android 5 / API 21)                             |
| targetSdk           | piloté par Flutter (Android 14+)                                    |
| R8 minify           | activé                                                              |
| Backend cible       | `https://api.gathe-finance.horus-lab.com` (injecté au build)        |
| Signature           | `jar verified` (AAB signé avec clé RSA 4096 PKCS12)                 |
| SHA-256 fingerprint | `E6:65:0B:49:EB:C0:DF:FF:C6:55:24:5F:71:6D:BC:3F:6F:45:04:D7:FF:D7:19:EA:EA:E9:B8:AB:35:E9:46:44` |

---

## 2. Clé d'upload (CRITIQUE)

* Type : clé d'upload (Upload key). Google gère la clé d'app signing finale via Play App Signing.
* Fichier : `mobile/android/keystore/gathefinance-upload.jks` (PKCS12, RSA 4096, 27 ans).
* Mot de passe : stocké dans `mobile/android/key.properties` (chmod 600, gitignored).
* Sauvegarde obligatoire : copier le `.jks` + le `key.properties` sur au moins 2 supports offline (clé USB chiffrée + papier au coffre + gestionnaire de mots de passe type Bitwarden / 1Password).

Si la clé est perdue mais Play App Signing est actif : possibilité de demander à Google une rotation de la clé d'upload via le formulaire dédié (https://support.google.com/googleplay/android-developer/answer/9842756). Cela peut prendre 1 à 2 semaines.

---

## 3. Politique de confidentialité

* URL à fournir au Play Console : `https://gathe-finance.horus-lab.com/fr/politique-confidentialite` (déjà publiée côté vitrine).
* Vérifier que la page mentionne :
  * données collectées : identité, contact, historique financier
  * base légale : exécution contractuelle + intérêt légitime
  * durée de conservation
  * droits d'accès, rectification, opposition
  * contact DPO : `contact@gathe-finance.com`
  * processus de demande de suppression de compte

---

## 4. Données safety form (Play Console)

| Catégorie                 | Collecté ? | Partagé ? | Optionnel ? | Justification                |
| ------------------------- | ---------- | --------- | ----------- | ---------------------------- |
| Identifiants personnels   | oui        | non       | non         | adhésion et compte membre    |
| Email                     | oui        | non       | non         | login, notifications         |
| Téléphone                 | oui        | non       | non         | login WhatsApp, Mobile Money |
| Données financières       | oui        | non       | non         | épargne, crédit              |
| Identifiants appareil     | non        | non       | non         |                              |
| Données de localisation   | non        | non       | non         |                              |
| Photos / médias           | oui        | non       | oui         | upload pièces (CNI, justifs) |
| Chiffrement en transit    | oui (HTTPS)|           |             |                              |
| Chiffrement au repos      | oui (Postgres + flutter_secure_storage côté device) | | |        |
| Suppression possible      | oui        |           |             | endpoint admin + RGPD        |

---

## 5. Catégorisation Play Console

* Type d'app : Finance.
* Catégorie : Finance.
* Public cible : 18+ (services financiers, conforme COBAC).
* Contenu : pas de violence, pas de jeu d'argent (ce n'est pas du gambling, c'est une coopérative).
* Service financier : oui.
* Permis nécessaires en local (Cameroun) : agrément COBAC ou certificat d'enregistrement coopératif. À joindre dans la déclaration.

---

## 6. Liste des permissions justifiées

| Permission                       | Justification                                |
| -------------------------------- | -------------------------------------------- |
| `USE_BIOMETRIC`                  | déverrouillage du PIN par empreinte ou face  |
| `INTERNET` (debug uniquement)    | hot-reload développement, retiré en release  |

L'absence de `READ_EXTERNAL_STORAGE`, `READ_CONTACTS`, `RECORD_AUDIO`, `CAMERA`, `ACCESS_FINE_LOCATION` est intentionnelle. Si on veut faire scanner une CNI plus tard, ajouter `CAMERA` avec justification.

---

## 7. Listing du store

### 7.1 FR (langue par défaut)

* **Titre** (30 caractères max) : « Gathe Finance Espace Membre »
* **Description courte** (80 caractères max) : « Gérez votre épargne, vos cotisations et vos crédits Gathe Finance »
* **Description longue** (4000 caractères max) :

```
Gathe Finance est une coopérative d'épargne et de crédit dédiée aux entrepreneurs et aux travailleurs camerounais. Cette application est l'espace membre officiel : elle vous permet de suivre votre compte au jour le jour, sans vous déplacer en agence.

CE QUE VOUS POUVEZ FAIRE
- Consulter votre solde d'épargne en temps réel, masqué et déverrouillable par empreinte ou code PIN
- Verser votre cotisation journalière, hebdomadaire ou mensuelle, en multi-jours pré-payé
- Choisir entre épargne libre et épargne placement 12 mois selon vos projets
- Demander un crédit (voie BRC, voie avaliste ou voie campagne micro-crédit)
- Suivre vos échéances de remboursement et payer en un geste
- Désigner un membre garant (avaliste) ou consentir à un mandat reçu
- Participer aux campagnes de financement entre membres (espace prêteur)
- Recevoir les annonces officielles de la coopérative
- Télécharger vos relevés et la note de votre demande de crédit en PDF
- Contacter le secrétariat en français ou en anglais

POURQUOI GATHE FINANCE
- Cooperative reconnue, transparente, alignée sur son règlement intérieur publié
- Frais clairs : adhésion 10 000 XAF, inscription 2 000 XAF, carnet 1 000 XAF
- Cotisation collecte avec commission 1 % uniquement à la clôture mensuelle
- Modèle solidaire : votre épargne sert aux crédits d'autres membres avec partage d'intérêts

SECURITE
- Connexion par code et empreinte
- Captures d'écran et aperçu dans le sélecteur d'applications bloqués
- Stockage local chiffré (Android Keystore)
- Chaque opération est tracée et auditable côté coopérative

CONTACT
- Siège : Rue Mermoz, Akwa, Douala, Cameroun
- Téléphone : +237 6 56 13 06 72 ou fixe 233 42 48 47
- E-mail : contact@gathe-finance.com
- Lundi à vendredi 8h00 à 17h00
```

* **Mots-clés** : épargne, crédit, microcrédit, coopérative, Cameroun, Douala, mobile money, finance solidaire, Tara, BRC.

### 7.2 EN

* **Title** : « Gathe Finance Member App »
* **Short description** : « Manage your savings, contributions and loans at Gathe Finance »
* **Long description** : version traduite du français ci-dessus.

---

## 8. Visuels obligatoires

| Asset                       | Taille                       | Statut                          |
| --------------------------- | ---------------------------- | ------------------------------- |
| Icône app                   | 512x512 PNG 32 bit avec alpha | à exporter depuis `mobile/assets/images/app_icon.png` |
| Image feature graphic       | 1024x500 PNG ou JPG          | à produire (bandeau marketing)  |
| Screenshots téléphone       | 8 minimum, 1080x1920 portrait | à reprendre depuis le livre v2 (captures mobile) |
| Vidéo promotionnelle (opt.) | YouTube                       | facultatif, peut être ajouté plus tard |

Suggestion sélection screenshots à recapturer proprement (8 visuels) : Splash, Login, Home (solde révélé), Sheet versement, Carnet, Crédit (3 voies), Demande crédit, Profil. Cible : viewport propre sans dialogue système. Réutiliser le script `livre_projet/capture_mobile_v4.sh` après désactivation manuelle de l'app parasite RH.

---

## 9. Test interne avant production

Recommandation forte avant publication ouverte :

1. Track « Test interne » Play Console (jusqu'à 100 testeurs internes).
2. Inviter 5 à 10 membres de la coopérative.
3. Cycle de 7 jours minimum.
4. Recueillir feedback via Brevo email automatique.
5. Bumper `versionCode` à 2 pour chaque correctif et republier.
6. Passer en « Test ouvert » (closed alpha) si OK, puis production.

---

## 10. Pré-requis avant submission

Tous P0 doivent être verts (cf. `audit/TESTS_PLAN.md` §10) :

* [ ] Bug racine backend `FOR UPDATE` fixé et 715/745 tests > 745/745
* [ ] Backend redéployé en prod
* [ ] Hook activation membre (CH-2) implémenté côté backend
* [ ] Privacy policy publiée et accessible
* [ ] AAB v1.0.0+1 signé (FAIT)
* [ ] Compte Play Console créé (25 USD frais unique)
* [ ] Compte développeur vérifié (identité légale Gathe Finance)
* [ ] Bénéficiaire COBAC ou agrément coopératif joint
* [ ] Screenshots propres (cf. §8)
* [ ] Test interne 7 jours minimum passé
* [ ] Adresse de support `contact@gathe-finance.com` opérationnelle

---

## 11. Commande de rebuild

Pour produire une nouvelle version après bumping `pubspec.yaml` (`version: 1.0.1+2` par exemple) :

```bash
cd mobile
flutter clean
flutter pub get
flutter build appbundle \
  --release \
  --dart-define=API_BASE_URL=https://api.gathe-finance.horus-lab.com
# AAB sera dans build/app/outputs/bundle/release/app-release.aab
```

---

## 12. Rappels critiques

* La clé d'upload est unique. La perdre = devoir contacter le support Google pour une rotation (Play App Signing).
* Le mot de passe est dans `key.properties` chmod 600. Ne jamais commit. Sauvegarder offline en 2 lieux distincts immédiatement.
* `versionCode` doit toujours être strictement croissant entre deux uploads.
* Si on retravaille R8 / ProGuard, garder `proguard-rules.pro` à jour pour les nouveaux plugins ajoutés à `pubspec.yaml`.
