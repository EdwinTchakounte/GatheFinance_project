// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for French (`fr`).
class AppL10nFr extends AppL10n {
  AppL10nFr([String locale = 'fr']) : super(locale);

  @override
  String get appTitle => 'GATHE Finance';

  @override
  String get common_continue => 'Continuer';

  @override
  String get common_cancel => 'Annuler';

  @override
  String get common_save => 'Enregistrer';

  @override
  String get common_close => 'Fermer';

  @override
  String get common_retry => 'Réessayer';

  @override
  String get common_back => 'Retour';

  @override
  String get common_loading => 'Chargement…';

  @override
  String get common_required => 'Requis';

  @override
  String get error_generic_title => 'Une erreur est survenue';

  @override
  String get error_generic_body =>
      'Impossible de charger ces données pour le moment. Vérifie ta connexion et réessaie.';

  @override
  String get nav_home => 'Accueil';

  @override
  String get nav_credit => 'Crédit';

  @override
  String get nav_booklet => 'Carnet';

  @override
  String get nav_profile => 'Profil';

  @override
  String get profile_eyebrow => 'Profil';

  @override
  String get profile_title => 'Mon compte';

  @override
  String get profile_section_finances => 'Mes finances';

  @override
  String get profile_section_security => 'Compte & sécurité';

  @override
  String get profile_section_preferences => 'Préférences';

  @override
  String get profile_member_badge => 'Membre';

  @override
  String get profile_tile_states => 'Mes états';

  @override
  String get profile_tile_states_sub => 'Solde, encours, ancienneté.';

  @override
  String get profile_tile_contributions => 'Mes frais';

  @override
  String get profile_tile_contributions_sub =>
      'Historique des frais payés à la coopérative.';

  @override
  String get profile_tile_lender => 'Espace prêteur';

  @override
  String get profile_tile_lender_sub => 'Convention, tranches et demandes 24h.';

  @override
  String get profile_tile_info => 'Mes informations';

  @override
  String get profile_tile_info_sub => 'Nom, e-mail, téléphone.';

  @override
  String get profile_tile_password => 'Sécurité & mot de passe';

  @override
  String get profile_tile_password_sub => 'Change ton mot de passe.';

  @override
  String get profile_tile_notifications => 'Notifications';

  @override
  String get profile_tile_notifications_sub => 'Push, email, SMS.';

  @override
  String get profile_tile_theme => 'Thème';

  @override
  String get profile_tile_theme_sub => 'Clair, sombre ou automatique.';

  @override
  String get profile_tile_language => 'Langue';

  @override
  String get profile_tile_language_sub => 'Français, English.';

  @override
  String get profile_tile_help => 'Aide & contact';

  @override
  String get profile_tile_help_sub => 'FAQ, support, agence.';

  @override
  String get profile_logout => 'Se déconnecter';

  @override
  String get theme_choice_title => 'Choisir le thème';

  @override
  String get theme_choice_desc =>
      'Sélectionne l\'apparence de l\'application. Le réglage est conservé sur cet appareil.';

  @override
  String get theme_auto => 'Automatique';

  @override
  String get theme_auto_desc => 'Suit les réglages de ton téléphone.';

  @override
  String get theme_light => 'Clair';

  @override
  String get theme_light_desc => 'Fonds cream et accents cobalt.';

  @override
  String get theme_dark => 'Sombre';

  @override
  String get theme_dark_desc => 'Confort nocturne, fonds cobalt profond.';

  @override
  String get language_choice_title => 'Choisir la langue';

  @override
  String get language_choice_desc =>
      'L\'application sera affichée dans la langue sélectionnée.';

  @override
  String get language_french => 'Français';

  @override
  String get language_english => 'English';

  @override
  String get home_eyebrow => 'Espace membre';

  @override
  String get home_greeting_night => 'Bonne nuit';

  @override
  String get home_greeting_morning => 'Bonjour';

  @override
  String get home_greeting_afternoon => 'Bon après-midi';

  @override
  String get home_greeting_evening => 'Bonsoir';

  @override
  String get home_account_active => 'Compte actif';

  @override
  String get home_my_savings => 'Mon épargne';

  @override
  String home_delta_week(String sign, String amount) {
    return '$sign $amount XAF ces 7 derniers jours';
  }

  @override
  String get home_no_movement_week => 'Pas de mouvement cette semaine.';

  @override
  String get home_deposit => 'Verser mon épargne';

  @override
  String get home_history => 'Historique';

  @override
  String get home_my_services => 'Mes services';

  @override
  String get home_my_services_sub => 'Tout est à portée d\'un geste.';

  @override
  String get home_request_credit => 'Demander un crédit';

  @override
  String get home_order_booklet => 'Commander mon carnet';

  @override
  String get home_repay => 'Rembourser une échéance';

  @override
  String get home_last_operations => 'Dernières opérations';

  @override
  String get home_no_operations => 'Aucune opération pour le moment.';

  @override
  String get home_history_unavailable => 'Historique indisponible.';

  @override
  String get home_hero_eyebrow => 'À ton rythme';

  @override
  String get home_hero_title => 'Construire,\npas à pas, ensemble.';

  @override
  String get home_hero_subtitle =>
      'La coopérative t\'accompagne dans la durée. Pose les bases d\'un patrimoine solide.';

  @override
  String get home_balance_unavailable => 'Solde indisponible';

  @override
  String get common_see_all => 'Voir tout';

  @override
  String get tx_deposit => 'Dépôt épargne';

  @override
  String get tx_deposit_cotisation => 'Versement collecte';

  @override
  String get tx_withdrawal => 'Retrait';

  @override
  String get tx_interest => 'Intérêts crédités';

  @override
  String tx_balance_after(String amount) {
    return 'Solde $amount';
  }

  @override
  String get login_title => 'Bon retour';

  @override
  String get login_subtitle => 'Pilotez votre épargne, suivez vos crédits.';

  @override
  String get login_sub_under_title =>
      'Identifiez-vous pour accéder à votre compte.';

  @override
  String get login_email_label => 'Adresse email';

  @override
  String get login_email_hint => 'tonadresse@example.com';

  @override
  String get login_email_required => 'Adresse email requise.';

  @override
  String get login_email_invalid => 'Format invalide.';

  @override
  String get login_password_label => 'Mot de passe';

  @override
  String get login_password_required => 'Mot de passe requis.';

  @override
  String get login_show_password => 'Afficher';

  @override
  String get login_hide_password => 'Masquer';

  @override
  String get login_forgot_password => 'Mot de passe oublié ?';

  @override
  String get login_submit => 'Se connecter';

  @override
  String get login_become_member => 'Devenir membre';

  @override
  String get login_not_member => 'Pas encore membre ?';

  @override
  String get login_security_tip =>
      'Ta session est chiffrée. Aucune information sensible n\'est stockée en clair sur l\'appareil.';

  @override
  String get common_or => 'OU';

  @override
  String get onb_eyebrow_welcome => 'Bienvenue';

  @override
  String get onb_skip => 'Passer';

  @override
  String get onb_continue => 'Continuer';

  @override
  String get onb_start => 'Commencer';

  @override
  String get onb_consent =>
      'En continuant tu acceptes les conditions de la coopérative.';

  @override
  String get onb_slide1_eyebrow => 'Épargne';

  @override
  String get onb_slide1_title => 'Ton épargne,\nun pas après l\'autre.';

  @override
  String get onb_slide1_body =>
      'Dépose en quelques secondes via Mobile Money. Suis ton solde et tes intérêts depuis ton téléphone.';

  @override
  String get onb_slide2_eyebrow => 'Crédit';

  @override
  String get onb_slide2_title => 'Finance tes projets\nau tarif coopératif.';

  @override
  String get onb_slide2_body =>
      'Demande un crédit basé sur ton épargne. Reçois directement ton décaissement sur ton numéro Mobile Money.';

  @override
  String get onb_slide3_eyebrow => 'Coopérative';

  @override
  String get onb_slide3_title =>
      'Une coopérative qui\nappartient à ses membres.';

  @override
  String get onb_slide3_body =>
      'Tes décisions comptent. Profite d\'une gouvernance transparente et de services administratifs simplifiés.';

  @override
  String get onb_slide4_eyebrow => 'Membre';

  @override
  String get onb_slide4_title => 'Pas un client.\nUn copropriétaire.';

  @override
  String get onb_slide4_body =>
      'Chez GATHE, tu ne déposes pas chez un tiers : tu participes à la coopérative, tu votes en assemblée et tu profites des bénéfices redistribués.';

  @override
  String get credit_eyebrow => 'Crédit';

  @override
  String get credit_title => 'Mes crédits';

  @override
  String get credit_in_progress_eyebrow => 'Crédit en cours';

  @override
  String get credit_status_active => 'Actif';

  @override
  String get credit_status_late => 'En retard';

  @override
  String get credit_status_closed => 'Clôturé';

  @override
  String get credit_remaining_balance => 'Solde restant';

  @override
  String credit_installments_count(int paid, int total) {
    return '$paid / $total échéances';
  }

  @override
  String get credit_next_installment => 'Prochaine échéance';

  @override
  String credit_see_installments(int count) {
    return 'Voir les $count échéances';
  }

  @override
  String get credit_repay => 'Rembourser';

  @override
  String get credit_renew => 'Reconduire';

  @override
  String get credit_meta_duration => 'Durée';

  @override
  String credit_meta_months(int count) {
    return '$count mois';
  }

  @override
  String get credit_meta_rate => 'Taux';

  @override
  String credit_meta_rate_value(String rate) {
    return '$rate %/an';
  }

  @override
  String get credit_meta_disbursed => 'Décaissé';

  @override
  String credit_schedule_for(String ref) {
    return 'Échéancier $ref';
  }

  @override
  String credit_schedule_summary(int count, String total) {
    return '$count échéances · $total total dû';
  }

  @override
  String get credit_empty_eyebrow => 'Aucun crédit';

  @override
  String get credit_empty_title => 'Pas encore de crédit';

  @override
  String credit_eligible_cap(String cap) {
    return 'Éligible . plafond $cap';
  }

  @override
  String get credit_not_eligible => 'Demande indisponible';

  @override
  String get credit_requests_title => 'Mes demandes';

  @override
  String get credit_requests_subtitle => 'État du dossier auprès du comité.';

  @override
  String get credit_req_pending => 'Frais à payer';

  @override
  String get credit_req_review => 'En instruction';

  @override
  String get credit_req_counter => 'Contre-proposition';

  @override
  String get credit_req_approved => 'Approuvée';

  @override
  String get credit_req_rejected => 'Rejetée';

  @override
  String credit_req_amount_duration(String amount, int duration) {
    return '$amount sur $duration mois';
  }

  @override
  String credit_req_submitted_on(String date) {
    return 'Soumise le $date';
  }

  @override
  String get credit_hero_eyebrow => 'Coopérative';

  @override
  String get credit_hero_title => 'Finance ton projet\navec ta coopérative.';

  @override
  String get credit_hero_subtitle =>
      'Un taux juste, un comité local, des décisions au plus près du terrain.';

  @override
  String get credit_error_title => 'Crédits indisponibles';

  @override
  String get booklet_eyebrow => 'Carnet';

  @override
  String get booklet_title => 'Mon carnet de collecte';

  @override
  String get booklet_pending_eyebrow => 'Commande en cours';

  @override
  String get booklet_status_paid => 'Payée';

  @override
  String get booklet_status_printing => 'En impression';

  @override
  String get booklet_status_delivered => 'Délivrée';

  @override
  String get booklet_step_payment => 'Payée';

  @override
  String get booklet_step_printing => 'En impression';

  @override
  String get booklet_step_delivered => 'Délivrée';

  @override
  String get booklet_hint_paid =>
      'Ton paiement est validé. L\'agence prépare ton carnet . cela prend généralement 48 h ouvrées.';

  @override
  String get booklet_hint_printing =>
      'Ton carnet est en impression. Tu recevras une notification dès qu\'il est prêt à être retiré.';

  @override
  String get booklet_hint_delivered => 'Carnet délivré. Merci !';

  @override
  String get booklet_new_eyebrow_fee => 'Frais 1 000 XAF';

  @override
  String get booklet_new_title => 'Commande un nouveau carnet.';

  @override
  String get booklet_step1 => 'Règle 1 000 XAF via Mobile Money.';

  @override
  String get booklet_step2 => 'L\'agence imprime ton carnet sous 48 h.';

  @override
  String get booklet_step3 =>
      'Notification au retrait . tu viens le récupérer.';

  @override
  String get booklet_order_cta => 'Commander mon carnet';

  @override
  String get booklet_history_title => 'Historique';

  @override
  String get booklet_history_subtitle => 'Carnets précédemment délivrés.';

  @override
  String booklet_history_item(String id) {
    return 'Carnet #$id';
  }

  @override
  String booklet_history_delivered_on(String date) {
    return 'Délivré le $date';
  }

  @override
  String get booklet_error_title => 'Carnet indisponible';

  @override
  String get booklet_active_title => 'Carnet actif';

  @override
  String booklet_active_subtitle(String date) {
    return 'Délivré le $date. Tu peux l\'utiliser pour tes versements à l\'agence.';
  }

  @override
  String get booklet_active_reorder_hint =>
      'Carnet épuisé ? Commander un nouveau';

  @override
  String get notifs_title => 'Notifications';

  @override
  String get notifs_mark_all_read => 'Tout lire';

  @override
  String get notifs_unavailable => 'Notifications indisponibles';

  @override
  String get notifs_empty_title => 'Aucune notification';

  @override
  String get notifs_empty_sub => 'Tout est à jour côté coopérative.';

  @override
  String notifs_rel_minutes(int n) {
    return 'il y a $n min';
  }

  @override
  String notifs_rel_hours(int n) {
    return 'il y a $n h';
  }

  @override
  String notifs_rel_days(int n) {
    return 'il y a $n j';
  }

  @override
  String get savings_history_eyebrow => 'Mon épargne';

  @override
  String get savings_history_title => 'Historique';

  @override
  String get savings_range_all => 'Tout';

  @override
  String get savings_range_this_month => 'Ce mois-ci';

  @override
  String get savings_range_last3 => '3 mois';

  @override
  String get savings_range_last6 => '6 mois';

  @override
  String get savings_type_all => 'Toutes';

  @override
  String get savings_type_deposits => 'Dépôts';

  @override
  String get savings_type_interest => 'Intérêts';

  @override
  String get savings_type_withdrawals => 'Retraits';

  @override
  String get savings_search_hint => 'Rechercher un montant…';

  @override
  String get savings_empty_amount =>
      'Aucune opération ne correspond à ce montant.';

  @override
  String get savings_empty_period => 'Aucune opération sur cette période.';

  @override
  String get savings_nothing_title => 'Rien à afficher';

  @override
  String get savings_history_unavailable => 'Historique indisponible';

  @override
  String get contrib_eyebrow => 'Profil';

  @override
  String get contrib_title => 'Mes frais';

  @override
  String get contrib_total_label => 'Total versé à la coopérative';

  @override
  String get contrib_type_inscription => 'Frais d\'inscription';

  @override
  String get contrib_type_adhesion => 'Frais d\'adhésion';

  @override
  String get contrib_type_credit_request => 'Frais de demande de crédit';

  @override
  String get contrib_type_renewal => 'Frais de reconduction';

  @override
  String get contrib_type_booklet => 'Frais de carnet';

  @override
  String get contrib_status_validated => 'Validé';

  @override
  String get contrib_status_pending => 'En attente';

  @override
  String get contrib_status_failed => 'Échec';

  @override
  String contrib_ref(String ref) {
    return 'Réf. $ref';
  }

  @override
  String get contrib_empty_title => 'Aucun versement';

  @override
  String get contrib_empty_sub =>
      'Tes frais payés à la coopérative apparaîtront ici au fur et à mesure.';

  @override
  String get contrib_error_title => 'Frais indisponibles';

  @override
  String get states_title => 'Mes états';

  @override
  String get states_releve_eyebrow => 'Mon relevé';

  @override
  String get states_releve_official => 'Officiel';

  @override
  String states_releve_on(String date) {
    return 'Au $date';
  }

  @override
  String states_member_since(String date) {
    return 'Membre depuis le $date.';
  }

  @override
  String get states_glance => 'En un coup d\'œil';

  @override
  String get states_kpi_savings => 'Solde épargne';

  @override
  String get states_kpi_credit => 'Encours crédit';

  @override
  String get states_no_active_credit => 'Aucun crédit actif';

  @override
  String get states_kpi_contributions => 'Solde collecte';

  @override
  String get states_kpi_seniority => 'Ancienneté';

  @override
  String get states_savings_detail => 'Mon épargne en détail';

  @override
  String get states_balance_today => 'Solde au jour';

  @override
  String get states_interest_rate => 'Taux d\'intérêt servi';

  @override
  String get states_account_opened => 'Compte ouvert le';

  @override
  String get states_movements => 'Mouvements enregistrés';

  @override
  String get states_contrib_detail_title => 'Détail de mon épargne';

  @override
  String get states_contrib_detail_sub =>
      'Voir la chronologie des frais payés.';

  @override
  String get states_pdf_soon => 'Génération PDF disponible bientôt.';

  @override
  String get states_download_pdf => 'Télécharger mon relevé PDF';

  @override
  String states_years(int n, String s) {
    return '$n an$s';
  }

  @override
  String states_months_total(int n) {
    return '$n mois cumulés';
  }

  @override
  String states_months(int n) {
    return '$n mois';
  }

  @override
  String states_days_long(int n) {
    return '$n jours';
  }

  @override
  String states_days_short(int n) {
    return '$n j';
  }

  @override
  String get states_since_join => 'depuis l\'adhésion';

  @override
  String get common_unavailable => 'Indisponible';

  @override
  String get help_eyebrow => 'Profil';

  @override
  String get help_copy_a11y => 'toucher pour copier';

  @override
  String get help_title => 'Aide & contact';

  @override
  String get help_intro_title => 'Une question ? On est là.';

  @override
  String get help_intro_sub =>
      'Trouve une réponse rapide dans la FAQ ou contacte directement l\'équipe par WhatsApp, téléphone ou e-mail.';

  @override
  String get help_faq_section => 'Questions fréquentes';

  @override
  String get help_contact_section => 'Nous contacter';

  @override
  String get help_faq1_q => 'Comment faire un dépôt sur mon compte épargne ?';

  @override
  String get help_faq1_a =>
      'Depuis l\'accueil, appuie sur « Déposer » puis choisis le montant. Le paiement passe par Tara (Mobile Money). Dès la validation, ton solde est crédité automatiquement.';

  @override
  String get help_faq2_q => 'Quand puis-je demander un crédit ?';

  @override
  String get help_faq2_a =>
      'Après 3 mois d\'épargne régulière (selon les statuts de la coopérative). Le montant maximum dépend de ton solde et de ton historique. Va dans l\'onglet « Crédit » pour lancer une demande.';

  @override
  String get help_faq3_q =>
      'Comment fonctionne la reconduction de mon crédit ?';

  @override
  String get help_faq3_a =>
      'À l\'approche de l\'échéance, tu peux demander une reconduction. Le comité étudie la demande sous 72h. Les frais de reconduction sont fixés par la coopérative.';

  @override
  String get help_faq4_q => 'Comment retirer mon carnet à l\'agence ?';

  @override
  String get help_faq4_a =>
      'Une fois la commande validée et les frais réglés, présente-toi à l\'agence avec ta pièce d\'identité. Un agent te remettra ton carnet officiel en main propre.';

  @override
  String get help_faq5_q => 'Mon argent est-il en sécurité ?';

  @override
  String get help_faq5_a =>
      'Oui. Tous les fonds sont logés sur le compte coopérative auprès d\'un établissement de crédit agréé. Les transactions sont tracées et auditées chaque trimestre.';

  @override
  String get help_contact_whatsapp => 'WhatsApp';

  @override
  String get help_contact_phone => 'Téléphone';

  @override
  String get help_contact_landline => 'Fixe';

  @override
  String get help_contact_email => 'Email';

  @override
  String get help_contact_agency => 'Agence';

  @override
  String get help_contact_hours => 'Horaires';

  @override
  String get help_copied_whatsapp => 'Numéro WhatsApp copié';

  @override
  String get help_copied_phone => 'Numéro copié';

  @override
  String get help_copied_landline => 'Numéro fixe copié';

  @override
  String get help_copied_email => 'Adresse e-mail copiée';

  @override
  String get help_copied_agency => 'Adresse copiée';

  @override
  String get notifprefs_eyebrow => 'Préférences';

  @override
  String get notifprefs_title => 'Notifications';

  @override
  String get notifprefs_intro_title => 'Comment souhaitez-vous être prévenu ?';

  @override
  String get notifprefs_intro_sub =>
      'Active ou désactive chaque canal (Push, Email, SMS) pour chaque type d\'événement de la coopérative.';

  @override
  String get notifprefs_cat_epargne => 'Épargne';

  @override
  String get notifprefs_cat_credit => 'Crédit';

  @override
  String get notifprefs_cat_carnet => 'Carnet';

  @override
  String get notifprefs_cat_reconduction => 'Reconduction';

  @override
  String get notifprefs_cat_securite => 'Sécurité';

  @override
  String get notifprefs_cat_epargne_sub =>
      'Dépôts validés, intérêts crédités, alertes solde.';

  @override
  String get notifprefs_cat_credit_sub =>
      'Demande, décision comité, décaissement, échéances.';

  @override
  String get notifprefs_cat_carnet_sub => 'Commande, retrait à l\'agence.';

  @override
  String get notifprefs_cat_reconduction_sub =>
      'Comité, frais à régler, validation.';

  @override
  String get notifprefs_cat_securite_sub =>
      'Connexions, changements de mot de passe, accès suspects.';

  @override
  String get notifprefs_chan_push => 'Push';

  @override
  String get notifprefs_chan_email => 'Email';

  @override
  String get notifprefs_chan_sms => 'SMS';

  @override
  String get notifprefs_unavailable => 'Préférences indisponibles';

  @override
  String get splash_eyebrow => 'COOPÉRATIVE D\'ÉPARGNE & DE CRÉDIT';

  @override
  String get splash_loading => 'Préparation de ton espace…';

  @override
  String get inst_status_paid => 'Payée';

  @override
  String get inst_status_upcoming => 'À venir';

  @override
  String get inst_status_late => 'En retard';

  @override
  String get inst_status_partial => 'Partielle';

  @override
  String inst_due_on(String date) {
    return 'Échéance $date';
  }

  @override
  String inst_capital_interest(String capital, String interest) {
    return 'Capital $capital · Intérêts $interest';
  }

  @override
  String get home_action_deposit => 'Verser';

  @override
  String get home_action_savings => 'Épargne';

  @override
  String get home_action_cotisation => 'Collecte';

  @override
  String get home_action_credit => 'Crédit';

  @override
  String get home_action_booklet => 'Carnet';

  @override
  String get home_action_history => 'Historique';

  @override
  String get home_recent_ops => 'Opérations récentes';

  @override
  String get home_see_all => 'Voir tout';

  @override
  String get home_balance_label => 'Solde épargne';

  @override
  String home_delta_this_month(String value) {
    return '$value ce mois';
  }

  @override
  String get carousel_save_title => 'Épargne chaque jour';

  @override
  String get carousel_save_sub => '1 000 FCFA/jour rémunérés à 1 % par mois.';

  @override
  String get carousel_save_cta => 'Verser';

  @override
  String get carousel_credit_title => 'Besoin d\'un crédit ?';

  @override
  String get carousel_credit_sub => 'Taux 10 % · durée selon le montant.';

  @override
  String get carousel_credit_cta => 'Demander';

  @override
  String get carousel_booklet_title => 'Commande ton carnet';

  @override
  String get carousel_booklet_sub => 'Carnet de collecte à 1 000 FCFA.';

  @override
  String get carousel_booklet_cta => 'Commander';

  @override
  String get carousel_help_title => 'Aide & contact';

  @override
  String get carousel_help_sub => 'Une question ? La coopérative répond.';

  @override
  String get carousel_help_cta => 'Contacter';

  @override
  String get credit_new_request => 'Nouvelle demande';

  @override
  String get credit_remaining => 'restants';

  @override
  String credit_due_total(String total, String rate) {
    return 'sur $total dus · taux $rate %';
  }

  @override
  String credit_repaid_pct(String pct) {
    return '$pct % remboursé';
  }

  @override
  String get credit_next_due => 'Prochaine échéance';

  @override
  String get credit_penalty_title => 'Pénalité de retard exigible';

  @override
  String get credit_penalty_sub =>
      '50 % des intérêts dus sur les échéances en retard (Article 12).';

  @override
  String get credit_empty_body =>
      'Soumets une demande au comité . taux 10 %, durée selon le palier du règlement (Article 7).';

  @override
  String get credit_empty_hint => 'Touche « + Nouvelle demande »';

  @override
  String get credit_status_litigation => 'Contentieux';

  @override
  String get credit_unavailable => 'Crédits indisponibles';

  @override
  String get profile_tile_pin => 'Code secret';

  @override
  String get profile_tile_pin_sub => 'Mettre à jour ton code à 4 chiffres';

  @override
  String get profile_tile_biometric => 'Empreinte digitale';

  @override
  String get profile_tile_biometric_sub =>
      'Déverrouiller l\'app sans saisir le code';

  @override
  String get biometric_cancelled => 'Authentification annulée.';

  @override
  String get pin_welcome_back => 'Bon retour';

  @override
  String pin_hello(String name) {
    return 'Bonjour, $name';
  }

  @override
  String get pin_wrong => 'Code incorrect. Réessaie.';

  @override
  String get pin_unlock_prompt => 'Saisis ton code secret pour déverrouiller.';

  @override
  String get pin_use_other_account => 'Utiliser un autre compte';

  @override
  String get pin_create_title => 'Crée ton code secret';

  @override
  String get pin_confirm_title => 'Confirme ton code';

  @override
  String get pin_mismatch => 'Les codes ne correspondent pas. Recommence.';

  @override
  String get pin_confirm_prompt =>
      'Saisis à nouveau le même code à 4 chiffres.';

  @override
  String get pin_create_sub =>
      'Ce code protège l\'accès à ton compte et masque ton solde.';

  @override
  String get pin_current_title => 'Code actuel';

  @override
  String get pin_current_sub => 'Saisis ton code secret actuel.';

  @override
  String get pin_new_title => 'Nouveau code';

  @override
  String get pin_new_sub => 'Choisis un nouveau code à 4 chiffres.';

  @override
  String get pin_confirm_new_title => 'Confirme le code';

  @override
  String get pin_confirm_new_sub => 'Saisis à nouveau le nouveau code.';

  @override
  String get pin_current_wrong => 'Code actuel incorrect.';

  @override
  String get pin_mismatch_short => 'Les codes ne correspondent pas.';

  @override
  String get pin_update_failed => 'Impossible de mettre à jour. Réessaie.';

  @override
  String get pin_updated => 'Code secret mis à jour ✓';

  @override
  String get pin_reveal_title => 'Affiche ton solde';

  @override
  String get pin_reveal_sub =>
      'Saisis ton code secret pour afficher le montant.';

  @override
  String get biometric_reason_unlock =>
      'Empreinte pour ouvrir ton espace GATHE Finance';

  @override
  String get biometric_reason_enable =>
      'Pose ton empreinte pour activer l\'ouverture rapide';

  @override
  String get biometric_signin_title => 'GATHE Finance';

  @override
  String get biometric_hint => 'Touche le capteur pour ouvrir ton espace';

  @override
  String get biometric_cancel_button => 'Utiliser le code PIN';

  @override
  String get releve_pdf_title => 'Relevé de compte';

  @override
  String get releve_pdf_member => 'Membre';

  @override
  String get releve_pdf_number => 'N° membre';

  @override
  String releve_pdf_issued_on(String date) {
    return 'Édité le $date';
  }

  @override
  String get releve_pdf_balance => 'Solde épargne';

  @override
  String get releve_pdf_rate => 'Taux d\'intérêt mensuel';

  @override
  String get releve_pdf_total_contrib => 'Total épargne validée';

  @override
  String get releve_pdf_tx_header => 'Opérations d\'épargne';

  @override
  String get releve_pdf_col_date => 'Date';

  @override
  String get releve_pdf_col_label => 'Libellé';

  @override
  String get releve_pdf_col_amount => 'Montant';

  @override
  String get releve_pdf_footer =>
      'Document généré par l\'application GATHE Finance . à titre informatif.';

  @override
  String get releve_pdf_filename => 'releve_gathe';

  @override
  String get common_done => 'Terminé';

  @override
  String get common_understood => 'Compris';

  @override
  String get common_amount => 'Montant';

  @override
  String get common_operator => 'Opérateur';

  @override
  String get common_number => 'Numéro';

  @override
  String get err_enter_amount => 'Saisis un montant.';

  @override
  String get err_min_100 => 'Minimum 100 XAF.';

  @override
  String get err_min_1000 => 'Minimum 1 000 XAF.';

  @override
  String get err_amount_multiple_50 =>
      'Le montant doit être un multiple de 50.';

  @override
  String err_collecte_min_per_day(String min, int days) {
    return 'Minimum $min ($days jour(s) × 1 000).';
  }

  @override
  String get err_number_incomplete => 'Numéro incomplet.';

  @override
  String get dep_title => 'Verser mon épargne';

  @override
  String get dep_how => 'Comment veux-tu verser aujourd\'hui ?';

  @override
  String get dep_mobile_money => 'Mobile Money';

  @override
  String get dep_mobile_sub => 'Paiement immédiat via Tara · 24h/24';

  @override
  String get dep_agency => 'À l\'agence';

  @override
  String get dep_agency_sub => 'Akwa Bercy · Lun–Ven · 08h00 – 17h00';

  @override
  String get dep_cutoff_note =>
      'Heure limite quotidienne : 17h00. Après ou en week-end, le versement est crédité au prochain jour ouvré.';

  @override
  String get dep_agency_title => 'On te garde une place à l\'agence';

  @override
  String get dep_agency_body =>
      'Présente-toi à GATHE FINANCE, Akwa Douala Bercy, avec ton numéro de membre. L\'agent enregistre ton versement et le crédit apparaît immédiatement.';

  @override
  String get dep_agency_place => 'Akwa, Douala . Bercy';

  @override
  String get dep_agency_hours => 'Lun–Ven · 08h00 – 17h00';

  @override
  String get dep_agency_cutoff => 'Cut-off journalier 17h00';

  @override
  String get dep_suggestion =>
      'Suggestion : 1 000 FCFA. Tu restes libre du montant.';

  @override
  String get classic_dep_title => 'Déposer sur l\'épargne';

  @override
  String get classic_dep_sub =>
      'Épargne classique . montant libre, séparé de ton épargne journalière.';

  @override
  String get classic_card_title => 'Épargne classique';

  @override
  String get classic_card_sub => 'Mets de côté quand tu veux';

  @override
  String get classic_card_cta => 'Déposer';

  @override
  String get dep_confirm_default => 'Confirmer le versement';

  @override
  String dep_confirm_amount(String amount) {
    return 'Verser $amount';
  }

  @override
  String get dep_waiting_title => 'En attente de ta confirmation…';

  @override
  String dep_waiting_body(String network, String amount) {
    return 'Un code te sera envoyé sur ton $network.\nSaisis ton PIN pour valider $amount.';
  }

  @override
  String get dep_waiting_hint => 'Cela peut prendre quelques secondes';

  @override
  String get dep_done_title => 'Versement confirmé';

  @override
  String dep_done_body(String amount) {
    return '$amount ont été crédités\nsur ton compte d\'épargne.';
  }

  @override
  String get lreq_title => 'Demander un crédit';

  @override
  String get lreq_intro =>
      'La durée et l\'échéancier sont fixés par le règlement à partir du montant.';

  @override
  String get lreq_amount => 'Montant souhaité';

  @override
  String get lreq_modality => 'Modalité de remboursement';

  @override
  String get lreq_motive => 'Motif de la demande';

  @override
  String get lreq_motive_hint =>
      'Explique ton projet . équipement, fonds de roulement, formation, etc.';

  @override
  String get lreq_motive_short => 'Motivation trop courte (min 10 caractères).';

  @override
  String get lreq_fees_note =>
      'Des frais de dossier (5 000 XAF) seront à régler après acceptation.';

  @override
  String get lreq_submit => 'Soumettre la demande';

  @override
  String get lreq_sending => 'Envoi en cours…';

  @override
  String get lreq_sent_title => 'Demande envoyée';

  @override
  String get lreq_sent_body =>
      'Règle les frais de dossier pour que ton dossier soit instruit par le comité.';

  @override
  String get lreq_schedule => 'Ton échéancier';

  @override
  String get lreq_duration => 'Durée';

  @override
  String get lreq_interest => 'Intérêts (10 %)';

  @override
  String get lreq_total => 'Total à rembourser';

  @override
  String get rep_title => 'Rembourser mon crédit';

  @override
  String rep_installment_n(String n) {
    return 'Échéance n°$n';
  }

  @override
  String rep_remaining_due(String amount) {
    return 'Restant dû : $amount';
  }

  @override
  String get rep_operator_mm => 'Opérateur Mobile Money';

  @override
  String get rep_confirm => 'Confirmer le remboursement';

  @override
  String rep_waiting_body(String network) {
    return 'Saisis ton code PIN $network\npour valider le remboursement.';
  }

  @override
  String get rep_done_title => 'Remboursement imputé';

  @override
  String rep_done_body(String amount) {
    return '$amount ont été imputés en FIFO\nsur tes échéances.';
  }

  @override
  String get ren_title => 'Reconduire mon crédit';

  @override
  String ren_subtitle(String dossier, String amount) {
    return 'Crédit $dossier . solde restant $amount.';
  }

  @override
  String get ren_extra_month => 'Prolongation : +1 mois';

  @override
  String get ren_mode_question => 'Comment règles-tu les intérêts ?';

  @override
  String get ren_mode_comptant => 'Au comptant . 10 %';

  @override
  String get ren_mode_comptant_sub =>
      'Tu verses les intérêts maintenant. Taux réduit sur le capital restant.';

  @override
  String get ren_mode_reporte => 'Reportés . 15 %';

  @override
  String get ren_mode_reporte_sub =>
      'Les intérêts sont reportés avec le capital. Taux majoré.';

  @override
  String get ren_recap_interest => 'Intérêts de reconduction';

  @override
  String get ren_recap_total => 'Nouveau total à rembourser';

  @override
  String get ren_fees_note =>
      'La reconduction prolonge ton crédit d\'un mois. Aucun frais de dossier n\'est dû : seuls les intérêts de reconduction, calculés sur le capital restant, s\'ajoutent. Ta demande sera soumise au comité pour validation.';

  @override
  String get ren_submit => 'Demander la reconduction';

  @override
  String get ren_sent_body =>
      'Ta demande de reconduction (+1 mois) a bien été envoyée.\nElle est en attente de validation du comité.';

  @override
  String lreq_installments(String n) {
    return '$n échéances';
  }

  @override
  String lreq_per_time(String amount) {
    return '$amount / fois';
  }

  @override
  String get common_modify => 'Modifier';

  @override
  String get common_firstname => 'Prénom';

  @override
  String get common_lastname => 'Nom';

  @override
  String get common_phone => 'Téléphone';

  @override
  String get common_email => 'Email';

  @override
  String get prof_logout_q => 'Se déconnecter ?';

  @override
  String get prof_logout_body =>
      'Tu devras te reconnecter avec ton email et ton mot de passe.';

  @override
  String get prof_logout_confirm => 'Oui, me déconnecter';

  @override
  String prof_member_num(String n) {
    return 'Membre · $n';
  }

  @override
  String get myinfo_saved => 'Informations enregistrées.';

  @override
  String get myinfo_title => 'Mes informations';

  @override
  String get myinfo_sub => 'Tu peux modifier ces champs depuis l\'app.';

  @override
  String get myinfo_firstname_required => 'Prénom requis';

  @override
  String get myinfo_lastname_required => 'Nom requis';

  @override
  String get myinfo_email_locked =>
      'Pour changer ton email, contacte le support.';

  @override
  String get pwd_title => 'Mot de passe';

  @override
  String get pwd_sub =>
      'Choisis un nouveau mot de passe d\'au moins 8 caractères.';

  @override
  String get pwd_old => 'Ancien mot de passe';

  @override
  String get pwd_old_required => 'Ancien mot de passe requis';

  @override
  String get pwd_new => 'Nouveau mot de passe';

  @override
  String get pwd_min_hint => 'Min 8 caractères';

  @override
  String get pwd_min_err => 'Au moins 8 caractères';

  @override
  String get pwd_diff_err => 'Doit être différent de l\'ancien';

  @override
  String get pwd_confirm => 'Confirmation';

  @override
  String get pwd_confirm_hint => 'Retape le nouveau mot de passe';

  @override
  String get pwd_mismatch => 'Les mots de passe ne correspondent pas';

  @override
  String get pwd_done_title => 'Mot de passe modifié';

  @override
  String get pwd_done_body =>
      'Tu utiliseras le nouveau dès la prochaine connexion.';

  @override
  String get bko_title => 'Commander mon carnet';

  @override
  String get bko_sub =>
      'Règle 1 000 XAF via Mobile Money pour lancer l\'impression.';

  @override
  String get bko_after_note =>
      'Une fois ton paiement validé, l\'agence imprime ton carnet et te prévient quand il est prêt.';

  @override
  String get bko_pay => 'Payer 1 000 XAF';

  @override
  String bko_waiting_body(String network) {
    return 'Saisis ton code PIN $network';
  }

  @override
  String get bko_done_title => 'Commande enregistrée';

  @override
  String get mi_eyebrow => 'Coopérative';

  @override
  String get mi_intro =>
      'Chez GATHE Finance, tu n\'es pas un simple client : tu deviens **copropriétaire** d\'une coopérative d\'épargne et de crédit. Tes décisions comptent, et les bénéfices reviennent aux membres.';

  @override
  String get mi_card1_title => 'Épargne sécurisée';

  @override
  String get mi_card1_body =>
      'Ton argent est protégé par la coopérative et rémunéré à 1 %/mois sur ton compte d\'épargne.';

  @override
  String get mi_card2_title => 'Crédit accessible';

  @override
  String get mi_card2_body =>
      'Crédit selon ton épargne. Taux 10 % par transaction, durée selon le règlement.';

  @override
  String get mi_card3_title => 'Voix au chapitre';

  @override
  String get mi_card3_body =>
      'Une part = une voix à l\'AG. Tu participes aux décisions de la coopérative.';

  @override
  String get mi_steps_title => 'Pour devenir membre';

  @override
  String get mi_step1 =>
      'Soumets ta demande d\'adhésion (formulaire ci-dessous)';

  @override
  String get mi_step2 => 'Règle les frais d\'adhésion (10 000 + 2 000 FCFA)';

  @override
  String get mi_step3 => 'Ton compte est activé après validation de ta demande';

  @override
  String get mi_submit => 'Soumettre ma demande';

  @override
  String get mi_later => 'Plus tard';

  @override
  String get mf_statut_salarie => 'Salarié';

  @override
  String get mf_statut_commercant => 'Commerçant';

  @override
  String get mf_statut_artisan => 'Artisan';

  @override
  String get mf_statut_sansemploi => 'Sans emploi';

  @override
  String get mf_statut_autre => 'Autre';

  @override
  String get mf_title => 'Devenir membre';

  @override
  String get mf_intro =>
      'Remplis ta demande. La coopérative l\'étudiera et te répondra.';

  @override
  String get mf_section_identity => 'Identité';

  @override
  String get mf_section_contact => 'Coordonnées';

  @override
  String get mf_section_location => 'Localisation';

  @override
  String get mf_section_statut => 'Statut professionnel';

  @override
  String get mf_section_urgence => 'Contact en cas d\'urgence';

  @override
  String get mf_section_motivation => 'Motivation (optionnel)';

  @override
  String get mf_section_pieces => 'Pièces justificatives';

  @override
  String get mf_pieces_intro =>
      'Toutes les pièces sont obligatoires (image ou PDF, 5 Mo max).';

  @override
  String get mf_piece_cni_recto => 'CNI . recto';

  @override
  String get mf_piece_cni_verso => 'CNI . verso';

  @override
  String get mf_piece_plan => 'Plan de localisation';

  @override
  String get mf_piece_photo => 'Photo d\'identité';

  @override
  String get mf_piece_tap_to_pick => 'Toucher pour choisir un fichier';

  @override
  String get mf_piece_remove => 'Retirer le fichier';

  @override
  String get mf_piece_too_large => 'Fichier trop volumineux (5 Mo max).';

  @override
  String get mf_pieces_required =>
      'Téléverse les 4 pièces avant d\'envoyer la demande.';

  @override
  String get mf_whatsapp => 'WhatsApp (optionnel)';

  @override
  String get mf_city => 'Ville';

  @override
  String get mf_quartier => 'Quartier / lieu précis';

  @override
  String get mf_urgence_nom => 'Nom & prénom';

  @override
  String get mf_urgence_lien => 'Lien (parent…)';

  @override
  String get mf_statut => 'Statut';

  @override
  String get mf_motivation_q => 'Quelle est votre motivation ?';

  @override
  String get mf_submit => 'Envoyer ma demande';

  @override
  String get mf_email_invalid => 'Email invalide';

  @override
  String get mf_fees_note =>
      'Frais à régler à l\'adhésion : 10 000 FCFA (adhésion) + 2 000 FCFA (inscription).';

  @override
  String get mf_sending => 'Envoi de ta demande…';

  @override
  String get mf_sent_title => 'Demande envoyée';

  @override
  String get mf_sent_body =>
      'La coopérative va étudier ton dossier et te répondra rapidement.';

  @override
  String get wd_action => 'Retirer';

  @override
  String get wd_title => 'Demander un retrait';

  @override
  String wd_subtitle(String balance) {
    return 'Disponible : $balance';
  }

  @override
  String get wd_channel_presentiel => 'Espèces (agence)';

  @override
  String get wd_channel_momo => 'Mobile Money';

  @override
  String get wd_field_amount => 'Montant';

  @override
  String get wd_field_motif => 'Raison du retrait';

  @override
  String get wd_field_motif_hint => 'Ex. urgence familiale, frais scolarité…';

  @override
  String get wd_field_phone => 'Numéro Mobile Money';

  @override
  String get wd_field_network => 'Réseau';

  @override
  String get wd_err_required => 'Obligatoire';

  @override
  String get wd_err_min_500 => 'Minimum 500 XAF';

  @override
  String get wd_err_over_balance => 'Montant supérieur au solde disponible.';

  @override
  String get wd_err_phone => 'Numéro invalide';

  @override
  String get wd_cta_submit => 'Envoyer la demande';

  @override
  String get wd_cta_close => 'Fermer';

  @override
  String get wd_disclaimer =>
      'Le solde est débité dès l\'envoi. L\'admin valide la sortie (espèces ou payout MOMO) sous 24 h.';

  @override
  String get wd_success_title => 'Demande envoyée à la coopérative';

  @override
  String get wd_recap_amount => 'Montant';

  @override
  String get wd_recap_channel => 'Canal';

  @override
  String get wd_recap_status => 'Statut';

  @override
  String get wd_loading => 'Envoi de la demande…';

  @override
  String offline_banner(String when) {
    return 'Hors-ligne . données du $when';
  }

  @override
  String get lreq_avaliste_title => 'Désigner un avaliste';

  @override
  String get lreq_avaliste_subtitle =>
      'Membre senior+BRC qui garantit le crédit.';

  @override
  String get lreq_avaliste_search_hint =>
      'Rechercher un membre (numéro ou nom)';

  @override
  String lreq_avaliste_saturated(String amount) {
    return 'Plafond atteint ($amount engagés)';
  }

  @override
  String lreq_avaliste_capacity(String amount, String numero) {
    return 'Dispo $amount ($numero)';
  }

  @override
  String lreq_avaliste_picked(String nom, String numero) {
    return 'Avaliste : $nom ($numero)';
  }

  @override
  String get lreq_avaliste_clear => 'Effacer';

  @override
  String get lreq_avaliste_required =>
      'Choisis un avaliste dans la liste (ou décoche).';

  @override
  String get lreq_avaliste_search_empty =>
      'Aucun membre éligible trouvé pour cette recherche.';

  @override
  String get lreq_campaign_title => 'Postuler à une campagne';

  @override
  String get lreq_campaign_subtitle =>
      'Crédit ciblé par la coopérative (ex. commerçants, agriculteurs).';

  @override
  String get lreq_campaign_pick => 'Choisir une campagne';

  @override
  String get lreq_campaign_required =>
      'Choisis une campagne dans la liste (ou décoche).';

  @override
  String get lreq_campaign_none =>
      'Aucune campagne active en ce moment. Réessaie plus tard ou décoche pour faire une demande standard.';

  @override
  String lreq_campaign_error(String error) {
    return 'Impossible de charger les campagnes : $error';
  }
}
