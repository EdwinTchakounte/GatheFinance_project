"""Cut-off de la collecte (Règlement, Article 4)."""
from datetime import datetime

from apps_coop.savings.cutoff import compute_value_date


class TestCutoff:
    def test_before_cutoff_returns_same_day(self):
        # Lundi 12 mai 2025 à 16h59 → date de valeur = lundi.
        now = datetime(2025, 5, 12, 16, 59)
        assert compute_value_date(now).isoformat() == "2025-05-12"

    def test_after_cutoff_returns_next_business_day(self):
        # Lundi 12 mai 2025 à 17h01 → mardi 13 mai.
        now = datetime(2025, 5, 12, 17, 1)
        assert compute_value_date(now).isoformat() == "2025-05-13"

    def test_exact_cutoff_is_after(self):
        # 17h00 pile = après l'heure limite ("au plus tard à 17h00").
        now = datetime(2025, 5, 12, 17, 0)
        assert compute_value_date(now).isoformat() == "2025-05-13"

    def test_friday_after_cutoff_skips_weekend(self):
        # Vendredi 9 mai 2025 à 17h30 → lundi 12 mai.
        now = datetime(2025, 5, 9, 17, 30)
        assert compute_value_date(now).isoformat() == "2025-05-12"

    def test_saturday_morning_goes_to_monday(self):
        # Samedi 10 mai 2025 à 10h00 (heure ouvrable mais jour férié hebdo).
        now = datetime(2025, 5, 10, 10, 0)
        assert compute_value_date(now).isoformat() == "2025-05-12"

    def test_sunday_evening_goes_to_monday(self):
        now = datetime(2025, 5, 11, 22, 0)
        assert compute_value_date(now).isoformat() == "2025-05-12"
