import copy
import json
import os
import tempfile
import unittest
from unittest import mock

import settings
from settings import DEFAULTS, ConfigError, load_config

ORIGINAL = copy.deepcopy(DEFAULTS)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def tearDown(self):
        self.assertEqual(settings.DEFAULTS, ORIGINAL, "DEFAULTS was mutated")

    def write(self, obj, raw=None):
        p = os.path.join(self.tmp.name, "cfg.json")
        with open(p, "w", encoding="utf-8") as f:
            f.write(raw if raw is not None else json.dumps(obj))
        return p


class TestDefaults(Base):
    def test_defaults_only(self):
        cfg = load_config(env={})
        self.assertEqual(cfg, ORIGINAL)
        self.assertIsNot(cfg, DEFAULTS)

    def test_result_is_deep_copy(self):
        cfg = load_config(env={})
        cfg["db"]["pool"]["size"] = 99
        cfg["allowed_hosts"].append("evil")
        cfg["features"]["tags"].append("x")
        cfg2 = load_config(env={})
        self.assertEqual(cfg2, ORIGINAL)


class TestFile(Base):
    def test_deep_merge_keeps_siblings(self):
        p = self.write({"port": 9000, "db": {"host": "db.internal", "pool": {"size": 20}}})
        cfg = load_config(p, env={})
        self.assertEqual(cfg["port"], 9000)
        self.assertEqual(cfg["db"]["host"], "db.internal")
        self.assertEqual(cfg["db"]["port"], 5432)
        self.assertEqual(cfg["db"]["user"], "app")
        self.assertEqual(cfg["db"]["pool"], {"size": 20, "recycle_seconds": 300.0})
        self.assertEqual(cfg["name"], "myapp")

    def test_list_replaced_not_merged(self):
        p = self.write({"allowed_hosts": ["a.com", "b.com"]})
        cfg = load_config(p, env={})
        self.assertEqual(cfg["allowed_hosts"], ["a.com", "b.com"])

    def test_file_values_not_coerced(self):
        p = self.write({"name": "svc", "timeout": 10})
        cfg = load_config(p, env={})
        self.assertEqual(cfg["timeout"], 10)
        self.assertEqual(cfg["name"], "svc")

    def test_unknown_top_level_key(self):
        with self.assertRaises(ConfigError):
            load_config(self.write({"prot": 9000}), env={})

    def test_unknown_nested_key(self):
        with self.assertRaises(ConfigError):
            load_config(self.write({"db": {"pool": {"sise": 3}}}), env={})

    def test_missing_file(self):
        with self.assertRaises(ConfigError):
            load_config(os.path.join(self.tmp.name, "nope.json"), env={})

    def test_invalid_json(self):
        with self.assertRaises(ConfigError):
            load_config(self.write(None, raw='{"port": 9000,'), env={})

    def test_top_level_not_object(self):
        with self.assertRaises(ConfigError):
            load_config(self.write([1, 2]), env={})

    def test_file_does_not_mutate_defaults_via_shared_lists(self):
        p = self.write({"features": {"tags": ["a"]}})
        cfg = load_config(p, env={})
        cfg["features"]["tags"].append("b")
        self.assertEqual(load_config(p, env={})["features"]["tags"], ["a"])


class TestEnv(Base):
    def test_simple_int_and_str(self):
        cfg = load_config(env={"MYAPP_PORT": "9100", "MYAPP_NAME": "api"})
        self.assertEqual(cfg["port"], 9100)
        self.assertIsInstance(cfg["port"], int)
        self.assertEqual(cfg["name"], "api")

    def test_float(self):
        cfg = load_config(env={"MYAPP_TIMEOUT": "7", "MYAPP_DB__POOL__RECYCLE_SECONDS": "12.5"})
        self.assertEqual(cfg["timeout"], 7.0)
        self.assertIsInstance(cfg["timeout"], float)
        self.assertEqual(cfg["db"]["pool"]["recycle_seconds"], 12.5)

    def test_nested(self):
        cfg = load_config(env={"MYAPP_DB__HOST": "pg", "MYAPP_DB__POOL__SIZE": "32"})
        self.assertEqual(cfg["db"]["host"], "pg")
        self.assertEqual(cfg["db"]["pool"]["size"], 32)
        self.assertEqual(cfg["db"]["port"], 5432)

    def test_bool_variants(self):
        for raw, want in [("true", True), ("TRUE", True), ("Yes", True), ("on", True), ("1", True),
                          ("false", False), ("No", False), ("OFF", False), ("0", False), (" true ", True)]:
            with self.subTest(raw=raw):
                cfg = load_config(env={"MYAPP_DEBUG": raw})
                self.assertIs(cfg["debug"], want)

    def test_bool_nested(self):
        cfg = load_config(env={"MYAPP_FEATURES__BETA_UI": "yes"})
        self.assertIs(cfg["features"]["beta_ui"], True)

    def test_bad_bool(self):
        with self.assertRaises(ConfigError) as cm:
            load_config(env={"MYAPP_DEBUG": "maybe"})
        self.assertIn("MYAPP_DEBUG", str(cm.exception))

    def test_bad_int_names_variable(self):
        with self.assertRaises(ConfigError) as cm:
            load_config(env={"MYAPP_DB__POOL__SIZE": "lots"})
        self.assertIn("MYAPP_DB__POOL__SIZE", str(cm.exception))

    def test_bad_float(self):
        with self.assertRaises(ConfigError) as cm:
            load_config(env={"MYAPP_TIMEOUT": "soon"})
        self.assertIn("MYAPP_TIMEOUT", str(cm.exception))

    def test_list(self):
        cfg = load_config(env={"MYAPP_ALLOWED_HOSTS": " a.com, b.com ,,c.com "})
        self.assertEqual(cfg["allowed_hosts"], ["a.com", "b.com", "c.com"])

    def test_empty_list(self):
        cfg = load_config(env={"MYAPP_ALLOWED_HOSTS": ""})
        self.assertEqual(cfg["allowed_hosts"], [])

    def test_empty_default_list(self):
        cfg = load_config(env={"MYAPP_FEATURES__TAGS": "x,y"})
        self.assertEqual(cfg["features"]["tags"], ["x", "y"])

    def test_unknown_and_unrelated_ignored(self):
        env = {"PATH": "/bin", "MYAPP_NOPE": "1", "MYAPP_DB__NOPE": "x", "MYAPP_DB": "whatever",
               "MYAPP_DB__POOL": "3", "OTHER_PORT": "1", "HOME": "/root"}
        cfg = load_config(env=env)
        self.assertEqual(cfg, ORIGINAL)

    def test_env_over_file(self):
        p = self.write({"port": 9000, "db": {"host": "from-file", "user": "fileuser"}})
        cfg = load_config(p, env={"MYAPP_PORT": "9500", "MYAPP_DB__HOST": "from-env"})
        self.assertEqual(cfg["port"], 9500)
        self.assertEqual(cfg["db"]["host"], "from-env")
        self.assertEqual(cfg["db"]["user"], "fileuser")

    def test_env_list_does_not_touch_defaults(self):
        cfg = load_config(env={"MYAPP_ALLOWED_HOSTS": "x"})
        self.assertEqual(cfg["allowed_hosts"], ["x"])

    def test_os_environ_used_when_env_none(self):
        with mock.patch.dict(os.environ, {"MYAPP_PORT": "7777", "MYAPP_DB__USER": "root"}):
            cfg = load_config()
        self.assertEqual(cfg["port"], 7777)
        self.assertEqual(cfg["db"]["user"], "root")

    def test_empty_env_mapping_ignores_os_environ(self):
        with mock.patch.dict(os.environ, {"MYAPP_PORT": "7777"}):
            cfg = load_config(env={})
        self.assertEqual(cfg["port"], 8000)


if __name__ == "__main__":
    unittest.main()
