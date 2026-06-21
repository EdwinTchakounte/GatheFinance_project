package com.gathefinance.gathe_finance

import android.os.Bundle
import android.view.WindowManager
import io.flutter.embedding.android.FlutterFragmentActivity

/**
 * FlutterFragmentActivity (et non FlutterActivity) est requis par local_auth
 * pour afficher le prompt biométrique système.
 *
 * **Privacy : FLAG_SECURE** posé dès `onCreate` →
 *   - Empêche les captures d'écran système (utilisateur ou tiers).
 *   - Le snapshot de l'app dans le sélecteur d'apps est noir / flouté
 *     selon la ROM, masquant les soldes / données sensibles.
 */
class MainActivity : FlutterFragmentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        window.setFlags(
            WindowManager.LayoutParams.FLAG_SECURE,
            WindowManager.LayoutParams.FLAG_SECURE,
        )
        super.onCreate(savedInstanceState)
    }
}
