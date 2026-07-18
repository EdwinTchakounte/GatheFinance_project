// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppL10nEn extends AppL10n {
  AppL10nEn([String locale = 'en']) : super(locale);

  @override
  String get appTitle => 'GATHE Finance';

  @override
  String get common_continue => 'Continue';

  @override
  String get common_cancel => 'Cancel';

  @override
  String get common_save => 'Save';

  @override
  String get common_close => 'Close';

  @override
  String get common_retry => 'Retry';

  @override
  String get common_back => 'Back';

  @override
  String get common_loading => 'Loading…';

  @override
  String get common_required => 'Required';

  @override
  String get error_generic_title => 'Something went wrong';

  @override
  String get error_generic_body =>
      'We couldn\'t load this data right now. Check your connection and try again.';

  @override
  String get nav_home => 'Home';

  @override
  String get nav_credit => 'Credit';

  @override
  String get nav_booklet => 'Passbook';

  @override
  String get nav_profile => 'Profile';

  @override
  String get profile_eyebrow => 'Profile';

  @override
  String get profile_title => 'My account';

  @override
  String get profile_section_finances => 'My finances';

  @override
  String get profile_section_security => 'Account & security';

  @override
  String get profile_section_preferences => 'Preferences';

  @override
  String get profile_member_badge => 'Member';

  @override
  String get profile_tile_states => 'My statements';

  @override
  String get profile_tile_states_sub => 'Balance, outstanding, seniority.';

  @override
  String get profile_tile_contributions => 'My fees';

  @override
  String get profile_tile_contributions_sub =>
      'History of fees paid to the cooperative.';

  @override
  String get profile_tile_lender => 'Lender space';

  @override
  String get profile_tile_lender_sub => 'Agreement, tranches and 24h requests.';

  @override
  String get profile_tile_info => 'My information';

  @override
  String get profile_tile_info_sub => 'Name, email, phone.';

  @override
  String get profile_tile_password => 'Security & password';

  @override
  String get profile_tile_password_sub => 'Change your password.';

  @override
  String get profile_tile_notifications => 'Notifications';

  @override
  String get profile_tile_notifications_sub => 'Push, email, SMS.';

  @override
  String get profile_tile_theme => 'Theme';

  @override
  String get profile_tile_theme_sub => 'Light, dark or automatic.';

  @override
  String get profile_tile_language => 'Language';

  @override
  String get profile_tile_language_sub => 'Français, English.';

  @override
  String get profile_tile_help => 'Help & contact';

  @override
  String get profile_tile_help_sub => 'FAQ, support, branch.';

  @override
  String get profile_logout => 'Sign out';

  @override
  String get theme_choice_title => 'Choose theme';

  @override
  String get theme_choice_desc =>
      'Select the look of the app. The setting is kept on this device.';

  @override
  String get theme_auto => 'Automatic';

  @override
  String get theme_auto_desc => 'Follows your phone\'s settings.';

  @override
  String get theme_light => 'Light';

  @override
  String get theme_light_desc => 'Cream surfaces and cobalt accents.';

  @override
  String get theme_dark => 'Dark';

  @override
  String get theme_dark_desc => 'Night-friendly, deep cobalt surfaces.';

  @override
  String get language_choice_title => 'Choose language';

  @override
  String get language_choice_desc =>
      'The app will be displayed in the selected language.';

  @override
  String get language_french => 'Français';

  @override
  String get language_english => 'English';

  @override
  String get home_eyebrow => 'Member area';

  @override
  String get home_greeting_night => 'Good night';

  @override
  String get home_greeting_morning => 'Good morning';

  @override
  String get home_greeting_afternoon => 'Good afternoon';

  @override
  String get home_greeting_evening => 'Good evening';

  @override
  String get home_account_active => 'Account active';

  @override
  String get home_my_savings => 'My savings';

  @override
  String home_delta_week(String sign, String amount) {
    return '$sign $amount XAF over the last 7 days';
  }

  @override
  String get home_no_movement_week => 'No movement this week.';

  @override
  String get home_deposit => 'Deposit my savings';

  @override
  String get home_history => 'History';

  @override
  String get home_my_services => 'My services';

  @override
  String get home_my_services_sub => 'Everything one tap away.';

  @override
  String get home_request_credit => 'Request a loan';

  @override
  String get home_order_booklet => 'Order my passbook';

  @override
  String get home_repay => 'Repay an installment';

  @override
  String get home_last_operations => 'Latest operations';

  @override
  String get home_no_operations => 'No operation yet.';

  @override
  String get home_history_unavailable => 'History unavailable.';

  @override
  String get home_hero_eyebrow => 'At your pace';

  @override
  String get home_hero_title => 'Building,\nstep by step, together.';

  @override
  String get home_hero_subtitle =>
      'The cooperative walks with you for the long run. Lay the foundations of a solid heritage.';

  @override
  String get home_balance_unavailable => 'Balance unavailable';

  @override
  String get common_see_all => 'See all';

  @override
  String get tx_deposit => 'Savings deposit';

  @override
  String get tx_deposit_cotisation => 'Daily collection';

  @override
  String get tx_withdrawal => 'Withdrawal';

  @override
  String get tx_interest => 'Interest credited';

  @override
  String tx_balance_after(String amount) {
    return 'Balance $amount';
  }

  @override
  String get login_title => 'Welcome back';

  @override
  String get login_subtitle => 'Manage your savings, track your loans.';

  @override
  String get login_sub_under_title => 'Sign in to access your account.';

  @override
  String get login_email_label => 'Email address';

  @override
  String get login_email_hint => 'you@example.com';

  @override
  String get login_email_required => 'Email address required.';

  @override
  String get login_email_invalid => 'Invalid format.';

  @override
  String get login_password_label => 'Password';

  @override
  String get login_password_required => 'Password required.';

  @override
  String get login_show_password => 'Show';

  @override
  String get login_hide_password => 'Hide';

  @override
  String get login_forgot_password => 'Forgot password?';

  @override
  String get login_submit => 'Sign in';

  @override
  String get login_become_member => 'Become a member';

  @override
  String get login_not_member => 'Not a member yet?';

  @override
  String get login_security_tip =>
      'Your session is encrypted. No sensitive information is stored in plain text on the device.';

  @override
  String get common_or => 'OR';

  @override
  String get onb_eyebrow_welcome => 'Welcome';

  @override
  String get onb_skip => 'Skip';

  @override
  String get onb_continue => 'Continue';

  @override
  String get onb_start => 'Get started';

  @override
  String get onb_consent =>
      'By continuing you accept the cooperative\'s terms.';

  @override
  String get onb_slide1_eyebrow => 'Savings';

  @override
  String get onb_slide1_title => 'Your savings,\none step at a time.';

  @override
  String get onb_slide1_body =>
      'Deposit in seconds via Mobile Money. Track your balance and interest from your phone.';

  @override
  String get onb_slide2_eyebrow => 'Credit';

  @override
  String get onb_slide2_title => 'Finance your projects\nat cooperative rates.';

  @override
  String get onb_slide2_body =>
      'Request a loan based on your savings. Receive disbursement directly on your Mobile Money number.';

  @override
  String get onb_slide3_eyebrow => 'Cooperative';

  @override
  String get onb_slide3_title => 'A cooperative owned\nby its members.';

  @override
  String get onb_slide3_body =>
      'Your decisions matter. Enjoy transparent governance and streamlined administrative services.';

  @override
  String get onb_slide4_eyebrow => 'Member';

  @override
  String get onb_slide4_title => 'Not a customer.\nA co-owner.';

  @override
  String get onb_slide4_body =>
      'At GATHE, you don\'t deposit with a third party: you take part in the cooperative, you vote at the assembly and you benefit from redistributed profits.';

  @override
  String get credit_eyebrow => 'Credit';

  @override
  String get credit_title => 'My loans';

  @override
  String get credit_in_progress_eyebrow => 'Active loan';

  @override
  String get credit_status_active => 'Active';

  @override
  String get credit_status_late => 'Late';

  @override
  String get credit_status_closed => 'Closed';

  @override
  String get credit_remaining_balance => 'Remaining balance';

  @override
  String credit_installments_count(int paid, int total) {
    return '$paid / $total installments';
  }

  @override
  String get credit_next_installment => 'Next installment';

  @override
  String credit_see_installments(int count) {
    return 'View the $count installments';
  }

  @override
  String get credit_repay => 'Repay';

  @override
  String get credit_renew => 'Renew';

  @override
  String get credit_meta_duration => 'Duration';

  @override
  String credit_meta_months(int count) {
    return '$count months';
  }

  @override
  String get credit_meta_rate => 'Rate';

  @override
  String credit_meta_rate_value(String rate) {
    return '$rate %/yr';
  }

  @override
  String get credit_meta_disbursed => 'Disbursed';

  @override
  String credit_schedule_for(String ref) {
    return 'Schedule $ref';
  }

  @override
  String credit_schedule_summary(int count, String total) {
    return '$count installments · $total total due';
  }

  @override
  String get credit_empty_eyebrow => 'No loan';

  @override
  String get credit_empty_title => 'No loan yet';

  @override
  String credit_eligible_cap(String cap) {
    return 'Eligible . cap $cap';
  }

  @override
  String get credit_not_eligible => 'Application unavailable';

  @override
  String get credit_requests_title => 'My requests';

  @override
  String get credit_requests_subtitle => 'Committee review status.';

  @override
  String get credit_req_pending => 'Fees to pay';

  @override
  String get credit_req_review => 'Under review';

  @override
  String get credit_req_counter => 'Counter-offer';

  @override
  String get credit_req_approved => 'Approved';

  @override
  String get credit_req_rejected => 'Rejected';

  @override
  String credit_req_amount_duration(String amount, int duration) {
    return '$amount over $duration months';
  }

  @override
  String credit_req_submitted_on(String date) {
    return 'Submitted on $date';
  }

  @override
  String get credit_hero_eyebrow => 'Cooperative';

  @override
  String get credit_hero_title => 'Finance your project\nat member rates.';

  @override
  String get credit_hero_subtitle =>
      'A fair rate, a local committee, decisions close to the ground.';

  @override
  String get credit_error_title => 'Loans unavailable';

  @override
  String get booklet_eyebrow => 'Passbook';

  @override
  String get booklet_title => 'My member passbook';

  @override
  String get booklet_pending_eyebrow => 'Pending order';

  @override
  String get booklet_status_paid => 'Paid';

  @override
  String get booklet_status_printing => 'Printing';

  @override
  String get booklet_status_delivered => 'Delivered';

  @override
  String get booklet_step_payment => 'Paid';

  @override
  String get booklet_step_printing => 'Printing';

  @override
  String get booklet_step_delivered => 'Delivered';

  @override
  String get booklet_hint_paid =>
      'Your payment is confirmed. The branch is preparing your passbook . typically 48 business hours.';

  @override
  String get booklet_hint_printing =>
      'Your passbook is being printed. You\'ll get a notification as soon as it\'s ready to pick up.';

  @override
  String get booklet_hint_delivered => 'Passbook delivered. Thank you!';

  @override
  String get booklet_new_eyebrow_fee => 'Fee 1,000 XAF';

  @override
  String get booklet_new_title => 'Order a new passbook.';

  @override
  String get booklet_step1 => 'Pay 1,000 XAF via Mobile Money.';

  @override
  String get booklet_step2 =>
      'The branch prints your passbook within 48 hours.';

  @override
  String get booklet_step3 => 'Notification on pickup . come collect it.';

  @override
  String get booklet_order_cta => 'Order my passbook';

  @override
  String get booklet_history_title => 'History';

  @override
  String get booklet_history_subtitle => 'Previously delivered passbooks.';

  @override
  String booklet_history_item(String id) {
    return 'Passbook $id';
  }

  @override
  String booklet_history_delivered_on(String date) {
    return 'Delivered on $date';
  }

  @override
  String get booklet_error_title => 'Passbook unavailable';

  @override
  String get booklet_active_title => 'Active passbook';

  @override
  String booklet_active_subtitle(String date) {
    return 'Delivered on $date. Use it for deposits at the agency.';
  }

  @override
  String get booklet_active_reorder_hint =>
      'Passbook exhausted? Order a new one';

  @override
  String get notifs_title => 'Notifications';

  @override
  String get notifs_mark_all_read => 'Mark all read';

  @override
  String get notifs_unavailable => 'Notifications unavailable';

  @override
  String get notifs_empty_title => 'No notifications';

  @override
  String get notifs_empty_sub =>
      'Everything is up to date on the cooperative side.';

  @override
  String notifs_rel_minutes(int n) {
    return '$n min ago';
  }

  @override
  String notifs_rel_hours(int n) {
    return '$n h ago';
  }

  @override
  String notifs_rel_days(int n) {
    return '$n d ago';
  }

  @override
  String get savings_history_eyebrow => 'My savings';

  @override
  String get savings_history_title => 'History';

  @override
  String get savings_range_all => 'All';

  @override
  String get savings_range_this_month => 'This month';

  @override
  String get savings_range_last3 => '3 months';

  @override
  String get savings_range_last6 => '6 months';

  @override
  String get savings_type_all => 'All';

  @override
  String get savings_type_deposits => 'Deposits';

  @override
  String get savings_type_interest => 'Interest';

  @override
  String get savings_type_withdrawals => 'Withdrawals';

  @override
  String get savings_search_hint => 'Search an amount…';

  @override
  String get savings_empty_amount => 'No operation matches this amount.';

  @override
  String get savings_empty_period => 'No operation in this period.';

  @override
  String get savings_nothing_title => 'Nothing to display';

  @override
  String get savings_history_unavailable => 'History unavailable';

  @override
  String get contrib_eyebrow => 'Profile';

  @override
  String get contrib_title => 'My fees';

  @override
  String get contrib_total_label => 'Total paid to the cooperative';

  @override
  String get contrib_type_inscription => 'Registration fees';

  @override
  String get contrib_type_adhesion => 'Membership fees';

  @override
  String get contrib_type_credit_request => 'Loan application fees';

  @override
  String get contrib_type_renewal => 'Renewal fees';

  @override
  String get contrib_type_booklet => 'Passbook fees';

  @override
  String get contrib_status_validated => 'Validated';

  @override
  String get contrib_status_pending => 'Pending';

  @override
  String get contrib_status_failed => 'Failed';

  @override
  String contrib_ref(String ref) {
    return 'Ref. $ref';
  }

  @override
  String get contrib_empty_title => 'No payment yet';

  @override
  String get contrib_empty_sub =>
      'Fees you pay to the cooperative will show up here.';

  @override
  String get contrib_error_title => 'Fees unavailable';

  @override
  String get states_title => 'My statements';

  @override
  String get states_releve_eyebrow => 'Member statement';

  @override
  String get states_releve_official => 'Official';

  @override
  String states_releve_on(String date) {
    return 'As of $date';
  }

  @override
  String states_member_since(String date) {
    return 'Member since $date.';
  }

  @override
  String get states_glance => 'At a glance';

  @override
  String get states_kpi_savings => 'Savings balance';

  @override
  String get states_kpi_credit => 'Outstanding loan';

  @override
  String get states_no_active_credit => 'No active loan';

  @override
  String get states_kpi_contributions => 'Collection balance';

  @override
  String get states_kpi_seniority => 'Seniority';

  @override
  String get states_savings_detail => 'Savings in detail';

  @override
  String get states_balance_today => 'Balance today';

  @override
  String get states_interest_rate => 'Interest rate served';

  @override
  String get states_account_opened => 'Account opened on';

  @override
  String get states_movements => 'Movements recorded';

  @override
  String get states_contrib_detail_title => 'My contributions detail';

  @override
  String get states_contrib_detail_sub => 'View the timeline of paid fees.';

  @override
  String get states_pdf_soon => 'PDF generation coming soon.';

  @override
  String get states_download_pdf => 'Download my PDF statement';

  @override
  String states_years(int n, String s) {
    return '$n year$s';
  }

  @override
  String states_months_total(int n) {
    return '$n months total';
  }

  @override
  String states_months(int n) {
    return '$n months';
  }

  @override
  String states_days_long(int n) {
    return '$n days';
  }

  @override
  String states_days_short(int n) {
    return '$n d';
  }

  @override
  String get states_since_join => 'since joining';

  @override
  String get common_unavailable => 'Unavailable';

  @override
  String get help_eyebrow => 'Profile';

  @override
  String get help_copy_a11y => 'tap to copy';

  @override
  String get help_title => 'Help & contact';

  @override
  String get help_intro_title => 'A question? We\'re here.';

  @override
  String get help_intro_sub =>
      'Find a quick answer in the FAQ or reach the team directly via WhatsApp, phone or email.';

  @override
  String get help_faq_section => 'Frequently asked questions';

  @override
  String get help_contact_section => 'Contact us';

  @override
  String get help_faq1_q => 'How do I make a deposit to my savings account?';

  @override
  String get help_faq1_a =>
      'From Home, tap \"Deposit\" then choose the amount. Payment goes through Tara (Mobile Money). Once validated, your balance is credited automatically.';

  @override
  String get help_faq2_q => 'When can I apply for a loan?';

  @override
  String get help_faq2_a =>
      'After 3 months of regular saving (per the cooperative\'s bylaws). The maximum amount depends on your balance and history. Go to the \"Credit\" tab to start an application.';

  @override
  String get help_faq3_q => 'How does loan renewal work?';

  @override
  String get help_faq3_a =>
      'As your loan nears maturity, you can request renewal. The committee reviews the request within 72h. Renewal fees are set by the cooperative.';

  @override
  String get help_faq4_q => 'How do I pick up my passbook at the branch?';

  @override
  String get help_faq4_a =>
      'Once the order is validated and fees paid, show up at the branch with your ID. An agent will hand over your official passbook.';

  @override
  String get help_faq5_q => 'Is my money safe?';

  @override
  String get help_faq5_a =>
      'Yes. All funds are held in the cooperative account at a licensed credit institution. Transactions are tracked and audited every quarter.';

  @override
  String get help_contact_whatsapp => 'WhatsApp';

  @override
  String get help_contact_phone => 'Phone';

  @override
  String get help_contact_landline => 'Landline';

  @override
  String get help_contact_email => 'Email';

  @override
  String get help_contact_agency => 'Branch';

  @override
  String get help_contact_hours => 'Opening hours';

  @override
  String get help_copied_whatsapp => 'WhatsApp number copied';

  @override
  String get help_copied_phone => 'Number copied';

  @override
  String get help_copied_landline => 'Landline copied';

  @override
  String get help_copied_email => 'Email copied';

  @override
  String get help_copied_agency => 'Address copied';

  @override
  String get notifprefs_eyebrow => 'Preferences';

  @override
  String get notifprefs_title => 'Notifications';

  @override
  String get notifprefs_intro_title => 'How would you like to be notified?';

  @override
  String get notifprefs_intro_sub =>
      'Toggle each channel (Push, Email, SMS) on or off for every cooperative event.';

  @override
  String get notifprefs_cat_epargne => 'Savings';

  @override
  String get notifprefs_cat_credit => 'Credit';

  @override
  String get notifprefs_cat_carnet => 'Passbook';

  @override
  String get notifprefs_cat_reconduction => 'Renewal';

  @override
  String get notifprefs_cat_securite => 'Security';

  @override
  String get notifprefs_cat_epargne_sub =>
      'Validated deposits, credited interest, balance alerts.';

  @override
  String get notifprefs_cat_credit_sub =>
      'Application, committee decision, disbursement, installments.';

  @override
  String get notifprefs_cat_carnet_sub => 'Order, branch pickup.';

  @override
  String get notifprefs_cat_reconduction_sub =>
      'Committee, fees due, validation.';

  @override
  String get notifprefs_cat_securite_sub =>
      'Sign-ins, password changes, suspicious access.';

  @override
  String get notifprefs_chan_push => 'Push';

  @override
  String get notifprefs_chan_email => 'Email';

  @override
  String get notifprefs_chan_sms => 'SMS';

  @override
  String get notifprefs_unavailable => 'Preferences unavailable';

  @override
  String get splash_eyebrow => 'SAVINGS & CREDIT COOPERATIVE';

  @override
  String get splash_loading => 'Preparing your space…';

  @override
  String get inst_status_paid => 'Paid';

  @override
  String get inst_status_upcoming => 'Upcoming';

  @override
  String get inst_status_late => 'Late';

  @override
  String get inst_status_partial => 'Partial';

  @override
  String inst_due_on(String date) {
    return 'Due $date';
  }

  @override
  String inst_capital_interest(String capital, String interest) {
    return 'Capital $capital · Interest $interest';
  }

  @override
  String get home_action_deposit => 'Deposit';

  @override
  String get home_action_savings => 'Savings';

  @override
  String get home_action_cotisation => 'Collection';

  @override
  String get home_action_credit => 'Loan';

  @override
  String get home_action_booklet => 'Booklet';

  @override
  String get home_action_history => 'History';

  @override
  String get home_recent_ops => 'Recent activity';

  @override
  String get home_see_all => 'See all';

  @override
  String get home_balance_label => 'Savings balance';

  @override
  String home_delta_this_month(String value) {
    return '$value this month';
  }

  @override
  String get carousel_save_title => 'Save every day';

  @override
  String get carousel_save_sub => '1,000 FCFA/day earning 1% per month.';

  @override
  String get carousel_save_cta => 'Deposit';

  @override
  String get carousel_credit_title => 'Need a loan?';

  @override
  String get carousel_credit_sub => '10% rate · term based on amount.';

  @override
  String get carousel_credit_cta => 'Request';

  @override
  String get carousel_booklet_title => 'Order your booklet';

  @override
  String get carousel_booklet_sub => 'Collection booklet for 1,000 FCFA.';

  @override
  String get carousel_booklet_cta => 'Order';

  @override
  String get carousel_help_title => 'Help & contact';

  @override
  String get carousel_help_sub => 'A question? The cooperative answers.';

  @override
  String get carousel_help_cta => 'Contact';

  @override
  String get credit_new_request => 'New request';

  @override
  String get credit_remaining => 'remaining';

  @override
  String credit_due_total(String total, String rate) {
    return 'of $total due · $rate% rate';
  }

  @override
  String credit_repaid_pct(String pct) {
    return '$pct% repaid';
  }

  @override
  String get credit_next_due => 'Next instalment';

  @override
  String get credit_penalty_title => 'Late penalty due';

  @override
  String get credit_penalty_sub =>
      '50% of the interest due on overdue instalments (Article 12).';

  @override
  String get credit_empty_body =>
      'Submit a request to the committee . 10% rate, term based on the bylaws tier (Article 7).';

  @override
  String get credit_empty_hint => 'Tap « + New request »';

  @override
  String get credit_status_litigation => 'Litigation';

  @override
  String get credit_unavailable => 'Loans unavailable';

  @override
  String get profile_tile_pin => 'Secret code';

  @override
  String get profile_tile_pin_sub => 'Update your 4-digit code';

  @override
  String get profile_tile_biometric => 'Fingerprint';

  @override
  String get profile_tile_biometric_sub =>
      'Unlock the app without typing the code';

  @override
  String get biometric_cancelled => 'Authentication cancelled.';

  @override
  String get pin_welcome_back => 'Welcome back';

  @override
  String pin_hello(String name) {
    return 'Hello, $name';
  }

  @override
  String get pin_wrong => 'Wrong code. Try again.';

  @override
  String get pin_unlock_prompt => 'Enter your secret code to unlock.';

  @override
  String get pin_use_other_account => 'Use another account';

  @override
  String get pin_create_title => 'Create your secret code';

  @override
  String get pin_confirm_title => 'Confirm your code';

  @override
  String get pin_mismatch => 'The codes don\'t match. Try again.';

  @override
  String get pin_confirm_prompt => 'Enter the same 4-digit code again.';

  @override
  String get pin_create_sub =>
      'This code protects access to your account and hides your balance.';

  @override
  String get pin_current_title => 'Current code';

  @override
  String get pin_current_sub => 'Enter your current secret code.';

  @override
  String get pin_new_title => 'New code';

  @override
  String get pin_new_sub => 'Choose a new 4-digit code.';

  @override
  String get pin_confirm_new_title => 'Confirm the code';

  @override
  String get pin_confirm_new_sub => 'Enter the new code again.';

  @override
  String get pin_current_wrong => 'Wrong current code.';

  @override
  String get pin_mismatch_short => 'The codes don\'t match.';

  @override
  String get pin_update_failed => 'Couldn\'t update. Try again.';

  @override
  String get pin_updated => 'Secret code updated ✓';

  @override
  String get pin_reveal_title => 'Show your balance';

  @override
  String get pin_reveal_sub => 'Enter your secret code to show the amount.';

  @override
  String get biometric_reason_unlock =>
      'Fingerprint to open your GATHE Finance space';

  @override
  String get biometric_reason_enable =>
      'Touch the sensor to enable quick unlock';

  @override
  String get biometric_signin_title => 'GATHE Finance';

  @override
  String get biometric_hint => 'Touch the sensor to open your space';

  @override
  String get biometric_cancel_button => 'Use PIN code';

  @override
  String get releve_pdf_title => 'Account statement';

  @override
  String get releve_pdf_member => 'Member';

  @override
  String get releve_pdf_number => 'Member no.';

  @override
  String releve_pdf_issued_on(String date) {
    return 'Issued on $date';
  }

  @override
  String get releve_pdf_balance => 'Savings balance';

  @override
  String get releve_pdf_rate => 'Monthly interest rate';

  @override
  String get releve_pdf_total_contrib => 'Total validated contributions';

  @override
  String get releve_pdf_tx_header => 'Savings transactions';

  @override
  String get releve_pdf_col_date => 'Date';

  @override
  String get releve_pdf_col_label => 'Description';

  @override
  String get releve_pdf_col_amount => 'Amount';

  @override
  String get releve_pdf_footer =>
      'Document generated by the GATHE Finance app . for information only.';

  @override
  String get releve_pdf_filename => 'gathe_statement';

  @override
  String get common_done => 'Done';

  @override
  String get common_understood => 'Got it';

  @override
  String get common_amount => 'Amount';

  @override
  String get common_operator => 'Operator';

  @override
  String get common_number => 'Number';

  @override
  String get err_enter_amount => 'Enter an amount.';

  @override
  String get err_min_100 => 'Minimum 100 XAF.';

  @override
  String get err_min_1000 => 'Minimum 1,000 XAF.';

  @override
  String get err_amount_multiple_50 => 'Amount must be a multiple of 50.';

  @override
  String err_collecte_min_per_day(String min, int days) {
    return 'Minimum $min ($days day(s) × 1,000).';
  }

  @override
  String get err_number_incomplete => 'Incomplete number.';

  @override
  String get dep_title => 'Make my contribution';

  @override
  String get dep_how => 'How do you want to pay today?';

  @override
  String get dep_mobile_money => 'Mobile Money';

  @override
  String get dep_mobile_sub => 'Instant payment via Tara · 24/7';

  @override
  String get dep_agency => 'At the branch';

  @override
  String get dep_agency_sub => 'Akwa Bercy · Mon–Fri · 08:00 – 17:00';

  @override
  String get dep_cutoff_note =>
      'Daily cut-off: 17:00. After that or on weekends, the deposit is credited on the next business day.';

  @override
  String get dep_agency_title => 'We\'ll keep a spot for you at the branch';

  @override
  String get dep_agency_body =>
      'Visit GATHE FINANCE, Akwa Douala Bercy, with your member number. The agent records your deposit and the credit appears immediately.';

  @override
  String get dep_agency_place => 'Akwa, Douala . Bercy';

  @override
  String get dep_agency_hours => 'Mon–Fri · 08:00 – 17:00';

  @override
  String get dep_agency_cutoff => 'Daily cut-off 17:00';

  @override
  String get dep_suggestion =>
      'Suggestion: 1,000 FCFA. The amount is up to you.';

  @override
  String get classic_dep_title => 'Deposit to savings';

  @override
  String get classic_dep_sub =>
      'Classic savings . any amount, separate from your daily contribution.';

  @override
  String get classic_card_title => 'Classic savings';

  @override
  String get classic_card_sub => 'Set money aside anytime';

  @override
  String get classic_card_cta => 'Deposit';

  @override
  String get dep_confirm_default => 'Confirm the deposit';

  @override
  String dep_confirm_amount(String amount) {
    return 'Deposit $amount';
  }

  @override
  String get dep_waiting_title => 'Waiting for your confirmation…';

  @override
  String dep_waiting_body(String network, String amount) {
    return 'A code will be sent to your $network.\nEnter your PIN to validate $amount.';
  }

  @override
  String get dep_waiting_hint => 'This may take a few seconds';

  @override
  String get dep_done_title => 'Deposit confirmed';

  @override
  String dep_done_body(String amount) {
    return '$amount has been credited\nto your savings account.';
  }

  @override
  String get lreq_title => 'Request a loan';

  @override
  String get lreq_intro =>
      'The term and schedule are set by the bylaws based on the amount.';

  @override
  String get lreq_amount => 'Desired amount';

  @override
  String get lreq_modality => 'Repayment modality';

  @override
  String get lreq_motive => 'Purpose of the request';

  @override
  String get lreq_motive_hint =>
      'Explain your project . equipment, working capital, training, etc.';

  @override
  String get lreq_motive_short => 'Motivation too short (min 10 characters).';

  @override
  String get lreq_fees_note =>
      'Processing fees (5,000 XAF) will be payable after approval.';

  @override
  String get lreq_submit => 'Submit the request';

  @override
  String get lreq_sending => 'Sending…';

  @override
  String get lreq_sent_title => 'Request sent';

  @override
  String get lreq_sent_body =>
      'Pay the processing fees so the committee can review your file.';

  @override
  String get lreq_schedule => 'Your schedule';

  @override
  String get lreq_duration => 'Term';

  @override
  String get lreq_interest => 'Interest (10%)';

  @override
  String get lreq_total => 'Total to repay';

  @override
  String get rep_title => 'Repay my loan';

  @override
  String rep_installment_n(String n) {
    return 'Instalment #$n';
  }

  @override
  String rep_remaining_due(String amount) {
    return 'Remaining due: $amount';
  }

  @override
  String get rep_operator_mm => 'Mobile Money operator';

  @override
  String get rep_confirm => 'Confirm the repayment';

  @override
  String rep_waiting_body(String network) {
    return 'Enter your $network PIN\nto validate the repayment.';
  }

  @override
  String get rep_done_title => 'Repayment applied';

  @override
  String rep_done_body(String amount) {
    return '$amount was applied FIFO\nacross your instalments.';
  }

  @override
  String get ren_title => 'Renew my loan';

  @override
  String ren_subtitle(String dossier, String amount) {
    return 'Loan $dossier . remaining balance $amount.';
  }

  @override
  String get ren_extra_month => 'Extension: +1 month';

  @override
  String get ren_mode_question => 'How will you settle the interest?';

  @override
  String get ren_mode_comptant => 'Upfront . 10%';

  @override
  String get ren_mode_comptant_sub =>
      'You pay the interest now. Reduced rate on the remaining principal.';

  @override
  String get ren_mode_reporte => 'Deferred . 15%';

  @override
  String get ren_mode_reporte_sub =>
      'Interest is carried over with the principal. Increased rate.';

  @override
  String get ren_recap_interest => 'Renewal interest';

  @override
  String get ren_recap_total => 'New total to repay';

  @override
  String get ren_fees_note =>
      'Renewal extends your loan by one month. No processing fee is charged . only the renewal interest, computed on the remaining principal, is added. Your request will be submitted to the committee for approval.';

  @override
  String get ren_submit => 'Request renewal';

  @override
  String get ren_sent_body =>
      'Your renewal request (+1 month) has been sent.\nIt\'s now awaiting committee approval.';

  @override
  String lreq_installments(String n) {
    return '$n instalments';
  }

  @override
  String lreq_per_time(String amount) {
    return '$amount each';
  }

  @override
  String get common_modify => 'Edit';

  @override
  String get common_firstname => 'First name';

  @override
  String get common_lastname => 'Last name';

  @override
  String get common_phone => 'Phone';

  @override
  String get common_email => 'Email';

  @override
  String get prof_logout_q => 'Log out?';

  @override
  String get prof_logout_body =>
      'You\'ll need to sign in again with your email and password.';

  @override
  String get prof_logout_confirm => 'Yes, log me out';

  @override
  String prof_member_num(String n) {
    return 'Member · $n';
  }

  @override
  String get myinfo_saved => 'Information saved.';

  @override
  String get myinfo_title => 'My information';

  @override
  String get myinfo_sub => 'You can edit these fields from the app.';

  @override
  String get myinfo_firstname_required => 'First name required';

  @override
  String get myinfo_lastname_required => 'Last name required';

  @override
  String get myinfo_email_locked => 'To change your email, contact support.';

  @override
  String get pwd_title => 'Password';

  @override
  String get pwd_sub => 'Choose a new password of at least 8 characters.';

  @override
  String get pwd_old => 'Current password';

  @override
  String get pwd_old_required => 'Current password required';

  @override
  String get pwd_new => 'New password';

  @override
  String get pwd_min_hint => 'Min 8 characters';

  @override
  String get pwd_min_err => 'At least 8 characters';

  @override
  String get pwd_diff_err => 'Must differ from the old one';

  @override
  String get pwd_confirm => 'Confirmation';

  @override
  String get pwd_confirm_hint => 'Re-type the new password';

  @override
  String get pwd_mismatch => 'Passwords don\'t match';

  @override
  String get pwd_done_title => 'Password changed';

  @override
  String get pwd_done_body => 'You\'ll use the new one at your next sign-in.';

  @override
  String get bko_title => 'Order my booklet';

  @override
  String get bko_sub => 'Pay 1,000 XAF via Mobile Money to start printing.';

  @override
  String get bko_after_note =>
      'Once your payment is confirmed, the branch prints your booklet and notifies you when it\'s ready.';

  @override
  String get bko_pay => 'Pay 1,000 XAF';

  @override
  String bko_waiting_body(String network) {
    return 'Enter your $network PIN';
  }

  @override
  String get bko_done_title => 'Order recorded';

  @override
  String get mi_eyebrow => 'Cooperative';

  @override
  String get mi_intro =>
      'At GATHE Finance, you\'re not just a customer: you become a **co-owner** of a savings & credit cooperative. Your decisions count, and profits go back to members.';

  @override
  String get mi_card1_title => 'Secure savings';

  @override
  String get mi_card1_body =>
      'Your money is protected by the cooperative and earns 1%/month on your savings account.';

  @override
  String get mi_card2_title => 'Accessible credit';

  @override
  String get mi_card2_body =>
      'Credit based on your savings. 10% rate per transaction, term per the bylaws.';

  @override
  String get mi_card3_title => 'A real say';

  @override
  String get mi_card3_body =>
      'One share = one vote at the AGM. You take part in the cooperative\'s decisions.';

  @override
  String get mi_steps_title => 'To become a member';

  @override
  String get mi_step1 => 'Submit your membership request (form below)';

  @override
  String get mi_step2 => 'Pay the membership fees (10,000 + 2,000 FCFA)';

  @override
  String get mi_step3 =>
      'Your account is activated once your request is approved';

  @override
  String get mi_submit => 'Submit my request';

  @override
  String get mi_later => 'Later';

  @override
  String get mf_statut_salarie => 'Employee';

  @override
  String get mf_statut_commercant => 'Trader';

  @override
  String get mf_statut_artisan => 'Craftsperson';

  @override
  String get mf_statut_sansemploi => 'Unemployed';

  @override
  String get mf_statut_autre => 'Other';

  @override
  String get mf_title => 'Become a member';

  @override
  String get mf_intro =>
      'Fill in your request. The cooperative will review it and get back to you.';

  @override
  String get mf_section_identity => 'Identity';

  @override
  String get mf_section_contact => 'Contact details';

  @override
  String get mf_section_location => 'Location';

  @override
  String get mf_section_statut => 'Professional status';

  @override
  String get mf_section_urgence => 'Emergency contact';

  @override
  String get mf_section_motivation => 'Motivation (optional)';

  @override
  String get mf_section_pieces => 'Supporting documents';

  @override
  String get mf_pieces_intro =>
      'All four documents are required (image or PDF, 5 MB max).';

  @override
  String get mf_piece_cni_recto => 'ID card . front';

  @override
  String get mf_piece_cni_verso => 'ID card . back';

  @override
  String get mf_piece_plan => 'Location plan';

  @override
  String get mf_piece_photo => 'ID photo';

  @override
  String get mf_piece_tap_to_pick => 'Tap to pick a file';

  @override
  String get mf_piece_remove => 'Remove file';

  @override
  String get mf_piece_too_large => 'File too large (5 MB max).';

  @override
  String get mf_pieces_required => 'Upload all 4 documents before submitting.';

  @override
  String get mf_whatsapp => 'WhatsApp (optional)';

  @override
  String get mf_city => 'City';

  @override
  String get mf_quartier => 'Neighbourhood / precise place';

  @override
  String get mf_urgence_nom => 'Full name';

  @override
  String get mf_urgence_lien => 'Relationship (parent…)';

  @override
  String get mf_statut => 'Status';

  @override
  String get mf_motivation_q => 'What is your motivation?';

  @override
  String get mf_submit => 'Send my request';

  @override
  String get mf_email_invalid => 'Invalid email';

  @override
  String get mf_fees_note =>
      'Fees due on joining: 10,000 FCFA (membership) + 2,000 FCFA (registration).';

  @override
  String get mf_sending => 'Sending your request…';

  @override
  String get mf_sent_title => 'Request sent';

  @override
  String get mf_sent_body =>
      'The cooperative will review your file and get back to you shortly.';

  @override
  String get wd_action => 'Withdraw';

  @override
  String get wd_title => 'Request a withdrawal';

  @override
  String wd_subtitle(String balance) {
    return 'Available: $balance';
  }

  @override
  String get wd_channel_presentiel => 'Cash (branch)';

  @override
  String get wd_channel_momo => 'Mobile Money';

  @override
  String get wd_field_amount => 'Amount';

  @override
  String get wd_field_motif => 'Reason';

  @override
  String get wd_field_motif_hint => 'Ex. family emergency, school fees…';

  @override
  String get wd_field_phone => 'Mobile Money number';

  @override
  String get wd_field_network => 'Network';

  @override
  String get wd_err_required => 'Required';

  @override
  String get wd_err_min_500 => 'Minimum 500 XAF';

  @override
  String get wd_err_over_balance => 'Amount exceeds your available balance.';

  @override
  String get wd_err_phone => 'Invalid number';

  @override
  String get wd_cta_submit => 'Send request';

  @override
  String get wd_cta_close => 'Close';

  @override
  String get wd_disclaimer =>
      'Balance is debited on submission. Admin validates payout (cash or MOMO) within 24 h.';

  @override
  String get wd_success_title => 'Request sent to the cooperative';

  @override
  String get wd_recap_amount => 'Amount';

  @override
  String get wd_recap_channel => 'Channel';

  @override
  String get wd_recap_status => 'Status';

  @override
  String get wd_loading => 'Sending request…';

  @override
  String offline_banner(String when) {
    return 'Offline . data from $when';
  }

  @override
  String get lreq_avaliste_title => 'Designate a guarantor';

  @override
  String get lreq_avaliste_subtitle => 'Senior+BRC member who backs the loan.';

  @override
  String get lreq_avaliste_search_hint => 'Search a member (number or name)';

  @override
  String lreq_avaliste_saturated(String amount) {
    return 'Capacity reached ($amount committed)';
  }

  @override
  String lreq_avaliste_capacity(String amount, String numero) {
    return 'Available $amount ($numero)';
  }

  @override
  String lreq_avaliste_picked(String nom, String numero) {
    return 'Guarantor: $nom ($numero)';
  }

  @override
  String get lreq_avaliste_clear => 'Clear';

  @override
  String get lreq_avaliste_required =>
      'Pick a guarantor from the list (or uncheck).';

  @override
  String get lreq_avaliste_search_empty =>
      'No eligible member found for this search.';

  @override
  String get lreq_campaign_title => 'Apply to a campaign';

  @override
  String get lreq_campaign_subtitle => 'Targeted loan (e.g. traders, farmers).';

  @override
  String get lreq_campaign_pick => 'Choose a campaign';

  @override
  String get lreq_campaign_required =>
      'Pick a campaign from the list (or uncheck).';

  @override
  String get lreq_campaign_none =>
      'No active campaign right now. Try later or uncheck to make a standard request.';

  @override
  String lreq_campaign_error(String error) {
    return 'Could not load campaigns: $error';
  }

  @override
  String get common_preview => 'Preview';

  @override
  String get nav_annonces => 'Updates';

  @override
  String get annonces_tab_news => 'News';

  @override
  String get annonces_tab_campaigns => 'Campaigns';

  @override
  String get annonces_tab_official => 'Cooperative';

  @override
  String get booklet_page_title => 'My booklet';

  @override
  String get news_title => 'News';

  @override
  String get news_load_error => 'Couldn\'t load the news.';

  @override
  String get news_read_article => 'Read article';

  @override
  String get news_empty_title => 'No news yet';

  @override
  String get feed_refresh_hint => 'Check back later, or pull to refresh.';

  @override
  String get campaigns_title => 'Active campaigns';

  @override
  String get campaigns_load_error => 'Couldn\'t load the campaigns.';

  @override
  String get campaign_closed => 'Closed';

  @override
  String get campaign_last_day => 'Last day';

  @override
  String campaign_ends_in_days(int days) {
    return 'Ends in ${days}d';
  }

  @override
  String campaign_ends_on(String date) {
    return 'Closes $date';
  }

  @override
  String get campaign_view_apply => 'View campaign & apply';

  @override
  String get campaigns_empty_title => 'No active campaigns';

  @override
  String booklet_ordered_on(String date) {
    return 'Ordered on $date';
  }

  @override
  String get booklet_validity_1y => 'Valid for 1 year';

  @override
  String get booklet_docs_title => 'Official documents';

  @override
  String get booklet_doc_reglement => 'Internal regulations';

  @override
  String get booklet_doc_reglement_sub => 'Bylaws + member rights and duties.';

  @override
  String get booklet_doc_ledger => 'My entries (PDF)';

  @override
  String get booklet_doc_ledger_sub =>
      'All transactions linked to your passbook.';

  @override
  String get booklet_doc_soon => 'Coming soon';

  @override
  String get credit_tab_credit => 'Credit';

  @override
  String get credit_tab_carnet => 'Passbook';

  @override
  String get credit_paths_title => 'Your credit paths';

  @override
  String get credit_mandates_title => 'My guarantor mandates';

  @override
  String get credit_mandates_sub =>
      'Respond to requests where you\'re named as guarantor.';

  @override
  String get credit_path_available => 'Available';

  @override
  String get credit_path_ineligible => 'Not eligible';

  @override
  String get credit_path_brc_sub_savings => 'Based on savings';

  @override
  String get credit_path_avaliste_title => 'Guarantor';

  @override
  String get credit_path_avaliste_sub => 'Named guarantor';

  @override
  String get credit_path_campaign_title => 'Campaign';

  @override
  String get credit_path_campaign_sub => 'Micro-loan';

  @override
  String get credit_path_garantie_title => 'Collateral';

  @override
  String get credit_path_garantie_sub => 'Asset pledged';

  @override
  String get credit_status_fee_due => 'Study fee due';

  @override
  String get credit_status_field_visit => 'Field visit required';

  @override
  String get credit_status_await_avaliste => 'Awaiting guarantor';

  @override
  String get credit_status_rejected_avaliste => 'Declined by guarantor';

  @override
  String get credit_status_campaign_validation =>
      'Campaign activity under review';

  @override
  String get credit_status_rejected_campaign => 'Declined (campaign)';

  @override
  String get credit_status_await_funding => 'Awaiting funding (24h)';

  @override
  String get credit_step_submitted => 'Request submitted';

  @override
  String get credit_step_fee_paid => 'Study fee paid';

  @override
  String get credit_step_committee => 'Committee review';

  @override
  String get credit_step_decision => 'Decision';

  @override
  String get credit_step_granted => 'Credit granted';

  @override
  String get credit_step_rejected => 'Request rejected';

  @override
  String get hero_toggle_savings => 'Savings';

  @override
  String get hero_toggle_collecte => 'Collection';

  @override
  String get home_hero_savings_label => 'My savings';

  @override
  String get home_hero_savings_cta => 'Deposit to savings';

  @override
  String get home_hero_collecte_label => 'My collection';

  @override
  String get home_hero_collecte_cta => 'Pay my collection';

  @override
  String get account_temporary_title => 'Temporary account';

  @override
  String get account_temporary_sub =>
      'Pay your registration fee to activate your full account.';

  @override
  String get account_suspended_title => 'Suspended account';

  @override
  String get account_suspended_sub =>
      'Contact the cooperative to regularize your situation.';

  @override
  String get account_revoked_title => 'Revoked account';

  @override
  String get account_revoked_sub =>
      'You no longer have access to the cooperative\'s services.';

  @override
  String get account_active_title => 'Active account';

  @override
  String get renewal_suspended_msg =>
      'Account suspended. Pay your yearly passbook to reactivate.';

  @override
  String renewal_overdue_days(int days) {
    return 'Yearly anniversary overdue by $days day(s).';
  }

  @override
  String get renewal_today => 'Yearly anniversary · renew today.';

  @override
  String renewal_in_days(int days) {
    return 'Yearly renewal in $days day(s).';
  }

  @override
  String get renewal_title_reactivate => 'Reactivation required';

  @override
  String get renewal_title_renew => 'Membership renewal';

  @override
  String get support_title => 'Support';

  @override
  String get support_subtitle => 'We\'ll reply as soon as we can.';

  @override
  String get support_empty_title => 'Need help?';

  @override
  String get support_empty_sub =>
      'Message us here; support will reply right in this thread.';

  @override
  String get support_input_hint => 'Write a message…';

  @override
  String get support_sender_you => 'You';

  @override
  String get support_sender_staff => 'Support';

  @override
  String get support_load_error => 'Couldn\'t load the conversation.';

  @override
  String get profile_tile_support => 'Online support';

  @override
  String get profile_tile_support_sub => 'Message support, reply in the app.';

  @override
  String get collecte_eom_title =>
      'Month end — what to do with your collection?';

  @override
  String get collecte_eom_sub =>
      'At the monthly close, 1% is kept by the cooperative.';

  @override
  String get collecte_eom_cash => 'Withdraw as cash';

  @override
  String get collecte_eom_cash_desc => 'Collect your balance at the branch.';

  @override
  String get collecte_eom_savings => 'Move to savings';

  @override
  String get collecte_eom_savings_desc =>
      'Your collection is transferred to your classic savings.';

  @override
  String get home_action_transfer => 'Transfer';

  @override
  String get transfer_title => 'Transfer to a loan';

  @override
  String get transfer_sub =>
      'Repay a loan from your available savings (excl. placement/frozen) + collection.';

  @override
  String get transfer_available_label => 'Available';

  @override
  String get transfer_no_loan => 'No active loan to repay.';

  @override
  String get transfer_pick_loan => 'LOAN TO REPAY';

  @override
  String get transfer_amount => 'AMOUNT TO TRANSFER';

  @override
  String get transfer_remaining => 'Remaining';

  @override
  String get transfer_cta => 'Transfer';

  @override
  String get transfer_success => 'Transfer done.';

  @override
  String get transfer_insufficient => 'Amount exceeds your available money.';

  @override
  String get fee_paid_success => 'Fee paid.';

  @override
  String get fee_from_account => 'From my account';

  @override
  String get fee_from_account_desc => 'Deducted from your available savings.';

  @override
  String get fee_mobile_money => 'Mobile Money';

  @override
  String get fee_mobile_money_desc => 'Pay with MTN / Orange Money.';

  @override
  String get fee_pay_cta => 'Pay';

  @override
  String get carousel_pay_adhesion_title => 'Pay my membership';

  @override
  String get carousel_pay_adhesion_sub => 'Activate your member account.';

  @override
  String get carousel_pay_inscription_title => 'Pay my registration';

  @override
  String get carousel_pay_inscription_sub => 'Cycle registration fee.';

  @override
  String get carousel_pay_cta => 'Pay';

  @override
  String get notifs_filter_all => 'All';

  @override
  String get notif_kind_savings => 'Savings';

  @override
  String get notif_kind_loan => 'Credit';

  @override
  String get notif_kind_payment => 'Payments';

  @override
  String get notif_kind_lender => 'Lender';

  @override
  String get notif_kind_announcement => 'Announcements';

  @override
  String get notif_kind_support => 'Support';

  @override
  String get notif_kind_system => 'System';
}
