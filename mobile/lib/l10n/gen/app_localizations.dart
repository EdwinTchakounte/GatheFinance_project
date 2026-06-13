import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';
import 'app_localizations_fr.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppL10n
/// returned by `AppL10n.of(context)`.
///
/// Applications need to include `AppL10n.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'gen/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppL10n.localizationsDelegates,
///   supportedLocales: AppL10n.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppL10n.supportedLocales
/// property.
abstract class AppL10n {
  AppL10n(String locale)
      : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppL10n of(BuildContext context) {
    return Localizations.of<AppL10n>(context, AppL10n)!;
  }

  static const LocalizationsDelegate<AppL10n> delegate = _AppL10nDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
    delegate,
    GlobalMaterialLocalizations.delegate,
    GlobalCupertinoLocalizations.delegate,
    GlobalWidgetsLocalizations.delegate,
  ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('en'),
    Locale('fr')
  ];

  /// Application title
  ///
  /// In fr, this message translates to:
  /// **'Gathe Finance'**
  String get appTitle;

  /// No description provided for @common_continue.
  ///
  /// In fr, this message translates to:
  /// **'Continuer'**
  String get common_continue;

  /// No description provided for @common_cancel.
  ///
  /// In fr, this message translates to:
  /// **'Annuler'**
  String get common_cancel;

  /// No description provided for @common_save.
  ///
  /// In fr, this message translates to:
  /// **'Enregistrer'**
  String get common_save;

  /// No description provided for @common_close.
  ///
  /// In fr, this message translates to:
  /// **'Fermer'**
  String get common_close;

  /// No description provided for @common_retry.
  ///
  /// In fr, this message translates to:
  /// **'Réessayer'**
  String get common_retry;

  /// No description provided for @common_back.
  ///
  /// In fr, this message translates to:
  /// **'Retour'**
  String get common_back;

  /// No description provided for @common_loading.
  ///
  /// In fr, this message translates to:
  /// **'Chargement…'**
  String get common_loading;

  /// No description provided for @common_required.
  ///
  /// In fr, this message translates to:
  /// **'Requis'**
  String get common_required;

  /// No description provided for @error_generic_title.
  ///
  /// In fr, this message translates to:
  /// **'Une erreur est survenue'**
  String get error_generic_title;

  /// No description provided for @error_generic_body.
  ///
  /// In fr, this message translates to:
  /// **'Impossible de charger ces données pour le moment. Vérifie ta connexion et réessaie.'**
  String get error_generic_body;

  /// No description provided for @nav_home.
  ///
  /// In fr, this message translates to:
  /// **'Accueil'**
  String get nav_home;

  /// No description provided for @nav_credit.
  ///
  /// In fr, this message translates to:
  /// **'Crédit'**
  String get nav_credit;

  /// No description provided for @nav_booklet.
  ///
  /// In fr, this message translates to:
  /// **'Carnet'**
  String get nav_booklet;

  /// No description provided for @nav_profile.
  ///
  /// In fr, this message translates to:
  /// **'Profil'**
  String get nav_profile;

  /// No description provided for @profile_eyebrow.
  ///
  /// In fr, this message translates to:
  /// **'Profil'**
  String get profile_eyebrow;

  /// No description provided for @profile_title.
  ///
  /// In fr, this message translates to:
  /// **'Mon compte'**
  String get profile_title;

  /// No description provided for @profile_section_finances.
  ///
  /// In fr, this message translates to:
  /// **'Mes finances'**
  String get profile_section_finances;

  /// No description provided for @profile_section_security.
  ///
  /// In fr, this message translates to:
  /// **'Compte & sécurité'**
  String get profile_section_security;

  /// No description provided for @profile_section_preferences.
  ///
  /// In fr, this message translates to:
  /// **'Préférences'**
  String get profile_section_preferences;

  /// No description provided for @profile_member_badge.
  ///
  /// In fr, this message translates to:
  /// **'Membre'**
  String get profile_member_badge;

  /// No description provided for @profile_tile_states.
  ///
  /// In fr, this message translates to:
  /// **'Mes états'**
  String get profile_tile_states;

  /// No description provided for @profile_tile_states_sub.
  ///
  /// In fr, this message translates to:
  /// **'Solde, encours, ancienneté.'**
  String get profile_tile_states_sub;

  /// No description provided for @profile_tile_contributions.
  ///
  /// In fr, this message translates to:
  /// **'Mes frais'**
  String get profile_tile_contributions;

  /// No description provided for @profile_tile_contributions_sub.
  ///
  /// In fr, this message translates to:
  /// **'Historique des frais payés à la coopérative.'**
  String get profile_tile_contributions_sub;

  /// No description provided for @profile_tile_lender.
  ///
  /// In fr, this message translates to:
  /// **'Espace prêteur'**
  String get profile_tile_lender;

  /// No description provided for @profile_tile_lender_sub.
  ///
  /// In fr, this message translates to:
  /// **'Convention, tranches et demandes 24h.'**
  String get profile_tile_lender_sub;

  /// No description provided for @profile_tile_info.
  ///
  /// In fr, this message translates to:
  /// **'Mes informations'**
  String get profile_tile_info;

  /// No description provided for @profile_tile_info_sub.
  ///
  /// In fr, this message translates to:
  /// **'Nom, e-mail, téléphone.'**
  String get profile_tile_info_sub;

  /// No description provided for @profile_tile_password.
  ///
  /// In fr, this message translates to:
  /// **'Sécurité & mot de passe'**
  String get profile_tile_password;

  /// No description provided for @profile_tile_password_sub.
  ///
  /// In fr, this message translates to:
  /// **'Change ton mot de passe.'**
  String get profile_tile_password_sub;

  /// No description provided for @profile_tile_notifications.
  ///
  /// In fr, this message translates to:
  /// **'Notifications'**
  String get profile_tile_notifications;

  /// No description provided for @profile_tile_notifications_sub.
  ///
  /// In fr, this message translates to:
  /// **'Push, email, SMS.'**
  String get profile_tile_notifications_sub;

  /// No description provided for @profile_tile_theme.
  ///
  /// In fr, this message translates to:
  /// **'Thème'**
  String get profile_tile_theme;

  /// No description provided for @profile_tile_theme_sub.
  ///
  /// In fr, this message translates to:
  /// **'Clair, sombre ou automatique.'**
  String get profile_tile_theme_sub;

  /// No description provided for @profile_tile_language.
  ///
  /// In fr, this message translates to:
  /// **'Langue'**
  String get profile_tile_language;

  /// No description provided for @profile_tile_language_sub.
  ///
  /// In fr, this message translates to:
  /// **'Français, English.'**
  String get profile_tile_language_sub;

  /// No description provided for @profile_tile_help.
  ///
  /// In fr, this message translates to:
  /// **'Aide & contact'**
  String get profile_tile_help;

  /// No description provided for @profile_tile_help_sub.
  ///
  /// In fr, this message translates to:
  /// **'FAQ, support, agence.'**
  String get profile_tile_help_sub;

  /// No description provided for @profile_logout.
  ///
  /// In fr, this message translates to:
  /// **'Se déconnecter'**
  String get profile_logout;

  /// No description provided for @theme_choice_title.
  ///
  /// In fr, this message translates to:
  /// **'Choisir le thème'**
  String get theme_choice_title;

  /// No description provided for @theme_choice_desc.
  ///
  /// In fr, this message translates to:
  /// **'Sélectionne l\'apparence de l\'application. Le réglage est conservé sur cet appareil.'**
  String get theme_choice_desc;

  /// No description provided for @theme_auto.
  ///
  /// In fr, this message translates to:
  /// **'Automatique'**
  String get theme_auto;

  /// No description provided for @theme_auto_desc.
  ///
  /// In fr, this message translates to:
  /// **'Suit les réglages de ton téléphone.'**
  String get theme_auto_desc;

  /// No description provided for @theme_light.
  ///
  /// In fr, this message translates to:
  /// **'Clair'**
  String get theme_light;

  /// No description provided for @theme_light_desc.
  ///
  /// In fr, this message translates to:
  /// **'Fonds cream et accents cobalt.'**
  String get theme_light_desc;

  /// No description provided for @theme_dark.
  ///
  /// In fr, this message translates to:
  /// **'Sombre'**
  String get theme_dark;

  /// No description provided for @theme_dark_desc.
  ///
  /// In fr, this message translates to:
  /// **'Confort nocturne, fonds cobalt profond.'**
  String get theme_dark_desc;

  /// No description provided for @language_choice_title.
  ///
  /// In fr, this message translates to:
  /// **'Choisir la langue'**
  String get language_choice_title;

  /// No description provided for @language_choice_desc.
  ///
  /// In fr, this message translates to:
  /// **'L\'application sera affichée dans la langue sélectionnée.'**
  String get language_choice_desc;

  /// No description provided for @language_french.
  ///
  /// In fr, this message translates to:
  /// **'Français'**
  String get language_french;

  /// No description provided for @language_english.
  ///
  /// In fr, this message translates to:
  /// **'English'**
  String get language_english;

  /// No description provided for @home_eyebrow.
  ///
  /// In fr, this message translates to:
  /// **'Espace membre'**
  String get home_eyebrow;

  /// No description provided for @home_greeting_night.
  ///
  /// In fr, this message translates to:
  /// **'Bonne nuit'**
  String get home_greeting_night;

  /// No description provided for @home_greeting_morning.
  ///
  /// In fr, this message translates to:
  /// **'Bonjour'**
  String get home_greeting_morning;

  /// No description provided for @home_greeting_afternoon.
  ///
  /// In fr, this message translates to:
  /// **'Bon après-midi'**
  String get home_greeting_afternoon;

  /// No description provided for @home_greeting_evening.
  ///
  /// In fr, this message translates to:
  /// **'Bonsoir'**
  String get home_greeting_evening;

  /// No description provided for @home_account_active.
  ///
  /// In fr, this message translates to:
  /// **'Compte actif'**
  String get home_account_active;

  /// No description provided for @home_my_savings.
  ///
  /// In fr, this message translates to:
  /// **'Mon épargne'**
  String get home_my_savings;

  /// No description provided for @home_delta_week.
  ///
  /// In fr, this message translates to:
  /// **'{sign} {amount} XAF ces 7 derniers jours'**
  String home_delta_week(String sign, String amount);

  /// No description provided for @home_no_movement_week.
  ///
  /// In fr, this message translates to:
  /// **'Pas de mouvement cette semaine.'**
  String get home_no_movement_week;

  /// No description provided for @home_deposit.
  ///
  /// In fr, this message translates to:
  /// **'Verser mon épargne'**
  String get home_deposit;

  /// No description provided for @home_history.
  ///
  /// In fr, this message translates to:
  /// **'Historique'**
  String get home_history;

  /// No description provided for @home_my_services.
  ///
  /// In fr, this message translates to:
  /// **'Mes services'**
  String get home_my_services;

  /// No description provided for @home_my_services_sub.
  ///
  /// In fr, this message translates to:
  /// **'Tout est à portée d\'un geste.'**
  String get home_my_services_sub;

  /// No description provided for @home_request_credit.
  ///
  /// In fr, this message translates to:
  /// **'Demander un crédit'**
  String get home_request_credit;

  /// No description provided for @home_order_booklet.
  ///
  /// In fr, this message translates to:
  /// **'Commander mon carnet'**
  String get home_order_booklet;

  /// No description provided for @home_repay.
  ///
  /// In fr, this message translates to:
  /// **'Rembourser une échéance'**
  String get home_repay;

  /// No description provided for @home_last_operations.
  ///
  /// In fr, this message translates to:
  /// **'Dernières opérations'**
  String get home_last_operations;

  /// No description provided for @home_no_operations.
  ///
  /// In fr, this message translates to:
  /// **'Aucune opération pour le moment.'**
  String get home_no_operations;

  /// No description provided for @home_history_unavailable.
  ///
  /// In fr, this message translates to:
  /// **'Historique indisponible.'**
  String get home_history_unavailable;

  /// No description provided for @home_hero_eyebrow.
  ///
  /// In fr, this message translates to:
  /// **'À ton rythme'**
  String get home_hero_eyebrow;

  /// No description provided for @home_hero_title.
  ///
  /// In fr, this message translates to:
  /// **'Construire,\npas à pas, ensemble.'**
  String get home_hero_title;

  /// No description provided for @home_hero_subtitle.
  ///
  /// In fr, this message translates to:
  /// **'La coopérative t\'accompagne dans la durée. Pose les bases d\'un patrimoine solide.'**
  String get home_hero_subtitle;

  /// No description provided for @home_balance_unavailable.
  ///
  /// In fr, this message translates to:
  /// **'Solde indisponible'**
  String get home_balance_unavailable;

  /// No description provided for @common_see_all.
  ///
  /// In fr, this message translates to:
  /// **'Voir tout'**
  String get common_see_all;

  /// No description provided for @tx_deposit.
  ///
  /// In fr, this message translates to:
  /// **'Dépôt épargne'**
  String get tx_deposit;

  /// No description provided for @tx_deposit_cotisation.
  ///
  /// In fr, this message translates to:
  /// **'Versement cotisation'**
  String get tx_deposit_cotisation;

  /// No description provided for @tx_withdrawal.
  ///
  /// In fr, this message translates to:
  /// **'Retrait'**
  String get tx_withdrawal;

  /// No description provided for @tx_interest.
  ///
  /// In fr, this message translates to:
  /// **'Intérêts crédités'**
  String get tx_interest;

  /// No description provided for @tx_balance_after.
  ///
  /// In fr, this message translates to:
  /// **'Solde {amount}'**
  String tx_balance_after(String amount);

  /// No description provided for @login_title.
  ///
  /// In fr, this message translates to:
  /// **'Bon retour'**
  String get login_title;

  /// No description provided for @login_subtitle.
  ///
  /// In fr, this message translates to:
  /// **'Connecte-toi à ton compte pour gérer ton épargne,\nsuivre tes crédits et commander un carnet.'**
  String get login_subtitle;

  /// No description provided for @login_email_label.
  ///
  /// In fr, this message translates to:
  /// **'Adresse email'**
  String get login_email_label;

  /// No description provided for @login_email_hint.
  ///
  /// In fr, this message translates to:
  /// **'tonadresse@example.com'**
  String get login_email_hint;

  /// No description provided for @login_email_required.
  ///
  /// In fr, this message translates to:
  /// **'Adresse email requise.'**
  String get login_email_required;

  /// No description provided for @login_email_invalid.
  ///
  /// In fr, this message translates to:
  /// **'Format invalide.'**
  String get login_email_invalid;

  /// No description provided for @login_password_label.
  ///
  /// In fr, this message translates to:
  /// **'Mot de passe'**
  String get login_password_label;

  /// No description provided for @login_password_required.
  ///
  /// In fr, this message translates to:
  /// **'Mot de passe requis.'**
  String get login_password_required;

  /// No description provided for @login_show_password.
  ///
  /// In fr, this message translates to:
  /// **'Afficher'**
  String get login_show_password;

  /// No description provided for @login_hide_password.
  ///
  /// In fr, this message translates to:
  /// **'Masquer'**
  String get login_hide_password;

  /// No description provided for @login_forgot_password.
  ///
  /// In fr, this message translates to:
  /// **'Mot de passe oublié ?'**
  String get login_forgot_password;

  /// No description provided for @login_submit.
  ///
  /// In fr, this message translates to:
  /// **'Se connecter'**
  String get login_submit;

  /// No description provided for @login_become_member.
  ///
  /// In fr, this message translates to:
  /// **'Devenir membre'**
  String get login_become_member;

  /// No description provided for @login_security_tip.
  ///
  /// In fr, this message translates to:
  /// **'Ta session est chiffrée. Aucune information sensible n\'est stockée en clair sur l\'appareil.'**
  String get login_security_tip;

  /// No description provided for @common_or.
  ///
  /// In fr, this message translates to:
  /// **'OU'**
  String get common_or;

  /// No description provided for @onb_eyebrow_welcome.
  ///
  /// In fr, this message translates to:
  /// **'Bienvenue'**
  String get onb_eyebrow_welcome;

  /// No description provided for @onb_skip.
  ///
  /// In fr, this message translates to:
  /// **'Passer'**
  String get onb_skip;

  /// No description provided for @onb_continue.
  ///
  /// In fr, this message translates to:
  /// **'Continuer'**
  String get onb_continue;

  /// No description provided for @onb_start.
  ///
  /// In fr, this message translates to:
  /// **'Commencer'**
  String get onb_start;

  /// No description provided for @onb_consent.
  ///
  /// In fr, this message translates to:
  /// **'En continuant tu acceptes les conditions de la coopérative.'**
  String get onb_consent;

  /// No description provided for @onb_slide1_eyebrow.
  ///
  /// In fr, this message translates to:
  /// **'Épargne'**
  String get onb_slide1_eyebrow;

  /// No description provided for @onb_slide1_title.
  ///
  /// In fr, this message translates to:
  /// **'Ton épargne,\nun pas après l\'autre.'**
  String get onb_slide1_title;

  /// No description provided for @onb_slide1_body.
  ///
  /// In fr, this message translates to:
  /// **'Dépose en quelques secondes via Mobile Money. Suis ton solde et tes intérêts depuis ton téléphone.'**
  String get onb_slide1_body;

  /// No description provided for @onb_slide2_eyebrow.
  ///
  /// In fr, this message translates to:
  /// **'Crédit'**
  String get onb_slide2_eyebrow;

  /// No description provided for @onb_slide2_title.
  ///
  /// In fr, this message translates to:
  /// **'Finance tes projets\nau tarif coopératif.'**
  String get onb_slide2_title;

  /// No description provided for @onb_slide2_body.
  ///
  /// In fr, this message translates to:
  /// **'Demande un crédit basé sur ton épargne. Reçois directement ton décaissement sur ton numéro Mobile Money.'**
  String get onb_slide2_body;

  /// No description provided for @onb_slide3_eyebrow.
  ///
  /// In fr, this message translates to:
  /// **'Coopérative'**
  String get onb_slide3_eyebrow;

  /// No description provided for @onb_slide3_title.
  ///
  /// In fr, this message translates to:
  /// **'Une coopérative qui\nappartient à ses membres.'**
  String get onb_slide3_title;

  /// No description provided for @onb_slide3_body.
  ///
  /// In fr, this message translates to:
  /// **'Tes décisions comptent. Profite d\'une gouvernance transparente et de services administratifs simplifiés.'**
  String get onb_slide3_body;

  /// No description provided for @onb_slide4_eyebrow.
  ///
  /// In fr, this message translates to:
  /// **'Membre'**
  String get onb_slide4_eyebrow;

  /// No description provided for @onb_slide4_title.
  ///
  /// In fr, this message translates to:
  /// **'Pas un client.\nUn copropriétaire.'**
  String get onb_slide4_title;

  /// No description provided for @onb_slide4_body.
  ///
  /// In fr, this message translates to:
  /// **'Chez Gathe, tu ne déposes pas chez un tiers : tu participes à la coopérative, tu votes en assemblée et tu profites des bénéfices redistribués.'**
  String get onb_slide4_body;

  /// No description provided for @credit_eyebrow.
  ///
  /// In fr, this message translates to:
  /// **'Crédit'**
  String get credit_eyebrow;

  /// No description provided for @credit_title.
  ///
  /// In fr, this message translates to:
  /// **'Mes crédits'**
  String get credit_title;

  /// No description provided for @credit_in_progress_eyebrow.
  ///
  /// In fr, this message translates to:
  /// **'Crédit en cours'**
  String get credit_in_progress_eyebrow;

  /// No description provided for @credit_status_active.
  ///
  /// In fr, this message translates to:
  /// **'Actif'**
  String get credit_status_active;

  /// No description provided for @credit_status_late.
  ///
  /// In fr, this message translates to:
  /// **'En retard'**
  String get credit_status_late;

  /// No description provided for @credit_status_closed.
  ///
  /// In fr, this message translates to:
  /// **'Clôturé'**
  String get credit_status_closed;

  /// No description provided for @credit_remaining_balance.
  ///
  /// In fr, this message translates to:
  /// **'Solde restant'**
  String get credit_remaining_balance;

  /// No description provided for @credit_installments_count.
  ///
  /// In fr, this message translates to:
  /// **'{paid} / {total} échéances'**
  String credit_installments_count(int paid, int total);

  /// No description provided for @credit_next_installment.
  ///
  /// In fr, this message translates to:
  /// **'Prochaine échéance'**
  String get credit_next_installment;

  /// No description provided for @credit_see_installments.
  ///
  /// In fr, this message translates to:
  /// **'Voir les {count} échéances'**
  String credit_see_installments(int count);

  /// No description provided for @credit_repay.
  ///
  /// In fr, this message translates to:
  /// **'Rembourser'**
  String get credit_repay;

  /// No description provided for @credit_renew.
  ///
  /// In fr, this message translates to:
  /// **'Reconduire'**
  String get credit_renew;

  /// No description provided for @credit_meta_duration.
  ///
  /// In fr, this message translates to:
  /// **'Durée'**
  String get credit_meta_duration;

  /// No description provided for @credit_meta_months.
  ///
  /// In fr, this message translates to:
  /// **'{count} mois'**
  String credit_meta_months(int count);

  /// No description provided for @credit_meta_rate.
  ///
  /// In fr, this message translates to:
  /// **'Taux'**
  String get credit_meta_rate;

  /// No description provided for @credit_meta_rate_value.
  ///
  /// In fr, this message translates to:
  /// **'{rate} %/an'**
  String credit_meta_rate_value(String rate);

  /// No description provided for @credit_meta_disbursed.
  ///
  /// In fr, this message translates to:
  /// **'Décaissé'**
  String get credit_meta_disbursed;

  /// No description provided for @credit_schedule_for.
  ///
  /// In fr, this message translates to:
  /// **'Échéancier {ref}'**
  String credit_schedule_for(String ref);

  /// No description provided for @credit_schedule_summary.
  ///
  /// In fr, this message translates to:
  /// **'{count} échéances · {total} total dû'**
  String credit_schedule_summary(int count, String total);

  /// No description provided for @credit_empty_eyebrow.
  ///
  /// In fr, this message translates to:
  /// **'Aucun crédit'**
  String get credit_empty_eyebrow;

  /// No description provided for @credit_empty_title.
  ///
  /// In fr, this message translates to:
  /// **'Pas encore de crédit'**
  String get credit_empty_title;

  /// No description provided for @credit_eligible_cap.
  ///
  /// In fr, this message translates to:
  /// **'Éligible — plafond {cap}'**
  String credit_eligible_cap(String cap);

  /// No description provided for @credit_not_eligible.
  ///
  /// In fr, this message translates to:
  /// **'Demande indisponible'**
  String get credit_not_eligible;

  /// No description provided for @credit_requests_title.
  ///
  /// In fr, this message translates to:
  /// **'Mes demandes'**
  String get credit_requests_title;

  /// No description provided for @credit_requests_subtitle.
  ///
  /// In fr, this message translates to:
  /// **'État du dossier auprès du comité.'**
  String get credit_requests_subtitle;

  /// No description provided for @credit_req_pending.
  ///
  /// In fr, this message translates to:
  /// **'Frais à payer'**
  String get credit_req_pending;

  /// No description provided for @credit_req_review.
  ///
  /// In fr, this message translates to:
  /// **'En instruction'**
  String get credit_req_review;

  /// No description provided for @credit_req_counter.
  ///
  /// In fr, this message translates to:
  /// **'Contre-proposition'**
  String get credit_req_counter;

  /// No description provided for @credit_req_approved.
  ///
  /// In fr, this message translates to:
  /// **'Approuvée'**
  String get credit_req_approved;

  /// No description provided for @credit_req_rejected.
  ///
  /// In fr, this message translates to:
  /// **'Rejetée'**
  String get credit_req_rejected;

  /// No description provided for @credit_req_amount_duration.
  ///
  /// In fr, this message translates to:
  /// **'{amount} sur {duration} mois'**
  String credit_req_amount_duration(String amount, int duration);

  /// No description provided for @credit_req_submitted_on.
  ///
  /// In fr, this message translates to:
  /// **'Soumise le {date}'**
  String credit_req_submitted_on(String date);

  /// No description provided for @credit_hero_eyebrow.
  ///
  /// In fr, this message translates to:
  /// **'Coopérative'**
  String get credit_hero_eyebrow;

  /// No description provided for @credit_hero_title.
  ///
  /// In fr, this message translates to:
  /// **'Finance ton projet\navec ta coopérative.'**
  String get credit_hero_title;

  /// No description provided for @credit_hero_subtitle.
  ///
  /// In fr, this message translates to:
  /// **'Un taux juste, un comité local, des décisions au plus près du terrain.'**
  String get credit_hero_subtitle;

  /// No description provided for @credit_error_title.
  ///
  /// In fr, this message translates to:
  /// **'Crédits indisponibles'**
  String get credit_error_title;

  /// No description provided for @booklet_eyebrow.
  ///
  /// In fr, this message translates to:
  /// **'Carnet'**
  String get booklet_eyebrow;

  /// No description provided for @booklet_title.
  ///
  /// In fr, this message translates to:
  /// **'Mon carnet de collecte'**
  String get booklet_title;

  /// No description provided for @booklet_pending_eyebrow.
  ///
  /// In fr, this message translates to:
  /// **'Commande en cours'**
  String get booklet_pending_eyebrow;

  /// No description provided for @booklet_status_paid.
  ///
  /// In fr, this message translates to:
  /// **'Payée'**
  String get booklet_status_paid;

  /// No description provided for @booklet_status_printing.
  ///
  /// In fr, this message translates to:
  /// **'En impression'**
  String get booklet_status_printing;

  /// No description provided for @booklet_status_delivered.
  ///
  /// In fr, this message translates to:
  /// **'Délivrée'**
  String get booklet_status_delivered;

  /// No description provided for @booklet_step_payment.
  ///
  /// In fr, this message translates to:
  /// **'Payée'**
  String get booklet_step_payment;

  /// No description provided for @booklet_step_printing.
  ///
  /// In fr, this message translates to:
  /// **'En impression'**
  String get booklet_step_printing;

  /// No description provided for @booklet_step_delivered.
  ///
  /// In fr, this message translates to:
  /// **'Délivrée'**
  String get booklet_step_delivered;

  /// No description provided for @booklet_hint_paid.
  ///
  /// In fr, this message translates to:
  /// **'Ton paiement est validé. L\'agence prépare ton carnet — cela prend généralement 48 h ouvrées.'**
  String get booklet_hint_paid;

  /// No description provided for @booklet_hint_printing.
  ///
  /// In fr, this message translates to:
  /// **'Ton carnet est en impression. Tu recevras une notification dès qu\'il est prêt à être retiré.'**
  String get booklet_hint_printing;

  /// No description provided for @booklet_hint_delivered.
  ///
  /// In fr, this message translates to:
  /// **'Carnet délivré. Merci !'**
  String get booklet_hint_delivered;

  /// No description provided for @booklet_new_eyebrow_fee.
  ///
  /// In fr, this message translates to:
  /// **'Frais 1 000 XAF'**
  String get booklet_new_eyebrow_fee;

  /// No description provided for @booklet_new_title.
  ///
  /// In fr, this message translates to:
  /// **'Commande un nouveau carnet.'**
  String get booklet_new_title;

  /// No description provided for @booklet_step1.
  ///
  /// In fr, this message translates to:
  /// **'Règle 1 000 XAF via Mobile Money.'**
  String get booklet_step1;

  /// No description provided for @booklet_step2.
  ///
  /// In fr, this message translates to:
  /// **'L\'agence imprime ton carnet sous 48 h.'**
  String get booklet_step2;

  /// No description provided for @booklet_step3.
  ///
  /// In fr, this message translates to:
  /// **'Notification au retrait — tu viens le récupérer.'**
  String get booklet_step3;

  /// No description provided for @booklet_order_cta.
  ///
  /// In fr, this message translates to:
  /// **'Commander mon carnet'**
  String get booklet_order_cta;

  /// No description provided for @booklet_history_title.
  ///
  /// In fr, this message translates to:
  /// **'Historique'**
  String get booklet_history_title;

  /// No description provided for @booklet_history_subtitle.
  ///
  /// In fr, this message translates to:
  /// **'Carnets précédemment délivrés.'**
  String get booklet_history_subtitle;

  /// No description provided for @booklet_history_item.
  ///
  /// In fr, this message translates to:
  /// **'Carnet #{id}'**
  String booklet_history_item(String id);

  /// No description provided for @booklet_history_delivered_on.
  ///
  /// In fr, this message translates to:
  /// **'Délivré le {date}'**
  String booklet_history_delivered_on(String date);

  /// No description provided for @booklet_error_title.
  ///
  /// In fr, this message translates to:
  /// **'Carnet indisponible'**
  String get booklet_error_title;

  /// No description provided for @notifs_title.
  ///
  /// In fr, this message translates to:
  /// **'Notifications'**
  String get notifs_title;

  /// No description provided for @notifs_mark_all_read.
  ///
  /// In fr, this message translates to:
  /// **'Tout lire'**
  String get notifs_mark_all_read;

  /// No description provided for @notifs_unavailable.
  ///
  /// In fr, this message translates to:
  /// **'Notifications indisponibles'**
  String get notifs_unavailable;

  /// No description provided for @notifs_empty_title.
  ///
  /// In fr, this message translates to:
  /// **'Aucune notification'**
  String get notifs_empty_title;

  /// No description provided for @notifs_empty_sub.
  ///
  /// In fr, this message translates to:
  /// **'Tout est à jour côté coopérative.'**
  String get notifs_empty_sub;

  /// No description provided for @notifs_rel_minutes.
  ///
  /// In fr, this message translates to:
  /// **'il y a {n} min'**
  String notifs_rel_minutes(int n);

  /// No description provided for @notifs_rel_hours.
  ///
  /// In fr, this message translates to:
  /// **'il y a {n} h'**
  String notifs_rel_hours(int n);

  /// No description provided for @notifs_rel_days.
  ///
  /// In fr, this message translates to:
  /// **'il y a {n} j'**
  String notifs_rel_days(int n);

  /// No description provided for @savings_history_eyebrow.
  ///
  /// In fr, this message translates to:
  /// **'Mon épargne'**
  String get savings_history_eyebrow;

  /// No description provided for @savings_history_title.
  ///
  /// In fr, this message translates to:
  /// **'Historique'**
  String get savings_history_title;

  /// No description provided for @savings_range_all.
  ///
  /// In fr, this message translates to:
  /// **'Tout'**
  String get savings_range_all;

  /// No description provided for @savings_range_this_month.
  ///
  /// In fr, this message translates to:
  /// **'Ce mois-ci'**
  String get savings_range_this_month;

  /// No description provided for @savings_range_last3.
  ///
  /// In fr, this message translates to:
  /// **'3 mois'**
  String get savings_range_last3;

  /// No description provided for @savings_range_last6.
  ///
  /// In fr, this message translates to:
  /// **'6 mois'**
  String get savings_range_last6;

  /// No description provided for @savings_type_all.
  ///
  /// In fr, this message translates to:
  /// **'Toutes'**
  String get savings_type_all;

  /// No description provided for @savings_type_deposits.
  ///
  /// In fr, this message translates to:
  /// **'Dépôts'**
  String get savings_type_deposits;

  /// No description provided for @savings_type_interest.
  ///
  /// In fr, this message translates to:
  /// **'Intérêts'**
  String get savings_type_interest;

  /// No description provided for @savings_type_withdrawals.
  ///
  /// In fr, this message translates to:
  /// **'Retraits'**
  String get savings_type_withdrawals;

  /// No description provided for @savings_search_hint.
  ///
  /// In fr, this message translates to:
  /// **'Rechercher un montant…'**
  String get savings_search_hint;

  /// No description provided for @savings_empty_amount.
  ///
  /// In fr, this message translates to:
  /// **'Aucune opération ne correspond à ce montant.'**
  String get savings_empty_amount;

  /// No description provided for @savings_empty_period.
  ///
  /// In fr, this message translates to:
  /// **'Aucune opération sur cette période.'**
  String get savings_empty_period;

  /// No description provided for @savings_nothing_title.
  ///
  /// In fr, this message translates to:
  /// **'Rien à afficher'**
  String get savings_nothing_title;

  /// No description provided for @savings_history_unavailable.
  ///
  /// In fr, this message translates to:
  /// **'Historique indisponible'**
  String get savings_history_unavailable;

  /// No description provided for @contrib_eyebrow.
  ///
  /// In fr, this message translates to:
  /// **'Profil'**
  String get contrib_eyebrow;

  /// No description provided for @contrib_title.
  ///
  /// In fr, this message translates to:
  /// **'Mes frais'**
  String get contrib_title;

  /// No description provided for @contrib_total_label.
  ///
  /// In fr, this message translates to:
  /// **'Total versé à la coopérative'**
  String get contrib_total_label;

  /// No description provided for @contrib_type_inscription.
  ///
  /// In fr, this message translates to:
  /// **'Frais d\'inscription'**
  String get contrib_type_inscription;

  /// No description provided for @contrib_type_adhesion.
  ///
  /// In fr, this message translates to:
  /// **'Frais d\'adhésion'**
  String get contrib_type_adhesion;

  /// No description provided for @contrib_type_credit_request.
  ///
  /// In fr, this message translates to:
  /// **'Frais de demande de crédit'**
  String get contrib_type_credit_request;

  /// No description provided for @contrib_type_renewal.
  ///
  /// In fr, this message translates to:
  /// **'Frais de reconduction'**
  String get contrib_type_renewal;

  /// No description provided for @contrib_type_booklet.
  ///
  /// In fr, this message translates to:
  /// **'Frais de carnet'**
  String get contrib_type_booklet;

  /// No description provided for @contrib_status_validated.
  ///
  /// In fr, this message translates to:
  /// **'Validé'**
  String get contrib_status_validated;

  /// No description provided for @contrib_status_pending.
  ///
  /// In fr, this message translates to:
  /// **'En attente'**
  String get contrib_status_pending;

  /// No description provided for @contrib_status_failed.
  ///
  /// In fr, this message translates to:
  /// **'Échec'**
  String get contrib_status_failed;

  /// No description provided for @contrib_ref.
  ///
  /// In fr, this message translates to:
  /// **'Réf. {ref}'**
  String contrib_ref(String ref);

  /// No description provided for @contrib_empty_title.
  ///
  /// In fr, this message translates to:
  /// **'Aucun versement'**
  String get contrib_empty_title;

  /// No description provided for @contrib_empty_sub.
  ///
  /// In fr, this message translates to:
  /// **'Tes frais payés à la coopérative apparaîtront ici au fur et à mesure.'**
  String get contrib_empty_sub;

  /// No description provided for @contrib_error_title.
  ///
  /// In fr, this message translates to:
  /// **'Frais indisponibles'**
  String get contrib_error_title;

  /// No description provided for @states_title.
  ///
  /// In fr, this message translates to:
  /// **'Mes états'**
  String get states_title;

  /// No description provided for @states_releve_eyebrow.
  ///
  /// In fr, this message translates to:
  /// **'Mon relevé'**
  String get states_releve_eyebrow;

  /// No description provided for @states_releve_official.
  ///
  /// In fr, this message translates to:
  /// **'Officiel'**
  String get states_releve_official;

  /// No description provided for @states_releve_on.
  ///
  /// In fr, this message translates to:
  /// **'Au {date}'**
  String states_releve_on(String date);

  /// No description provided for @states_member_since.
  ///
  /// In fr, this message translates to:
  /// **'Membre depuis le {date}.'**
  String states_member_since(String date);

  /// No description provided for @states_glance.
  ///
  /// In fr, this message translates to:
  /// **'En un coup d\'œil'**
  String get states_glance;

  /// No description provided for @states_kpi_savings.
  ///
  /// In fr, this message translates to:
  /// **'Solde épargne'**
  String get states_kpi_savings;

  /// No description provided for @states_kpi_credit.
  ///
  /// In fr, this message translates to:
  /// **'Encours crédit'**
  String get states_kpi_credit;

  /// No description provided for @states_no_active_credit.
  ///
  /// In fr, this message translates to:
  /// **'Aucun crédit actif'**
  String get states_no_active_credit;

  /// No description provided for @states_kpi_contributions.
  ///
  /// In fr, this message translates to:
  /// **'Versements effectués'**
  String get states_kpi_contributions;

  /// No description provided for @states_kpi_seniority.
  ///
  /// In fr, this message translates to:
  /// **'Ancienneté'**
  String get states_kpi_seniority;

  /// No description provided for @states_savings_detail.
  ///
  /// In fr, this message translates to:
  /// **'Mon épargne en détail'**
  String get states_savings_detail;

  /// No description provided for @states_balance_today.
  ///
  /// In fr, this message translates to:
  /// **'Solde au jour'**
  String get states_balance_today;

  /// No description provided for @states_interest_rate.
  ///
  /// In fr, this message translates to:
  /// **'Taux d\'intérêt servi'**
  String get states_interest_rate;

  /// No description provided for @states_account_opened.
  ///
  /// In fr, this message translates to:
  /// **'Compte ouvert le'**
  String get states_account_opened;

  /// No description provided for @states_movements.
  ///
  /// In fr, this message translates to:
  /// **'Mouvements enregistrés'**
  String get states_movements;

  /// No description provided for @states_contrib_detail_title.
  ///
  /// In fr, this message translates to:
  /// **'Détail de mon épargne'**
  String get states_contrib_detail_title;

  /// No description provided for @states_contrib_detail_sub.
  ///
  /// In fr, this message translates to:
  /// **'Voir la chronologie des frais payés.'**
  String get states_contrib_detail_sub;

  /// No description provided for @states_pdf_soon.
  ///
  /// In fr, this message translates to:
  /// **'Génération PDF disponible bientôt.'**
  String get states_pdf_soon;

  /// No description provided for @states_download_pdf.
  ///
  /// In fr, this message translates to:
  /// **'Télécharger mon relevé PDF'**
  String get states_download_pdf;

  /// No description provided for @states_years.
  ///
  /// In fr, this message translates to:
  /// **'{n} an{s}'**
  String states_years(int n, String s);

  /// No description provided for @states_months_total.
  ///
  /// In fr, this message translates to:
  /// **'{n} mois cumulés'**
  String states_months_total(int n);

  /// No description provided for @states_months.
  ///
  /// In fr, this message translates to:
  /// **'{n} mois'**
  String states_months(int n);

  /// No description provided for @states_days_long.
  ///
  /// In fr, this message translates to:
  /// **'{n} jours'**
  String states_days_long(int n);

  /// No description provided for @states_days_short.
  ///
  /// In fr, this message translates to:
  /// **'{n} j'**
  String states_days_short(int n);

  /// No description provided for @states_since_join.
  ///
  /// In fr, this message translates to:
  /// **'depuis l\'adhésion'**
  String get states_since_join;

  /// No description provided for @common_unavailable.
  ///
  /// In fr, this message translates to:
  /// **'Indisponible'**
  String get common_unavailable;

  /// No description provided for @help_eyebrow.
  ///
  /// In fr, this message translates to:
  /// **'Profil'**
  String get help_eyebrow;

  /// No description provided for @help_copy_a11y.
  ///
  /// In fr, this message translates to:
  /// **'toucher pour copier'**
  String get help_copy_a11y;

  /// No description provided for @help_title.
  ///
  /// In fr, this message translates to:
  /// **'Aide & contact'**
  String get help_title;

  /// No description provided for @help_intro_title.
  ///
  /// In fr, this message translates to:
  /// **'Une question ? On est là.'**
  String get help_intro_title;

  /// No description provided for @help_intro_sub.
  ///
  /// In fr, this message translates to:
  /// **'Trouve une réponse rapide dans la FAQ ou contacte directement l\'équipe par WhatsApp, téléphone ou e-mail.'**
  String get help_intro_sub;

  /// No description provided for @help_faq_section.
  ///
  /// In fr, this message translates to:
  /// **'Questions fréquentes'**
  String get help_faq_section;

  /// No description provided for @help_contact_section.
  ///
  /// In fr, this message translates to:
  /// **'Nous contacter'**
  String get help_contact_section;

  /// No description provided for @help_faq1_q.
  ///
  /// In fr, this message translates to:
  /// **'Comment faire un dépôt sur mon compte épargne ?'**
  String get help_faq1_q;

  /// No description provided for @help_faq1_a.
  ///
  /// In fr, this message translates to:
  /// **'Depuis l\'accueil, appuie sur « Déposer » puis choisis le montant. Le paiement passe par Tara (Mobile Money). Dès la validation, ton solde est crédité automatiquement.'**
  String get help_faq1_a;

  /// No description provided for @help_faq2_q.
  ///
  /// In fr, this message translates to:
  /// **'Quand puis-je demander un crédit ?'**
  String get help_faq2_q;

  /// No description provided for @help_faq2_a.
  ///
  /// In fr, this message translates to:
  /// **'Après 3 mois d\'épargne régulière (selon les statuts de la coopérative). Le montant maximum dépend de ton solde et de ton historique. Va dans l\'onglet « Crédit » pour lancer une demande.'**
  String get help_faq2_a;

  /// No description provided for @help_faq3_q.
  ///
  /// In fr, this message translates to:
  /// **'Comment fonctionne la reconduction de mon crédit ?'**
  String get help_faq3_q;

  /// No description provided for @help_faq3_a.
  ///
  /// In fr, this message translates to:
  /// **'À l\'approche de l\'échéance, tu peux demander une reconduction. Le comité étudie la demande sous 72h. Les frais de reconduction sont fixés par la coopérative.'**
  String get help_faq3_a;

  /// No description provided for @help_faq4_q.
  ///
  /// In fr, this message translates to:
  /// **'Comment retirer mon carnet à l\'agence ?'**
  String get help_faq4_q;

  /// No description provided for @help_faq4_a.
  ///
  /// In fr, this message translates to:
  /// **'Une fois la commande validée et les frais réglés, présente-toi à l\'agence avec ta pièce d\'identité. Un agent te remettra ton carnet officiel en main propre.'**
  String get help_faq4_a;

  /// No description provided for @help_faq5_q.
  ///
  /// In fr, this message translates to:
  /// **'Mon argent est-il en sécurité ?'**
  String get help_faq5_q;

  /// No description provided for @help_faq5_a.
  ///
  /// In fr, this message translates to:
  /// **'Oui. Tous les fonds sont logés sur le compte coopérative auprès d\'un établissement de crédit agréé. Les transactions sont tracées et auditées chaque trimestre.'**
  String get help_faq5_a;

  /// No description provided for @help_contact_whatsapp.
  ///
  /// In fr, this message translates to:
  /// **'WhatsApp'**
  String get help_contact_whatsapp;

  /// No description provided for @help_contact_phone.
  ///
  /// In fr, this message translates to:
  /// **'Téléphone'**
  String get help_contact_phone;

  /// No description provided for @help_contact_landline.
  ///
  /// In fr, this message translates to:
  /// **'Fixe'**
  String get help_contact_landline;

  /// No description provided for @help_contact_email.
  ///
  /// In fr, this message translates to:
  /// **'Email'**
  String get help_contact_email;

  /// No description provided for @help_contact_agency.
  ///
  /// In fr, this message translates to:
  /// **'Agence'**
  String get help_contact_agency;

  /// No description provided for @help_contact_hours.
  ///
  /// In fr, this message translates to:
  /// **'Horaires'**
  String get help_contact_hours;

  /// No description provided for @help_copied_whatsapp.
  ///
  /// In fr, this message translates to:
  /// **'Numéro WhatsApp copié'**
  String get help_copied_whatsapp;

  /// No description provided for @help_copied_phone.
  ///
  /// In fr, this message translates to:
  /// **'Numéro copié'**
  String get help_copied_phone;

  /// No description provided for @help_copied_landline.
  ///
  /// In fr, this message translates to:
  /// **'Numéro fixe copié'**
  String get help_copied_landline;

  /// No description provided for @help_copied_email.
  ///
  /// In fr, this message translates to:
  /// **'Adresse e-mail copiée'**
  String get help_copied_email;

  /// No description provided for @help_copied_agency.
  ///
  /// In fr, this message translates to:
  /// **'Adresse copiée'**
  String get help_copied_agency;

  /// No description provided for @notifprefs_eyebrow.
  ///
  /// In fr, this message translates to:
  /// **'Préférences'**
  String get notifprefs_eyebrow;

  /// No description provided for @notifprefs_title.
  ///
  /// In fr, this message translates to:
  /// **'Notifications'**
  String get notifprefs_title;

  /// No description provided for @notifprefs_intro_title.
  ///
  /// In fr, this message translates to:
  /// **'Comment souhaitez-vous être prévenu ?'**
  String get notifprefs_intro_title;

  /// No description provided for @notifprefs_intro_sub.
  ///
  /// In fr, this message translates to:
  /// **'Active ou désactive chaque canal (Push, Email, SMS) pour chaque type d\'événement de la coopérative.'**
  String get notifprefs_intro_sub;

  /// No description provided for @notifprefs_cat_epargne.
  ///
  /// In fr, this message translates to:
  /// **'Épargne'**
  String get notifprefs_cat_epargne;

  /// No description provided for @notifprefs_cat_credit.
  ///
  /// In fr, this message translates to:
  /// **'Crédit'**
  String get notifprefs_cat_credit;

  /// No description provided for @notifprefs_cat_carnet.
  ///
  /// In fr, this message translates to:
  /// **'Carnet'**
  String get notifprefs_cat_carnet;

  /// No description provided for @notifprefs_cat_reconduction.
  ///
  /// In fr, this message translates to:
  /// **'Reconduction'**
  String get notifprefs_cat_reconduction;

  /// No description provided for @notifprefs_cat_securite.
  ///
  /// In fr, this message translates to:
  /// **'Sécurité'**
  String get notifprefs_cat_securite;

  /// No description provided for @notifprefs_cat_epargne_sub.
  ///
  /// In fr, this message translates to:
  /// **'Dépôts validés, intérêts crédités, alertes solde.'**
  String get notifprefs_cat_epargne_sub;

  /// No description provided for @notifprefs_cat_credit_sub.
  ///
  /// In fr, this message translates to:
  /// **'Demande, décision comité, décaissement, échéances.'**
  String get notifprefs_cat_credit_sub;

  /// No description provided for @notifprefs_cat_carnet_sub.
  ///
  /// In fr, this message translates to:
  /// **'Commande, retrait à l\'agence.'**
  String get notifprefs_cat_carnet_sub;

  /// No description provided for @notifprefs_cat_reconduction_sub.
  ///
  /// In fr, this message translates to:
  /// **'Comité, frais à régler, validation.'**
  String get notifprefs_cat_reconduction_sub;

  /// No description provided for @notifprefs_cat_securite_sub.
  ///
  /// In fr, this message translates to:
  /// **'Connexions, changements de mot de passe, accès suspects.'**
  String get notifprefs_cat_securite_sub;

  /// No description provided for @notifprefs_chan_push.
  ///
  /// In fr, this message translates to:
  /// **'Push'**
  String get notifprefs_chan_push;

  /// No description provided for @notifprefs_chan_email.
  ///
  /// In fr, this message translates to:
  /// **'Email'**
  String get notifprefs_chan_email;

  /// No description provided for @notifprefs_chan_sms.
  ///
  /// In fr, this message translates to:
  /// **'SMS'**
  String get notifprefs_chan_sms;

  /// No description provided for @notifprefs_unavailable.
  ///
  /// In fr, this message translates to:
  /// **'Préférences indisponibles'**
  String get notifprefs_unavailable;

  /// No description provided for @splash_eyebrow.
  ///
  /// In fr, this message translates to:
  /// **'COOPÉRATIVE D\'ÉPARGNE & DE CRÉDIT'**
  String get splash_eyebrow;

  /// No description provided for @splash_loading.
  ///
  /// In fr, this message translates to:
  /// **'Préparation de ton espace…'**
  String get splash_loading;

  /// No description provided for @inst_status_paid.
  ///
  /// In fr, this message translates to:
  /// **'Payée'**
  String get inst_status_paid;

  /// No description provided for @inst_status_upcoming.
  ///
  /// In fr, this message translates to:
  /// **'À venir'**
  String get inst_status_upcoming;

  /// No description provided for @inst_status_late.
  ///
  /// In fr, this message translates to:
  /// **'En retard'**
  String get inst_status_late;

  /// No description provided for @inst_status_partial.
  ///
  /// In fr, this message translates to:
  /// **'Partielle'**
  String get inst_status_partial;

  /// No description provided for @inst_due_on.
  ///
  /// In fr, this message translates to:
  /// **'Échéance {date}'**
  String inst_due_on(String date);

  /// No description provided for @inst_capital_interest.
  ///
  /// In fr, this message translates to:
  /// **'Capital {capital} · Intérêts {interest}'**
  String inst_capital_interest(String capital, String interest);

  /// No description provided for @home_action_deposit.
  ///
  /// In fr, this message translates to:
  /// **'Verser'**
  String get home_action_deposit;

  /// No description provided for @home_action_savings.
  ///
  /// In fr, this message translates to:
  /// **'Épargne'**
  String get home_action_savings;

  /// No description provided for @home_action_cotisation.
  ///
  /// In fr, this message translates to:
  /// **'Cotisation'**
  String get home_action_cotisation;

  /// No description provided for @home_action_credit.
  ///
  /// In fr, this message translates to:
  /// **'Crédit'**
  String get home_action_credit;

  /// No description provided for @home_action_booklet.
  ///
  /// In fr, this message translates to:
  /// **'Carnet'**
  String get home_action_booklet;

  /// No description provided for @home_action_history.
  ///
  /// In fr, this message translates to:
  /// **'Historique'**
  String get home_action_history;

  /// No description provided for @home_recent_ops.
  ///
  /// In fr, this message translates to:
  /// **'Opérations récentes'**
  String get home_recent_ops;

  /// No description provided for @home_see_all.
  ///
  /// In fr, this message translates to:
  /// **'Voir tout'**
  String get home_see_all;

  /// No description provided for @home_balance_label.
  ///
  /// In fr, this message translates to:
  /// **'Solde épargne'**
  String get home_balance_label;

  /// No description provided for @home_delta_this_month.
  ///
  /// In fr, this message translates to:
  /// **'{value} ce mois'**
  String home_delta_this_month(String value);

  /// No description provided for @carousel_save_title.
  ///
  /// In fr, this message translates to:
  /// **'Épargne chaque jour'**
  String get carousel_save_title;

  /// No description provided for @carousel_save_sub.
  ///
  /// In fr, this message translates to:
  /// **'1 000 FCFA/jour rémunérés à 1 % par mois.'**
  String get carousel_save_sub;

  /// No description provided for @carousel_save_cta.
  ///
  /// In fr, this message translates to:
  /// **'Verser'**
  String get carousel_save_cta;

  /// No description provided for @carousel_credit_title.
  ///
  /// In fr, this message translates to:
  /// **'Besoin d\'un crédit ?'**
  String get carousel_credit_title;

  /// No description provided for @carousel_credit_sub.
  ///
  /// In fr, this message translates to:
  /// **'Taux 10 % · durée selon le montant.'**
  String get carousel_credit_sub;

  /// No description provided for @carousel_credit_cta.
  ///
  /// In fr, this message translates to:
  /// **'Demander'**
  String get carousel_credit_cta;

  /// No description provided for @carousel_booklet_title.
  ///
  /// In fr, this message translates to:
  /// **'Commande ton carnet'**
  String get carousel_booklet_title;

  /// No description provided for @carousel_booklet_sub.
  ///
  /// In fr, this message translates to:
  /// **'Carnet de collecte à 1 000 FCFA.'**
  String get carousel_booklet_sub;

  /// No description provided for @carousel_booklet_cta.
  ///
  /// In fr, this message translates to:
  /// **'Commander'**
  String get carousel_booklet_cta;

  /// No description provided for @carousel_help_title.
  ///
  /// In fr, this message translates to:
  /// **'Aide & contact'**
  String get carousel_help_title;

  /// No description provided for @carousel_help_sub.
  ///
  /// In fr, this message translates to:
  /// **'Une question ? La coopérative répond.'**
  String get carousel_help_sub;

  /// No description provided for @carousel_help_cta.
  ///
  /// In fr, this message translates to:
  /// **'Contacter'**
  String get carousel_help_cta;

  /// No description provided for @credit_new_request.
  ///
  /// In fr, this message translates to:
  /// **'Nouvelle demande'**
  String get credit_new_request;

  /// No description provided for @credit_remaining.
  ///
  /// In fr, this message translates to:
  /// **'restants'**
  String get credit_remaining;

  /// No description provided for @credit_due_total.
  ///
  /// In fr, this message translates to:
  /// **'sur {total} dus · taux {rate} %'**
  String credit_due_total(String total, String rate);

  /// No description provided for @credit_repaid_pct.
  ///
  /// In fr, this message translates to:
  /// **'{pct} % remboursé'**
  String credit_repaid_pct(String pct);

  /// No description provided for @credit_next_due.
  ///
  /// In fr, this message translates to:
  /// **'Prochaine échéance'**
  String get credit_next_due;

  /// No description provided for @credit_penalty_title.
  ///
  /// In fr, this message translates to:
  /// **'Pénalité de retard exigible'**
  String get credit_penalty_title;

  /// No description provided for @credit_penalty_sub.
  ///
  /// In fr, this message translates to:
  /// **'50 % des intérêts dus sur les échéances en retard (Article 12).'**
  String get credit_penalty_sub;

  /// No description provided for @credit_empty_body.
  ///
  /// In fr, this message translates to:
  /// **'Soumets une demande au comité — taux 10 %, durée selon le palier du règlement (Article 7).'**
  String get credit_empty_body;

  /// No description provided for @credit_empty_hint.
  ///
  /// In fr, this message translates to:
  /// **'Touche « + Nouvelle demande »'**
  String get credit_empty_hint;

  /// No description provided for @credit_status_litigation.
  ///
  /// In fr, this message translates to:
  /// **'Contentieux'**
  String get credit_status_litigation;

  /// No description provided for @credit_unavailable.
  ///
  /// In fr, this message translates to:
  /// **'Crédits indisponibles'**
  String get credit_unavailable;

  /// No description provided for @profile_tile_pin.
  ///
  /// In fr, this message translates to:
  /// **'Code secret'**
  String get profile_tile_pin;

  /// No description provided for @profile_tile_pin_sub.
  ///
  /// In fr, this message translates to:
  /// **'Mettre à jour ton code à 4 chiffres'**
  String get profile_tile_pin_sub;

  /// No description provided for @profile_tile_biometric.
  ///
  /// In fr, this message translates to:
  /// **'Empreinte digitale'**
  String get profile_tile_biometric;

  /// No description provided for @profile_tile_biometric_sub.
  ///
  /// In fr, this message translates to:
  /// **'Déverrouiller l\'app sans saisir le code'**
  String get profile_tile_biometric_sub;

  /// No description provided for @biometric_cancelled.
  ///
  /// In fr, this message translates to:
  /// **'Authentification annulée.'**
  String get biometric_cancelled;

  /// No description provided for @pin_welcome_back.
  ///
  /// In fr, this message translates to:
  /// **'Bon retour'**
  String get pin_welcome_back;

  /// No description provided for @pin_hello.
  ///
  /// In fr, this message translates to:
  /// **'Bonjour, {name}'**
  String pin_hello(String name);

  /// No description provided for @pin_wrong.
  ///
  /// In fr, this message translates to:
  /// **'Code incorrect. Réessaie.'**
  String get pin_wrong;

  /// No description provided for @pin_unlock_prompt.
  ///
  /// In fr, this message translates to:
  /// **'Saisis ton code secret pour déverrouiller.'**
  String get pin_unlock_prompt;

  /// No description provided for @pin_use_other_account.
  ///
  /// In fr, this message translates to:
  /// **'Utiliser un autre compte'**
  String get pin_use_other_account;

  /// No description provided for @pin_create_title.
  ///
  /// In fr, this message translates to:
  /// **'Crée ton code secret'**
  String get pin_create_title;

  /// No description provided for @pin_confirm_title.
  ///
  /// In fr, this message translates to:
  /// **'Confirme ton code'**
  String get pin_confirm_title;

  /// No description provided for @pin_mismatch.
  ///
  /// In fr, this message translates to:
  /// **'Les codes ne correspondent pas. Recommence.'**
  String get pin_mismatch;

  /// No description provided for @pin_confirm_prompt.
  ///
  /// In fr, this message translates to:
  /// **'Saisis à nouveau le même code à 4 chiffres.'**
  String get pin_confirm_prompt;

  /// No description provided for @pin_create_sub.
  ///
  /// In fr, this message translates to:
  /// **'Ce code protège l\'accès à ton compte et masque ton solde.'**
  String get pin_create_sub;

  /// No description provided for @pin_current_title.
  ///
  /// In fr, this message translates to:
  /// **'Code actuel'**
  String get pin_current_title;

  /// No description provided for @pin_current_sub.
  ///
  /// In fr, this message translates to:
  /// **'Saisis ton code secret actuel.'**
  String get pin_current_sub;

  /// No description provided for @pin_new_title.
  ///
  /// In fr, this message translates to:
  /// **'Nouveau code'**
  String get pin_new_title;

  /// No description provided for @pin_new_sub.
  ///
  /// In fr, this message translates to:
  /// **'Choisis un nouveau code à 4 chiffres.'**
  String get pin_new_sub;

  /// No description provided for @pin_confirm_new_title.
  ///
  /// In fr, this message translates to:
  /// **'Confirme le code'**
  String get pin_confirm_new_title;

  /// No description provided for @pin_confirm_new_sub.
  ///
  /// In fr, this message translates to:
  /// **'Saisis à nouveau le nouveau code.'**
  String get pin_confirm_new_sub;

  /// No description provided for @pin_current_wrong.
  ///
  /// In fr, this message translates to:
  /// **'Code actuel incorrect.'**
  String get pin_current_wrong;

  /// No description provided for @pin_mismatch_short.
  ///
  /// In fr, this message translates to:
  /// **'Les codes ne correspondent pas.'**
  String get pin_mismatch_short;

  /// No description provided for @pin_update_failed.
  ///
  /// In fr, this message translates to:
  /// **'Impossible de mettre à jour. Réessaie.'**
  String get pin_update_failed;

  /// No description provided for @pin_updated.
  ///
  /// In fr, this message translates to:
  /// **'Code secret mis à jour ✓'**
  String get pin_updated;

  /// No description provided for @pin_reveal_title.
  ///
  /// In fr, this message translates to:
  /// **'Affiche ton solde'**
  String get pin_reveal_title;

  /// No description provided for @pin_reveal_sub.
  ///
  /// In fr, this message translates to:
  /// **'Saisis ton code secret pour afficher le montant.'**
  String get pin_reveal_sub;

  /// No description provided for @biometric_reason_unlock.
  ///
  /// In fr, this message translates to:
  /// **'Confirme ton identité pour déverrouiller Gathé Finance'**
  String get biometric_reason_unlock;

  /// No description provided for @biometric_reason_enable.
  ///
  /// In fr, this message translates to:
  /// **'Confirme ton empreinte pour activer le déverrouillage rapide'**
  String get biometric_reason_enable;

  /// No description provided for @biometric_signin_title.
  ///
  /// In fr, this message translates to:
  /// **'Déverrouillage'**
  String get biometric_signin_title;

  /// No description provided for @biometric_hint.
  ///
  /// In fr, this message translates to:
  /// **'Vérifie ton empreinte'**
  String get biometric_hint;

  /// No description provided for @biometric_cancel_button.
  ///
  /// In fr, this message translates to:
  /// **'Utiliser le code'**
  String get biometric_cancel_button;

  /// No description provided for @releve_pdf_title.
  ///
  /// In fr, this message translates to:
  /// **'Relevé de compte'**
  String get releve_pdf_title;

  /// No description provided for @releve_pdf_member.
  ///
  /// In fr, this message translates to:
  /// **'Membre'**
  String get releve_pdf_member;

  /// No description provided for @releve_pdf_number.
  ///
  /// In fr, this message translates to:
  /// **'N° membre'**
  String get releve_pdf_number;

  /// No description provided for @releve_pdf_issued_on.
  ///
  /// In fr, this message translates to:
  /// **'Édité le {date}'**
  String releve_pdf_issued_on(String date);

  /// No description provided for @releve_pdf_balance.
  ///
  /// In fr, this message translates to:
  /// **'Solde épargne'**
  String get releve_pdf_balance;

  /// No description provided for @releve_pdf_rate.
  ///
  /// In fr, this message translates to:
  /// **'Taux d\'intérêt mensuel'**
  String get releve_pdf_rate;

  /// No description provided for @releve_pdf_total_contrib.
  ///
  /// In fr, this message translates to:
  /// **'Total épargne validée'**
  String get releve_pdf_total_contrib;

  /// No description provided for @releve_pdf_tx_header.
  ///
  /// In fr, this message translates to:
  /// **'Opérations d\'épargne'**
  String get releve_pdf_tx_header;

  /// No description provided for @releve_pdf_col_date.
  ///
  /// In fr, this message translates to:
  /// **'Date'**
  String get releve_pdf_col_date;

  /// No description provided for @releve_pdf_col_label.
  ///
  /// In fr, this message translates to:
  /// **'Libellé'**
  String get releve_pdf_col_label;

  /// No description provided for @releve_pdf_col_amount.
  ///
  /// In fr, this message translates to:
  /// **'Montant'**
  String get releve_pdf_col_amount;

  /// No description provided for @releve_pdf_footer.
  ///
  /// In fr, this message translates to:
  /// **'Document généré par l\'application Gathé Finance — à titre informatif.'**
  String get releve_pdf_footer;

  /// No description provided for @releve_pdf_filename.
  ///
  /// In fr, this message translates to:
  /// **'releve_gathe'**
  String get releve_pdf_filename;

  /// No description provided for @common_done.
  ///
  /// In fr, this message translates to:
  /// **'Terminé'**
  String get common_done;

  /// No description provided for @common_understood.
  ///
  /// In fr, this message translates to:
  /// **'Compris'**
  String get common_understood;

  /// No description provided for @common_amount.
  ///
  /// In fr, this message translates to:
  /// **'Montant'**
  String get common_amount;

  /// No description provided for @common_operator.
  ///
  /// In fr, this message translates to:
  /// **'Opérateur'**
  String get common_operator;

  /// No description provided for @common_number.
  ///
  /// In fr, this message translates to:
  /// **'Numéro'**
  String get common_number;

  /// No description provided for @err_enter_amount.
  ///
  /// In fr, this message translates to:
  /// **'Saisis un montant.'**
  String get err_enter_amount;

  /// No description provided for @err_min_100.
  ///
  /// In fr, this message translates to:
  /// **'Minimum 100 XAF.'**
  String get err_min_100;

  /// No description provided for @err_number_incomplete.
  ///
  /// In fr, this message translates to:
  /// **'Numéro incomplet.'**
  String get err_number_incomplete;

  /// No description provided for @dep_title.
  ///
  /// In fr, this message translates to:
  /// **'Verser mon épargne'**
  String get dep_title;

  /// No description provided for @dep_how.
  ///
  /// In fr, this message translates to:
  /// **'Comment veux-tu verser aujourd\'hui ?'**
  String get dep_how;

  /// No description provided for @dep_mobile_money.
  ///
  /// In fr, this message translates to:
  /// **'Mobile Money'**
  String get dep_mobile_money;

  /// No description provided for @dep_mobile_sub.
  ///
  /// In fr, this message translates to:
  /// **'Paiement immédiat via Tara · 24h/24'**
  String get dep_mobile_sub;

  /// No description provided for @dep_agency.
  ///
  /// In fr, this message translates to:
  /// **'À l\'agence'**
  String get dep_agency;

  /// No description provided for @dep_agency_sub.
  ///
  /// In fr, this message translates to:
  /// **'Akwa Bercy · Lun–Ven · 08h00 – 17h00'**
  String get dep_agency_sub;

  /// No description provided for @dep_cutoff_note.
  ///
  /// In fr, this message translates to:
  /// **'Heure limite quotidienne : 17h00. Après ou en week-end, le versement est crédité au prochain jour ouvré.'**
  String get dep_cutoff_note;

  /// No description provided for @dep_agency_title.
  ///
  /// In fr, this message translates to:
  /// **'On te garde une place à l\'agence'**
  String get dep_agency_title;

  /// No description provided for @dep_agency_body.
  ///
  /// In fr, this message translates to:
  /// **'Présente-toi à GATHE FINANCE, Akwa Douala Bercy, avec ton numéro de membre. L\'agent enregistre ton versement et le crédit apparaît immédiatement.'**
  String get dep_agency_body;

  /// No description provided for @dep_agency_place.
  ///
  /// In fr, this message translates to:
  /// **'Akwa, Douala — Bercy'**
  String get dep_agency_place;

  /// No description provided for @dep_agency_hours.
  ///
  /// In fr, this message translates to:
  /// **'Lun–Ven · 08h00 – 17h00'**
  String get dep_agency_hours;

  /// No description provided for @dep_agency_cutoff.
  ///
  /// In fr, this message translates to:
  /// **'Cut-off journalier 17h00'**
  String get dep_agency_cutoff;

  /// No description provided for @dep_suggestion.
  ///
  /// In fr, this message translates to:
  /// **'Suggestion : 1 000 FCFA. Tu restes libre du montant.'**
  String get dep_suggestion;

  /// No description provided for @classic_dep_title.
  ///
  /// In fr, this message translates to:
  /// **'Déposer sur l\'épargne'**
  String get classic_dep_title;

  /// No description provided for @classic_dep_sub.
  ///
  /// In fr, this message translates to:
  /// **'Épargne classique — montant libre, séparé de ton épargne journalière.'**
  String get classic_dep_sub;

  /// No description provided for @classic_card_title.
  ///
  /// In fr, this message translates to:
  /// **'Épargne classique'**
  String get classic_card_title;

  /// No description provided for @classic_card_sub.
  ///
  /// In fr, this message translates to:
  /// **'Mets de côté quand tu veux'**
  String get classic_card_sub;

  /// No description provided for @classic_card_cta.
  ///
  /// In fr, this message translates to:
  /// **'Déposer'**
  String get classic_card_cta;

  /// No description provided for @dep_confirm_default.
  ///
  /// In fr, this message translates to:
  /// **'Confirmer le versement'**
  String get dep_confirm_default;

  /// No description provided for @dep_confirm_amount.
  ///
  /// In fr, this message translates to:
  /// **'Verser {amount}'**
  String dep_confirm_amount(String amount);

  /// No description provided for @dep_waiting_title.
  ///
  /// In fr, this message translates to:
  /// **'En attente de ta confirmation…'**
  String get dep_waiting_title;

  /// No description provided for @dep_waiting_body.
  ///
  /// In fr, this message translates to:
  /// **'Un code te sera envoyé sur ton {network}.\nSaisis ton PIN pour valider {amount}.'**
  String dep_waiting_body(String network, String amount);

  /// No description provided for @dep_waiting_hint.
  ///
  /// In fr, this message translates to:
  /// **'Cela peut prendre quelques secondes'**
  String get dep_waiting_hint;

  /// No description provided for @dep_done_title.
  ///
  /// In fr, this message translates to:
  /// **'Versement confirmé'**
  String get dep_done_title;

  /// No description provided for @dep_done_body.
  ///
  /// In fr, this message translates to:
  /// **'{amount} ont été crédités\nsur ton compte d\'épargne.'**
  String dep_done_body(String amount);

  /// No description provided for @lreq_title.
  ///
  /// In fr, this message translates to:
  /// **'Demander un crédit'**
  String get lreq_title;

  /// No description provided for @lreq_intro.
  ///
  /// In fr, this message translates to:
  /// **'La durée et l\'échéancier sont fixés par le règlement à partir du montant.'**
  String get lreq_intro;

  /// No description provided for @lreq_amount.
  ///
  /// In fr, this message translates to:
  /// **'Montant souhaité'**
  String get lreq_amount;

  /// No description provided for @lreq_modality.
  ///
  /// In fr, this message translates to:
  /// **'Modalité de remboursement'**
  String get lreq_modality;

  /// No description provided for @lreq_motive.
  ///
  /// In fr, this message translates to:
  /// **'Motif de la demande'**
  String get lreq_motive;

  /// No description provided for @lreq_motive_hint.
  ///
  /// In fr, this message translates to:
  /// **'Explique ton projet — équipement, fonds de roulement, formation, etc.'**
  String get lreq_motive_hint;

  /// No description provided for @lreq_motive_short.
  ///
  /// In fr, this message translates to:
  /// **'Motivation trop courte (min 10 caractères).'**
  String get lreq_motive_short;

  /// No description provided for @lreq_fees_note.
  ///
  /// In fr, this message translates to:
  /// **'Des frais de dossier (5 000 XAF) seront à régler après acceptation.'**
  String get lreq_fees_note;

  /// No description provided for @lreq_submit.
  ///
  /// In fr, this message translates to:
  /// **'Soumettre la demande'**
  String get lreq_submit;

  /// No description provided for @lreq_sending.
  ///
  /// In fr, this message translates to:
  /// **'Envoi en cours…'**
  String get lreq_sending;

  /// No description provided for @lreq_sent_title.
  ///
  /// In fr, this message translates to:
  /// **'Demande envoyée'**
  String get lreq_sent_title;

  /// No description provided for @lreq_sent_body.
  ///
  /// In fr, this message translates to:
  /// **'Règle les frais de dossier pour que ton dossier soit instruit par le comité.'**
  String get lreq_sent_body;

  /// No description provided for @lreq_schedule.
  ///
  /// In fr, this message translates to:
  /// **'Ton échéancier'**
  String get lreq_schedule;

  /// No description provided for @lreq_duration.
  ///
  /// In fr, this message translates to:
  /// **'Durée'**
  String get lreq_duration;

  /// No description provided for @lreq_interest.
  ///
  /// In fr, this message translates to:
  /// **'Intérêts (10 %)'**
  String get lreq_interest;

  /// No description provided for @lreq_total.
  ///
  /// In fr, this message translates to:
  /// **'Total à rembourser'**
  String get lreq_total;

  /// No description provided for @rep_title.
  ///
  /// In fr, this message translates to:
  /// **'Rembourser mon crédit'**
  String get rep_title;

  /// No description provided for @rep_installment_n.
  ///
  /// In fr, this message translates to:
  /// **'Échéance n°{n}'**
  String rep_installment_n(String n);

  /// No description provided for @rep_remaining_due.
  ///
  /// In fr, this message translates to:
  /// **'Restant dû : {amount}'**
  String rep_remaining_due(String amount);

  /// No description provided for @rep_operator_mm.
  ///
  /// In fr, this message translates to:
  /// **'Opérateur Mobile Money'**
  String get rep_operator_mm;

  /// No description provided for @rep_confirm.
  ///
  /// In fr, this message translates to:
  /// **'Confirmer le remboursement'**
  String get rep_confirm;

  /// No description provided for @rep_waiting_body.
  ///
  /// In fr, this message translates to:
  /// **'Saisis ton code PIN {network}\npour valider le remboursement.'**
  String rep_waiting_body(String network);

  /// No description provided for @rep_done_title.
  ///
  /// In fr, this message translates to:
  /// **'Remboursement imputé'**
  String get rep_done_title;

  /// No description provided for @rep_done_body.
  ///
  /// In fr, this message translates to:
  /// **'{amount} ont été imputés en FIFO\nsur tes échéances.'**
  String rep_done_body(String amount);

  /// No description provided for @ren_title.
  ///
  /// In fr, this message translates to:
  /// **'Reconduire mon crédit'**
  String get ren_title;

  /// No description provided for @ren_subtitle.
  ///
  /// In fr, this message translates to:
  /// **'Crédit {dossier} — solde restant {amount}.'**
  String ren_subtitle(String dossier, String amount);

  /// No description provided for @ren_extra_month.
  ///
  /// In fr, this message translates to:
  /// **'Prolongation : +1 mois'**
  String get ren_extra_month;

  /// No description provided for @ren_mode_question.
  ///
  /// In fr, this message translates to:
  /// **'Comment règles-tu les intérêts ?'**
  String get ren_mode_question;

  /// No description provided for @ren_mode_comptant.
  ///
  /// In fr, this message translates to:
  /// **'Au comptant — 10 %'**
  String get ren_mode_comptant;

  /// No description provided for @ren_mode_comptant_sub.
  ///
  /// In fr, this message translates to:
  /// **'Tu verses les intérêts maintenant. Taux réduit sur le capital restant.'**
  String get ren_mode_comptant_sub;

  /// No description provided for @ren_mode_reporte.
  ///
  /// In fr, this message translates to:
  /// **'Reportés — 15 %'**
  String get ren_mode_reporte;

  /// No description provided for @ren_mode_reporte_sub.
  ///
  /// In fr, this message translates to:
  /// **'Les intérêts sont reportés avec le capital. Taux majoré.'**
  String get ren_mode_reporte_sub;

  /// No description provided for @ren_recap_interest.
  ///
  /// In fr, this message translates to:
  /// **'Intérêts de reconduction'**
  String get ren_recap_interest;

  /// No description provided for @ren_recap_total.
  ///
  /// In fr, this message translates to:
  /// **'Nouveau total à rembourser'**
  String get ren_recap_total;

  /// No description provided for @ren_fees_note.
  ///
  /// In fr, this message translates to:
  /// **'La reconduction prolonge ton crédit d\'un mois. Aucun frais de dossier n\'est dû : seuls les intérêts de reconduction, calculés sur le capital restant, s\'ajoutent. Ta demande sera soumise au comité pour validation.'**
  String get ren_fees_note;

  /// No description provided for @ren_submit.
  ///
  /// In fr, this message translates to:
  /// **'Demander la reconduction'**
  String get ren_submit;

  /// No description provided for @ren_sent_body.
  ///
  /// In fr, this message translates to:
  /// **'Ta demande de reconduction (+1 mois) a bien été envoyée.\nElle est en attente de validation du comité.'**
  String get ren_sent_body;

  /// No description provided for @lreq_installments.
  ///
  /// In fr, this message translates to:
  /// **'{n} échéances'**
  String lreq_installments(String n);

  /// No description provided for @lreq_per_time.
  ///
  /// In fr, this message translates to:
  /// **'{amount} / fois'**
  String lreq_per_time(String amount);

  /// No description provided for @common_modify.
  ///
  /// In fr, this message translates to:
  /// **'Modifier'**
  String get common_modify;

  /// No description provided for @common_firstname.
  ///
  /// In fr, this message translates to:
  /// **'Prénom'**
  String get common_firstname;

  /// No description provided for @common_lastname.
  ///
  /// In fr, this message translates to:
  /// **'Nom'**
  String get common_lastname;

  /// No description provided for @common_phone.
  ///
  /// In fr, this message translates to:
  /// **'Téléphone'**
  String get common_phone;

  /// No description provided for @common_email.
  ///
  /// In fr, this message translates to:
  /// **'Email'**
  String get common_email;

  /// No description provided for @prof_logout_q.
  ///
  /// In fr, this message translates to:
  /// **'Se déconnecter ?'**
  String get prof_logout_q;

  /// No description provided for @prof_logout_body.
  ///
  /// In fr, this message translates to:
  /// **'Tu devras te reconnecter avec ton email et ton mot de passe.'**
  String get prof_logout_body;

  /// No description provided for @prof_logout_confirm.
  ///
  /// In fr, this message translates to:
  /// **'Oui, me déconnecter'**
  String get prof_logout_confirm;

  /// No description provided for @prof_member_num.
  ///
  /// In fr, this message translates to:
  /// **'Membre · {n}'**
  String prof_member_num(String n);

  /// No description provided for @myinfo_saved.
  ///
  /// In fr, this message translates to:
  /// **'Informations enregistrées.'**
  String get myinfo_saved;

  /// No description provided for @myinfo_title.
  ///
  /// In fr, this message translates to:
  /// **'Mes informations'**
  String get myinfo_title;

  /// No description provided for @myinfo_sub.
  ///
  /// In fr, this message translates to:
  /// **'Tu peux modifier ces champs depuis l\'app.'**
  String get myinfo_sub;

  /// No description provided for @myinfo_firstname_required.
  ///
  /// In fr, this message translates to:
  /// **'Prénom requis'**
  String get myinfo_firstname_required;

  /// No description provided for @myinfo_lastname_required.
  ///
  /// In fr, this message translates to:
  /// **'Nom requis'**
  String get myinfo_lastname_required;

  /// No description provided for @myinfo_email_locked.
  ///
  /// In fr, this message translates to:
  /// **'Pour changer ton email, contacte le support.'**
  String get myinfo_email_locked;

  /// No description provided for @pwd_title.
  ///
  /// In fr, this message translates to:
  /// **'Mot de passe'**
  String get pwd_title;

  /// No description provided for @pwd_sub.
  ///
  /// In fr, this message translates to:
  /// **'Choisis un nouveau mot de passe d\'au moins 8 caractères.'**
  String get pwd_sub;

  /// No description provided for @pwd_old.
  ///
  /// In fr, this message translates to:
  /// **'Ancien mot de passe'**
  String get pwd_old;

  /// No description provided for @pwd_old_required.
  ///
  /// In fr, this message translates to:
  /// **'Ancien mot de passe requis'**
  String get pwd_old_required;

  /// No description provided for @pwd_new.
  ///
  /// In fr, this message translates to:
  /// **'Nouveau mot de passe'**
  String get pwd_new;

  /// No description provided for @pwd_min_hint.
  ///
  /// In fr, this message translates to:
  /// **'Min 8 caractères'**
  String get pwd_min_hint;

  /// No description provided for @pwd_min_err.
  ///
  /// In fr, this message translates to:
  /// **'Au moins 8 caractères'**
  String get pwd_min_err;

  /// No description provided for @pwd_diff_err.
  ///
  /// In fr, this message translates to:
  /// **'Doit être différent de l\'ancien'**
  String get pwd_diff_err;

  /// No description provided for @pwd_confirm.
  ///
  /// In fr, this message translates to:
  /// **'Confirmation'**
  String get pwd_confirm;

  /// No description provided for @pwd_confirm_hint.
  ///
  /// In fr, this message translates to:
  /// **'Retape le nouveau mot de passe'**
  String get pwd_confirm_hint;

  /// No description provided for @pwd_mismatch.
  ///
  /// In fr, this message translates to:
  /// **'Les mots de passe ne correspondent pas'**
  String get pwd_mismatch;

  /// No description provided for @pwd_done_title.
  ///
  /// In fr, this message translates to:
  /// **'Mot de passe modifié'**
  String get pwd_done_title;

  /// No description provided for @pwd_done_body.
  ///
  /// In fr, this message translates to:
  /// **'Tu utiliseras le nouveau dès la prochaine connexion.'**
  String get pwd_done_body;

  /// No description provided for @bko_title.
  ///
  /// In fr, this message translates to:
  /// **'Commander mon carnet'**
  String get bko_title;

  /// No description provided for @bko_sub.
  ///
  /// In fr, this message translates to:
  /// **'Règle 1 000 XAF via Mobile Money pour lancer l\'impression.'**
  String get bko_sub;

  /// No description provided for @bko_after_note.
  ///
  /// In fr, this message translates to:
  /// **'Une fois ton paiement validé, l\'agence imprime ton carnet et te prévient quand il est prêt.'**
  String get bko_after_note;

  /// No description provided for @bko_pay.
  ///
  /// In fr, this message translates to:
  /// **'Payer 1 000 XAF'**
  String get bko_pay;

  /// No description provided for @bko_waiting_body.
  ///
  /// In fr, this message translates to:
  /// **'Saisis ton code PIN {network}'**
  String bko_waiting_body(String network);

  /// No description provided for @bko_done_title.
  ///
  /// In fr, this message translates to:
  /// **'Commande enregistrée'**
  String get bko_done_title;

  /// No description provided for @mi_eyebrow.
  ///
  /// In fr, this message translates to:
  /// **'Coopérative'**
  String get mi_eyebrow;

  /// No description provided for @mi_intro.
  ///
  /// In fr, this message translates to:
  /// **'Chez Gathe Finance, tu n\'es pas un simple client : tu deviens **copropriétaire** d\'une coopérative d\'épargne et de crédit. Tes décisions comptent, et les bénéfices reviennent aux membres.'**
  String get mi_intro;

  /// No description provided for @mi_card1_title.
  ///
  /// In fr, this message translates to:
  /// **'Épargne sécurisée'**
  String get mi_card1_title;

  /// No description provided for @mi_card1_body.
  ///
  /// In fr, this message translates to:
  /// **'Ton argent est protégé par la coopérative et rémunéré à 1 %/mois sur ton compte d\'épargne.'**
  String get mi_card1_body;

  /// No description provided for @mi_card2_title.
  ///
  /// In fr, this message translates to:
  /// **'Crédit accessible'**
  String get mi_card2_title;

  /// No description provided for @mi_card2_body.
  ///
  /// In fr, this message translates to:
  /// **'Crédit selon ton épargne. Taux 10 % par transaction, durée selon le règlement.'**
  String get mi_card2_body;

  /// No description provided for @mi_card3_title.
  ///
  /// In fr, this message translates to:
  /// **'Voix au chapitre'**
  String get mi_card3_title;

  /// No description provided for @mi_card3_body.
  ///
  /// In fr, this message translates to:
  /// **'Une part = une voix à l\'AG. Tu participes aux décisions de la coopérative.'**
  String get mi_card3_body;

  /// No description provided for @mi_steps_title.
  ///
  /// In fr, this message translates to:
  /// **'Pour devenir membre'**
  String get mi_steps_title;

  /// No description provided for @mi_step1.
  ///
  /// In fr, this message translates to:
  /// **'Soumets ta demande d\'adhésion (formulaire ci-dessous)'**
  String get mi_step1;

  /// No description provided for @mi_step2.
  ///
  /// In fr, this message translates to:
  /// **'Règle les frais d\'adhésion (10 000 + 2 000 FCFA)'**
  String get mi_step2;

  /// No description provided for @mi_step3.
  ///
  /// In fr, this message translates to:
  /// **'Ton compte est activé après l\'entretien d\'admission'**
  String get mi_step3;

  /// No description provided for @mi_submit.
  ///
  /// In fr, this message translates to:
  /// **'Soumettre ma demande'**
  String get mi_submit;

  /// No description provided for @mi_later.
  ///
  /// In fr, this message translates to:
  /// **'Plus tard'**
  String get mi_later;

  /// No description provided for @mf_statut_salarie.
  ///
  /// In fr, this message translates to:
  /// **'Salarié'**
  String get mf_statut_salarie;

  /// No description provided for @mf_statut_commercant.
  ///
  /// In fr, this message translates to:
  /// **'Commerçant'**
  String get mf_statut_commercant;

  /// No description provided for @mf_statut_artisan.
  ///
  /// In fr, this message translates to:
  /// **'Artisan'**
  String get mf_statut_artisan;

  /// No description provided for @mf_statut_sansemploi.
  ///
  /// In fr, this message translates to:
  /// **'Sans emploi'**
  String get mf_statut_sansemploi;

  /// No description provided for @mf_statut_autre.
  ///
  /// In fr, this message translates to:
  /// **'Autre'**
  String get mf_statut_autre;

  /// No description provided for @mf_title.
  ///
  /// In fr, this message translates to:
  /// **'Devenir membre'**
  String get mf_title;

  /// No description provided for @mf_intro.
  ///
  /// In fr, this message translates to:
  /// **'Remplis ta demande. Tu seras ensuite convoqué à un entretien d\'admission.'**
  String get mf_intro;

  /// No description provided for @mf_section_identity.
  ///
  /// In fr, this message translates to:
  /// **'Identité'**
  String get mf_section_identity;

  /// No description provided for @mf_section_contact.
  ///
  /// In fr, this message translates to:
  /// **'Coordonnées'**
  String get mf_section_contact;

  /// No description provided for @mf_section_location.
  ///
  /// In fr, this message translates to:
  /// **'Localisation'**
  String get mf_section_location;

  /// No description provided for @mf_section_statut.
  ///
  /// In fr, this message translates to:
  /// **'Statut professionnel'**
  String get mf_section_statut;

  /// No description provided for @mf_section_urgence.
  ///
  /// In fr, this message translates to:
  /// **'Contact en cas d\'urgence'**
  String get mf_section_urgence;

  /// No description provided for @mf_section_motivation.
  ///
  /// In fr, this message translates to:
  /// **'Motivation (optionnel)'**
  String get mf_section_motivation;

  /// No description provided for @mf_whatsapp.
  ///
  /// In fr, this message translates to:
  /// **'WhatsApp (optionnel)'**
  String get mf_whatsapp;

  /// No description provided for @mf_city.
  ///
  /// In fr, this message translates to:
  /// **'Ville'**
  String get mf_city;

  /// No description provided for @mf_quartier.
  ///
  /// In fr, this message translates to:
  /// **'Quartier / lieu précis'**
  String get mf_quartier;

  /// No description provided for @mf_urgence_nom.
  ///
  /// In fr, this message translates to:
  /// **'Nom & prénom'**
  String get mf_urgence_nom;

  /// No description provided for @mf_urgence_lien.
  ///
  /// In fr, this message translates to:
  /// **'Lien (parent…)'**
  String get mf_urgence_lien;

  /// No description provided for @mf_statut.
  ///
  /// In fr, this message translates to:
  /// **'Statut'**
  String get mf_statut;

  /// No description provided for @mf_motivation_q.
  ///
  /// In fr, this message translates to:
  /// **'Quelle est votre motivation ?'**
  String get mf_motivation_q;

  /// No description provided for @mf_submit.
  ///
  /// In fr, this message translates to:
  /// **'Envoyer ma demande'**
  String get mf_submit;

  /// No description provided for @mf_email_invalid.
  ///
  /// In fr, this message translates to:
  /// **'Email invalide'**
  String get mf_email_invalid;

  /// No description provided for @mf_fees_note.
  ///
  /// In fr, this message translates to:
  /// **'Frais à régler à l\'adhésion : 10 000 FCFA (adhésion) + 2 000 FCFA (inscription).'**
  String get mf_fees_note;

  /// No description provided for @mf_sending.
  ///
  /// In fr, this message translates to:
  /// **'Envoi de ta demande…'**
  String get mf_sending;

  /// No description provided for @mf_sent_title.
  ///
  /// In fr, this message translates to:
  /// **'Demande envoyée'**
  String get mf_sent_title;

  /// No description provided for @mf_sent_body.
  ///
  /// In fr, this message translates to:
  /// **'La coopérative va étudier ton dossier et te convoquer à un entretien d\'admission.'**
  String get mf_sent_body;
}

class _AppL10nDelegate extends LocalizationsDelegate<AppL10n> {
  const _AppL10nDelegate();

  @override
  Future<AppL10n> load(Locale locale) {
    return SynchronousFuture<AppL10n>(lookupAppL10n(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en', 'fr'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppL10nDelegate old) => false;
}

AppL10n lookupAppL10n(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return AppL10nEn();
    case 'fr':
      return AppL10nFr();
  }

  throw FlutterError(
      'AppL10n.delegate failed to load unsupported locale "$locale". This is likely '
      'an issue with the localizations generation tool. Please file an issue '
      'on GitHub with a reproducible sample app and the gen-l10n configuration '
      'that was used.');
}
