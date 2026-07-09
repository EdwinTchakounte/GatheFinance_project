"""Seed the blog with the three articles of the existing site (idempotent).

Text is the verbatim content recorded in conception/00_contenu_site_existant.md
(reconstructed from the live site; to be replaced by the client's WordPress export
for 100% fidelity). FR only for now — EN translations are created in the Wagtail
admin via wagtail-localize. Safe to re-run.
"""
from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from wagtail.models import Locale

from apps_cms.cms.models import BlogIndexPage, BlogPostPage
from apps_cms.content.models import Author, Category

ARTICLE_1_BODY = """
<p>Pour une petite ou moyenne entreprise (PME), accéder à un financement adapté est souvent essentiel pour franchir de nouvelles étapes de croissance. Que ce soit pour financer l'achat d'équipements, élargir les stocks, ou pénétrer de nouveaux marchés, le crédit peut jouer un rôle crucial dans le développement de votre entreprise.</p>
<h2>1. Faciliter l'Accès aux Ressources Nécessaires</h2>
<p>Un des principaux avantages du crédit pour une PME est de permettre l'accès immédiat aux ressources nécessaires pour développer l'activité, même si l'entreprise ne dispose pas encore des fonds suffisants.</p>
<p><strong>a) Achat d'Équipements et de Matériel</strong> — L'une des utilisations les plus courantes du crédit est le financement d'équipements ou de machines nécessaires à l'amélioration de la production ou des services. En prenant un crédit, vous pouvez acheter du matériel moderne et plus performant, ce qui permet d'optimiser votre capacité de production et, à terme, d'augmenter vos revenus.</p>
<p><strong>b) Constitution de Stocks</strong> — Pour les entreprises opérant dans la vente de biens, avoir un stock suffisant est essentiel pour répondre à la demande du marché. Grâce à un crédit, vous pouvez acheter des stocks en plus grande quantité, négocier de meilleurs prix auprès de vos fournisseurs, et ne pas être pris au dépourvu lors des pics de demande.</p>
<h2>2. Stimuler l'Innovation et l'Expansion</h2>
<p>Le crédit peut aussi être utilisé pour financer des projets d'innovation ou pour explorer de nouvelles opportunités commerciales.</p>
<p><strong>a) Développement de Nouveaux Produits</strong> — Si votre entreprise envisage de lancer de nouveaux produits ou services, un crédit peut permettre de couvrir les coûts de recherche, de développement et de marketing. Cela vous offre l'opportunité de tester de nouvelles offres tout en minimisant les risques financiers.</p>
<p><strong>b) Expansion Géographique</strong> — L'expansion sur de nouveaux marchés, que ce soit au niveau national ou international, nécessite souvent des investissements importants. Que vous deviez ouvrir de nouvelles agences, financer une campagne de communication, ou recruter du personnel, un crédit peut vous donner les moyens d'accélérer cette expansion.</p>
<h2>3. Améliorer la Trésorerie et la Gestion des Flux de Trésorerie</h2>
<p>La gestion des flux de trésorerie est l'un des défis les plus courants pour une PME. En particulier, il peut y avoir des périodes où vous devez gérer des décalages entre les paiements des clients et vos propres obligations financières. Un crédit peut vous permettre de lisser ces périodes et d'éviter les problèmes de trésorerie.</p>
<p><strong>a) Trésorerie d'Oxygène</strong> — Dans certaines situations, un crédit de trésorerie peut servir à maintenir l'entreprise à flot pendant les périodes de faible activité. Cela vous permet de continuer à payer vos charges courantes (salaires, loyers, etc.) sans interruption.</p>
<p><strong>b) Gestion des Périodes de Crise</strong> — En période de crise économique ou de ralentissement du marché, un crédit peut constituer un filet de sécurité. Il vous permet de surmonter ces difficultés temporaires tout en préservant votre capacité de production et en évitant les licenciements ou d'autres mesures drastiques.</p>
<h2>4. Maximiser les Opportunités de Croissance</h2>
<p>Un autre avantage majeur du crédit est qu'il vous permet de saisir les opportunités de croissance au moment où elles se présentent, même si votre entreprise n'a pas immédiatement les fonds nécessaires.</p>
<p><strong>a) Saisir les Opportunités de Marché</strong> — Il peut arriver que de nouvelles opportunités de marché se présentent soudainement : un partenariat stratégique, un gros contrat, ou une demande accrue pour vos produits. Grâce au crédit, vous pouvez répondre à ces opportunités sans tarder, augmentant ainsi votre chiffre d'affaires potentiel.</p>
<p><strong>b) Accélérer la Croissance</strong> — Le crédit peut aussi vous aider à accélérer la croissance de votre PME, en vous permettant d'investir massivement dans des domaines stratégiques comme le marketing, la formation du personnel ou encore l'amélioration des infrastructures.</p>
<h2>5. Flexibilité des Types de Crédit</h2>
<p>Il existe différents types de crédit adaptés aux besoins des PME, offrant ainsi une certaine flexibilité en fonction des projets ou de la situation financière de l'entreprise.</p>
<p><strong>a) Crédit d'Investissement</strong> — Le crédit d'investissement est destiné à financer des projets à long terme comme l'achat de biens immobiliers, de machines ou de véhicules d'entreprise. Ce type de crédit vous permet d'étaler le coût de votre investissement sur plusieurs années.</p>
<p><strong>b) Crédit de Trésorerie</strong> — Le crédit de trésorerie ou le découvert bancaire est idéal pour couvrir les besoins de financement à court terme, comme les frais courants ou les imprévus. Ce type de crédit peut être utilisé ponctuellement pour éviter des décalages de trésorerie.</p>
<p><strong>c) Leasing</strong> — Le leasing ou crédit-bail est une autre forme de financement où vous louez des équipements avec une option d'achat à la fin du contrat. Cette méthode est particulièrement avantageuse si vous ne souhaitez pas immobiliser de grosses sommes d'argent.</p>
<h2>6. Renforcer Votre Crédibilité et Vos Relations avec les Banques</h2>
<p>Accéder à des crédits et les rembourser régulièrement renforce la crédibilité financière de votre entreprise auprès des banques et des investisseurs potentiels. Cette confiance accrue vous ouvrira plus facilement les portes pour des crédits futurs à des conditions avantageuses.</p>
<p><strong>a) Bâtir une Relation Solide avec les Institutions Financières</strong> — En démontrant que votre PME est capable de gérer efficacement le crédit et de le rembourser sans incident, vous bâtissez une relation solide avec votre banque ou votre microfinance. Cela peut vous permettre d'obtenir des prêts plus importants à l'avenir, ou des taux d'intérêt plus compétitifs.</p>
<p><strong>b) Attirer des Investisseurs</strong> — Si votre entreprise a une bonne réputation financière, elle sera également plus attrayante pour les investisseurs qui cherchent des PME bien gérées avec un potentiel de croissance.</p>
<h2>Conclusion</h2>
<p>Le crédit peut jouer un rôle déterminant dans la réussite et la croissance de votre PME. Qu'il s'agisse de financer des équipements, d'améliorer la gestion de votre trésorerie ou de saisir de nouvelles opportunités de marché, il est un levier puissant pour booster votre activité. Toutefois, il est important de bien évaluer vos besoins et de vous assurer que votre entreprise est en mesure de rembourser le crédit sans mettre en péril sa santé financière. Un bon usage du crédit peut véritablement propulser votre PME vers de nouveaux horizons de croissance.</p>
"""

ARTICLE_2_BODY = """
<p>Devenir propriétaire représente une aspiration commune pour nombreux Camerounais. Le financement immobilier peut sembler intimidant, mais le prêt immobilier est une solution fiable qui permet à des milliers de personnes de réaliser ce rêve en toute sérénité.</p>
<h2>1. Comprendre le Prêt Immobilier</h2>
<p>Un prêt immobilier finance l'acquisition d'un bien (maison, appartement, terrain) et s'étend généralement sur 20 ans ou plus. Le principal intérêt consiste à devenir propriétaire sans avoir à disposer immédiatement du montant total nécessaire.</p>
<h2>2. Les Étapes pour Obtenir un Prêt Immobilier</h2>
<p><strong>a) Évaluer Votre Capacité d'Emprunt</strong> — L'analyse repose sur vos revenus mensuels, charges actuelles et apport personnel disponible. Il est conseillé que le montant de vos mensualités ne dépasse pas 30 à 40 % de vos revenus mensuels.</p>
<p><strong>b) Préparer Votre Dossier de Demande</strong> — Documents requis : relevés bancaires ; preuve de revenus (bulletins de salaire) ; pièce d'identité ; détails du bien immobilier. Un bon historique de crédit démontre votre fiabilité.</p>
<p><strong>c) Choisir la Banque ou l'Institution Financière</strong> — Critères de comparaison : taux d'intérêt (fixe ou variable) ; durée du prêt ; frais de dossier ; conditions de remboursement anticipé.</p>
<p><strong>d) Signer l'Offre de Prêt</strong> — L'offre détaille montant, durée, taux, mensualités et conditions particulières. Examinez attentivement tous les termes avant signature.</p>
<p><strong>e) Finaliser l'Achat de Votre Propriété</strong> — La banque débourse les fonds directement au vendeur ou notaire. Vous devenez alors propriétaire officiellement.</p>
<h2>3. Les Avantages d'un Prêt Immobilier</h2>
<p><strong>a) Accessibilité à la Propriété</strong> — Accédez au bien sans attendre la totalité des économies nécessaires.</p>
<p><strong>b) Construire Votre Patrimoine</strong> — Acheter un bien immobilier constitue une forme d'investissement. L'actif peut prendre de la valeur et se transmettre aux générations futures.</p>
<p><strong>c) Stabilité Financière</strong> — Dans le cadre d'un prêt à taux fixe, vos mensualités restent identiques pendant toute la durée du prêt, offrant une prévisibilité budgétaire contrairement aux loyers variables.</p>
<p><strong>d) Déductions Fiscales</strong> — Certains pays permettent la déduction des intérêts immobiliers. Les avantages fiscaux dépendent de votre situation au Cameroun.</p>
<h2>4. Comment Rembourser Votre Prêt en Toute Sérénité</h2>
<ul>
<li>Budgétez judicieusement : intégrez les mensualités sans vous surendetter</li>
<li>Constituez une épargne d'urgence : protégez-vous contre les revenus instables</li>
<li>Anticipez les fluctuations : préparez-vous aux augmentations potentielles avec taux variable</li>
</ul>
<h2>Conclusion</h2>
<p>Avec une bonne planification, un dossier bien préparé et un choix judicieux de l'institution financière, vous pouvez accéder à la propriété en toute sérénité. Comprendre vos besoins, comparer les offres et gérer responsablement les remboursements constituent les clés du succès.</p>
"""

ARTICLE_3_BODY = """
<p>L'éducation de nos enfants représente un investissement parental majeur. Cependant, le coût croissant des frais de scolarité, des fournitures, et d'autres dépenses liées à l'éducation peut constituer un défi financier de taille. La caisse scolaire offre une solution pour planifier sereinement cet avenir éducatif.</p>
<h2>Qu'est-ce que la Caisse Scolaire ?</h2>
<p>La caisse scolaire est un service proposé par certaines institutions financières et coopératives d'épargne qui permet aux parents de constituer une épargne spécialement dédiée aux frais de scolarité de leurs enfants. Elle fonctionne comme une épargne bloquée ou semi-bloquée, encourageant la discipline financière familiale.</p>
<h2>Pourquoi Est-il Important de Planifier les Dépenses Scolaires ?</h2>
<ul>
<li>Éviter les frais de scolarité inattendus</li>
<li>Réduire le stress financier en évitant l'endettement</li>
<li>Favoriser la continuité éducative sans interruption</li>
</ul>
<h2>Comment Utiliser la Caisse Scolaire pour Planifier l'Éducation de Vos Enfants ?</h2>
<p><strong>1. Établissez un Budget Réaliste</strong> — Calculez tous les frais annuels (scolarité, fournitures, uniformes, transport). Exemple : des frais annuels de 500 000 FCFA nécessitent une épargne mensuelle d'environ 42 000 FCFA.</p>
<p><strong>2. Épargnez Tôt et Régulièrement</strong> — Plus tôt vous commencez à épargner pour l'éducation de vos enfants, mieux c'est. Cette régularité évite les solutions de dernier recours comme les prêts ou les cartes de crédit.</p>
<p><strong>3. Bénéficiez des Avantages d'une Caisse Scolaire</strong> — Un des principaux avantages d'une caisse scolaire est qu'elle vous offre des taux d'intérêt attractifs. Certaines institutions proposent des bonus d'épargne ou des offres spéciales.</p>
<p><strong>4. Adaptez votre Épargne en Fonction de l'Évolution des Besoins</strong> — Les frais varient selon les niveaux scolaires. Il faut réévaluer régulièrement les cotisations.</p>
<p><strong>5. Prévoyez pour Plusieurs Enfants</strong> — Un compte distinct par enfant facilite le suivi sans créer de disparités financières.</p>
<h2>Les Bénéfices à Long Terme de la Caisse Scolaire</h2>
<p>La caisse scolaire vous permet de développer des habitudes financières saines. Elle améliore la gestion budgétaire globale tout en assurant un avenir éducatif plus prometteur aux enfants.</p>
<h2>Conclusion</h2>
<p>La caisse scolaire est un outil puissant qui vous aide à planifier l'avenir éducatif de vos enfants avec sérénité. Il n'est jamais trop tard pour commencer cette épargne.</p>
"""

ARTICLES = [
    {
        "slug": "les-avantages-du-credit-pour-booster-le-developpement-de-votre-pme",
        "title": "Les avantages du crédit pour booster le développement de votre PME",
        "date": date(2024, 10, 4),
        "excerpt": (
            "Pour une petite ou moyenne entreprise (PME), accéder à un financement adapté est souvent "
            "essentiel pour franchir de nouvelles étapes de croissance."
        ),
        "body": ARTICLE_1_BODY,
    },
    {
        "slug": "pret-immobilier-comment-acceder-a-votre-propriete-en-toute-serenite",
        "title": "Prêt Immobilier : Comment accéder à votre propriété en toute sérénité ?",
        "date": date(2024, 10, 4),
        "excerpt": (
            "Devenir propriétaire est un rêve partagé par de nombreux Camerounais. Le prêt immobilier "
            "est une solution fiable pour le réaliser en toute sérénité."
        ),
        "body": ARTICLE_2_BODY,
    },
    {
        "slug": "comment-planifier-leducation-de-vos-enfants-grace-a-la-caisse-scolaire",
        "title": "Comment planifier l'éducation de vos enfants grâce à la Caisse Scolaire ?",
        "date": date(2024, 9, 3),
        "excerpt": (
            "L'éducation de nos enfants est l'un des investissements les plus importants. La caisse "
            "scolaire offre une solution pour planifier sereinement cet avenir éducatif."
        ),
        "body": ARTICLE_3_BODY,
    },
]


class Command(BaseCommand):
    help = "Seed the blog with the existing site's three articles (FR, idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        fr = Locale.objects.get(language_code="fr")
        blog_index = BlogIndexPage.objects.live().first()
        if blog_index is None:
            self.stdout.write(self.style.WARNING("No BlogIndexPage found — run bootstrap_site first. Skipping."))
            return

        author, _ = Author.objects.get_or_create(
            locale=fr, name="GATHE", defaults={"role": "Équipe GATHE Finance"}
        )
        category, _ = Category.objects.get_or_create(locale=fr, slug="conseils", defaults={"name": "Conseils"})

        for art in ARTICLES:
            if BlogPostPage.objects.child_of(blog_index).filter(slug=art["slug"]).exists():
                self.stdout.write(f"Article '{art['slug']}' already exists — skipping")
                continue
            post = BlogPostPage(
                title=art["title"],
                slug=art["slug"],
                locale=fr,
                date=art["date"],
                author=author,
                excerpt=art["excerpt"].strip(),
                body=[("rich_text", {"body": art["body"].strip()})],
            )
            blog_index.add_child(instance=post)
            post.categories.add(category)
            post.save()
            post.save_revision().publish()
            self.stdout.write(self.style.SUCCESS(f"Created article '{art['slug']}' (id={post.pk})"))

        self.stdout.write(self.style.SUCCESS("Blog seeding complete."))
