import unittest
from datetime import date
from backend.core.ai_engine import get_anomalies_for_month, _anomaly_cache

class TestAnomaliesCoherence(unittest.TestCase):
    def setUp(self):
        # Pulisci cache prima di ogni test
        _anomaly_cache.clear()
        self.user_id = "test_user"
        self.year = 2024
        self.month = 4

    def test_cache_logic(self):
        # Primo caricamento (cache miss)
        res1 = get_anomalies_for_month(self.user_id, self.year, self.month)
        self.assertIn("anomalies", res1)
        self.assertIn("generated_at", res1)
        
        # Secondo caricamento (cache hit)
        res2 = get_anomalies_for_month(self.user_id, self.year, self.month)
        self.assertEqual(res1["generated_at"], res2["generated_at"], "Dovrebbe ritornare lo stesso timestamp della cache")
        
        # Refresh forzato
        res3 = get_anomalies_for_month(self.user_id, self.year, self.month, force_refresh=True)
        self.assertNotEqual(res1["generated_at"], res3["generated_at"], "Dovrebbe ricalcolare con force_refresh")

    def test_shape_consistency(self):
        res = get_anomalies_for_month(self.user_id, self.year, self.month)
        anomalies = res.get("anomalies", [])
        
        required_fields = [
            "id", "amount", "category", "description", "date", 
            "detection_type", "detection_label", "severity", "stats",
            "z_score", "avg_category", "pct_above_avg"
        ]
        
        if anomalies:
            for field in required_fields:
                self.assertIn(field, anomalies[0], f"Campo {field} mancante nell'anomalia")

if __name__ == "__main__":
    unittest.main()
