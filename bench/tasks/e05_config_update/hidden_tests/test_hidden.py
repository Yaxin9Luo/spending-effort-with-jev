import tomllib
import unittest

EXPECTED = {
    "server": {"host": "0.0.0.0", "port": 8080, "workers": 4},
    "database": {"url": "postgresql://localhost:5432/orders", "pool_size": 20, "timeout_seconds": 30},
    "logging": {"level": "WARNING", "format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
    "cache": {"backend": "redis", "url": "redis://localhost:6379/0", "ttl_seconds": 300},
}


def load():
    with open("config/settings.toml", "rb") as f:
        return tomllib.load(f)


class ConfigTest(unittest.TestCase):
    def test_pool_size(self):
        self.assertEqual(load()["database"]["pool_size"], 20)

    def test_log_level(self):
        self.assertEqual(load()["logging"]["level"], "WARNING")

    def test_legacy_mode_removed(self):
        self.assertNotIn("legacy_mode", load()["server"])

    def test_cache_section(self):
        self.assertEqual(load()["cache"], EXPECTED["cache"])

    def test_nothing_else_changed(self):
        self.assertEqual(load(), EXPECTED)

    def test_loader_still_works(self):
        from orders.settings import load_settings
        self.assertEqual(load_settings(), EXPECTED)


if __name__ == "__main__":
    unittest.main()
