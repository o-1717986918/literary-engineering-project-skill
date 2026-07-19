import unittest

from literary_engineering_workbench.text_counts import (
    count_chinese_content_chars,
    count_nonspace_chars,
    chinese_machine_count_mapping,
)


class TextCountTests(unittest.TestCase):
    def test_chinese_content_counts_han_and_chinese_punctuation_only(self):
        text = "汉字，标点。ASCII/path"

        self.assertEqual(count_chinese_content_chars(text), 6)
        self.assertGreater(count_nonspace_chars(text), 6)

    def test_machine_mapping_keeps_formal_chinese_count_and_diagnostic_bridge(self):
        mapping = chinese_machine_count_mapping("汉字，标点。ASCIIEXTRA", target_chinese_chars=6)

        self.assertEqual(mapping["target_unit"], "chinese_content_chars_including_chinese_punctuation")
        self.assertEqual(mapping["chinese_content_chars"], 6)
        self.assertEqual(mapping["machine_nonspace_chars"], 16)
        self.assertEqual(mapping["rough_expected_machine_chars"], 16)
        self.assertEqual(mapping["rough_expected_machine_chars_range"], [15, 17])
        self.assertEqual(mapping["baseline_machine_chars_1_to_1_range"], [6, 7])
        self.assertEqual(mapping["mapping_basis"], "current_text_observed_machine_to_chinese_ratio")
        self.assertEqual(mapping["diagnostic_warning"], "machine_count_inflated_by_non_chinese_or_workbench_content")


if __name__ == "__main__":
    unittest.main()
