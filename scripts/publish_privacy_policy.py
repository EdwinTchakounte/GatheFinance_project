"""Publie le contenu réel de la POLITIQUE DE CONFIDENTIALITÉ dans le CMS Wagtail.

Corrige le placeholder « contenu en cours de finalisation » : la LegalPage
`politique-confidentialite` existe (créée par bootstrap_site) mais son corps est
vide → la vitrine affiche `legal.draftNotice`. Ce script remplit le corps avec le
texte canonique (un bloc « Texte enrichi ») et PUBLIE la page.

- Idempotent : réécrit le corps + republie à chaque exécution.
- Ne touche qu'à cette page (le reste du CMS est intact).

Usage (dans le conteneur backend) :
    python manage.py shell < publish_privacy_policy.py
"""

from wagtail.models import Locale

from apps_cms.cms.models import LegalPage

SLUG = "politique-confidentialite"

# Contenu rich-text (tags autorisés : h2/h3, p, ul/li, strong/em, a). Le <table>
# et le <div callout> de la source ont été convertis en liste / paragraphe.
BODY_FR = """
<p><em>Dernière mise à jour : 14 août 2026</em></p>

<p>La présente politique décrit comment la coopérative <strong>GATHE Finance</strong> (« nous ») collecte, utilise et protège les données personnelles des membres qui utilisent l'application mobile <strong>GATHE Finance</strong> (« l'Application »), disponible sur Google Play. Elle s'applique en complément du Règlement intérieur de la coopérative et des Conditions générales d'utilisation.</p>

<h2>1. Responsable du traitement</h2>
<p>Le responsable du traitement des données est la coopérative <strong>GATHE Finance</strong>, sise Rue Mermoz, Akwa, Douala, Cameroun. Pour toute question relative à vos données, écrivez à <a href="mailto:contact@gathe-finance.com">contact@gathe-finance.com</a>.</p>

<h2>2. Données que nous collectons</h2>
<ul>
<li><strong>Identité</strong> — nom, prénom, photo de profil. <em>Finalité :</em> création et gestion de votre compte membre.</li>
<li><strong>Coordonnées</strong> — adresse e-mail, numéro de téléphone. <em>Finalité :</em> connexion, communications, assistance.</li>
<li><strong>Données financières coopératives</strong> — épargne, collectes, demandes et remboursements de crédit, opérations. <em>Finalité :</em> fourniture des services de la coopérative.</li>
<li><strong>Justificatifs</strong> — pièce d'identité (CNI), documents de dossier. <em>Finalité :</em> instruction des demandes d'adhésion, de crédit ou d'avaliste.</li>
<li><strong>Données techniques</strong> — jeton de notification (FCM), journaux d'activité dans l'app. <em>Finalité :</em> notifications, sécurité, support.</li>
</ul>
<p>Nous ne collectons <strong>pas</strong> votre localisation, vos contacts, vos SMS, ni aucune donnée de santé. L'Application n'utilise aucune donnée à des fins de publicité ciblée.</p>

<h2>3. Base légale et finalités</h2>
<p>Vos données sont traitées pour :</p>
<ul>
<li>l'exécution du contrat coopératif qui vous lie à GATHE Finance (gestion de l'épargne, des collectes et du crédit) ;</li>
<li>le respect de nos obligations légales et réglementaires (lutte contre la fraude, tenue des registres) ;</li>
<li>votre intérêt et le nôtre à sécuriser l'accès et à vous assister ;</li>
<li>votre consentement, pour les traitements facultatifs (photo de profil, notifications).</li>
</ul>

<h2>4. Destinataires des données</h2>
<p>Vos données sont accessibles aux personnels habilités de la coopérative (comité, gestion, support) dans la limite de leurs missions. Elles peuvent être confiées à des <strong>sous-traitants techniques</strong> agissant pour notre compte (hébergement sécurisé, service d'envoi des notifications et des e-mails). Ces prestataires sont tenus à la confidentialité et n'utilisent pas vos données pour leur propre compte.</p>
<p><strong>Aucune revente.</strong> Nous ne vendons ni ne louons vos données personnelles à des tiers, et nous ne les partageons à aucune fin publicitaire.</p>

<h2>5. Durée de conservation</h2>
<p>Vos données sont conservées pendant toute la durée de votre appartenance à la coopérative, puis archivées pour la durée requise par nos obligations légales et comptables. Au-delà, elles sont supprimées ou anonymisées.</p>

<h2>6. Sécurité</h2>
<p>Les échanges entre l'Application et nos serveurs sont <strong>chiffrés en transit (HTTPS/TLS)</strong>. L'accès à l'Application est protégé par un identifiant, un mot de passe et un code PIN, avec possibilité de déverrouillage biométrique géré localement sur votre appareil. Nous mettons en œuvre des mesures techniques et organisationnelles raisonnables pour protéger vos données contre tout accès non autorisé.</p>

<h2>7. Vos droits</h2>
<p>Conformément à la réglementation applicable au Cameroun en matière de protection des données personnelles, vous disposez des droits d'<strong>accès</strong>, de <strong>rectification</strong>, d'<strong>opposition</strong> et de <strong>suppression</strong> de vos données. Vous pouvez également demander la limitation d'un traitement ou la portabilité de vos données.</p>
<p>Pour exercer ces droits, écrivez à <a href="mailto:contact@gathe-finance.com">contact@gathe-finance.com</a> en précisant votre demande. Nous répondons dans un délai raisonnable après vérification de votre identité.</p>

<h2>8. Suppression de votre compte et de vos données</h2>
<p>Vous pouvez à tout moment demander la suppression de votre compte et des données associées en écrivant à <a href="mailto:contact@gathe-finance.com">contact@gathe-finance.com</a>. Certaines données peuvent être conservées le temps strictement nécessaire au respect de nos obligations légales et comptables (par exemple l'historique d'un crédit remboursé).</p>

<h2>9. Mineurs</h2>
<p>L'Application est réservée aux membres majeurs de la coopérative. Nous ne collectons pas sciemment de données concernant des personnes de moins de 18 ans.</p>

<h2>10. Modifications</h2>
<p>Nous pouvons mettre à jour la présente politique. Toute modification substantielle sera portée à votre connaissance par l'Application ou par e-mail. La date de dernière mise à jour figure en tête de ce document.</p>

<h2>11. Contact</h2>
<p>Pour toute question relative à cette politique ou à vos données personnelles :<br/><strong>GATHE Finance</strong>, Rue Mermoz, Akwa, Douala, Cameroun<br/>E-mail : <a href="mailto:contact@gathe-finance.com">contact@gathe-finance.com</a> · Tél. / WhatsApp : +237 6 56 13 06 72</p>
""".strip()


def publish(slug: str, html: str) -> None:
    qs = LegalPage.objects.filter(slug=slug)
    try:
        fr = Locale.objects.get(language_code="fr")
        page = qs.filter(locale=fr).first() or qs.first()
    except Locale.DoesNotExist:
        page = qs.first()

    if page is None:
        print(f"!! LegalPage '{slug}' introuvable — lance d'abord bootstrap_site.")
        return

    page.body = [("rich_text", {"body": html})]
    rev = page.save_revision()
    rev.publish()
    print(
        f"✓ Publié : slug={page.slug} locale={page.locale.language_code} "
        f"live={page.live} blocs={len(page.body)}"
    )


publish(SLUG, BODY_FR)
print("Terminé. Vider éventuellement le cache CDN/navigateur pour voir le contenu.")
