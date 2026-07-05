import unittest

from tradingagents import i18n


class TestNormalizeLanguage(unittest.TestCase):
    def test_supported_codes_passthrough(self):
        for code in ("en", "ko", "ja", "zh"):
            self.assertEqual(i18n.normalize_language(code), code)

    def test_case_and_region_variants(self):
        self.assertEqual(i18n.normalize_language("KO"), "ko")
        self.assertEqual(i18n.normalize_language("ko-KR"), "ko")
        self.assertEqual(i18n.normalize_language("en_US"), "en")
        self.assertEqual(i18n.normalize_language("zh-Hans"), "zh")

    def test_unknown_and_empty_fall_back_to_english(self):
        for bad in ("fr", "", None, "xx-YY", 123):
            self.assertEqual(i18n.normalize_language(bad), "en")


class TestLanguageInstruction(unittest.TestCase):
    def test_each_language_names_itself(self):
        # Every language — including English — emits an explicit instruction so
        # the model does not follow the Korean-heavy input context by default.
        self.assertIn("English", i18n.get_language_instruction({"report_language": "en"}))
        self.assertIn("Korean", i18n.get_language_instruction({"report_language": "ko"}))
        self.assertIn("Japanese", i18n.get_language_instruction({"report_language": "ja"}))
        self.assertIn("Chinese", i18n.get_language_instruction({"report_language": "zh"}))

    def test_unknown_falls_back_to_english(self):
        self.assertIn("English", i18n.get_language_instruction({"report_language": "fr"}))

    def test_agent_utils_delegates(self):
        from tradingagents.agents.utils.agent_utils import get_language_instruction

        self.assertIn("Korean", get_language_instruction({"report_language": "ko"}))
        self.assertIn("English", get_language_instruction({"report_language": "en"}))


class TestOutputLanguageName(unittest.TestCase):
    def test_names(self):
        self.assertEqual(i18n.get_output_language_name({"report_language": "en"}), "English")
        self.assertIn("Korean", i18n.get_output_language_name({"report_language": "ko"}))
        self.assertIn("Chinese", i18n.get_output_language_name({"report_language": "zh"}))


class TestReportStringsAndChecklist(unittest.TestCase):
    def test_report_strings_complete_per_language(self):
        keys = set(i18n.REPORT_STRINGS["en"])
        for code in i18n.SUPPORTED_LANGUAGES:
            self.assertEqual(set(i18n.REPORT_STRINGS[code]), keys, f"{code} missing keys")

    def test_get_report_strings_fallback(self):
        self.assertEqual(i18n.get_report_strings("fr"), i18n.REPORT_STRINGS["en"])
        self.assertEqual(i18n.get_report_strings("ja"), i18n.REPORT_STRINGS["ja"])

    def test_default_checklist_per_language(self):
        for code in i18n.SUPPORTED_LANGUAGES:
            cl = i18n.get_default_prediction_checklist({"report_language": code})
            self.assertTrue(cl and all(isinstance(x, str) and x for x in cl))


if __name__ == "__main__":
    unittest.main()
