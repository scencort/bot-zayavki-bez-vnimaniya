import unittest

from app.main import parse_realtor_input
from app.parser import extract_realtor_leads


class ExtractRealtorLeadsTests(unittest.TestCase):
    def test_extracts_links_after_target_realtor(self) -> None:
        document_text = """
Поляков Ярослав Алексеевич
0

Рогулин Роман Александрович
https://kosmos.example/leads/123
https://kosmos.example/leads/456

Иванов Иван Иванович
https://kosmos.example/leads/789
"""
        result = extract_realtor_leads(document_text, "Рогулин Роман Александрович")
        self.assertEqual(
            result.links,
            [
                "https://kosmos.example/leads/123",
                "https://kosmos.example/leads/456",
            ],
        )

    def test_returns_empty_list_when_zero_follows_name(self) -> None:
        document_text = """
Рогулин Роман Александрович
0
"""
        result = extract_realtor_leads(document_text, "Рогулин Роман Александрович")
        self.assertEqual(result.links, [])

    def test_supports_name_and_value_on_same_line(self) -> None:
        document_text = """
Рогулин Роман Александрович: https://kosmos.example/leads/123 https://kosmos.example/leads/456
"""
        result = extract_realtor_leads(document_text, "Рогулин Роман Александрович")
        self.assertEqual(
            result.links,
            [
                "https://kosmos.example/leads/123",
                "https://kosmos.example/leads/456",
            ],
        )

    def test_returns_empty_list_when_realtor_not_found(self) -> None:
        document_text = """
Поляков Ярослав Алексеевич
https://kosmos.example/leads/123
"""
        result = extract_realtor_leads(document_text, "Рогулин Роман Александрович")
        self.assertEqual(result.links, [])

    def test_parse_realtor_input_with_telegram_id(self) -> None:
        result = parse_realtor_input("Иванов Иван Иванович - 123456789")
        self.assertEqual(result, ("Иванов Иван Иванович", "123456789"))

    def test_parse_realtor_input_without_telegram_id(self) -> None:
        result = parse_realtor_input("Иванов Иван Иванович - пока нет ID")
        self.assertEqual(result, ("Иванов Иван Иванович", None))


if __name__ == "__main__":
    unittest.main()
