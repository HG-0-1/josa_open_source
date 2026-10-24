import unittest

from services import safety_service


class SafetyServiceTests(unittest.TestCase):
    def test_distress_and_negated_or_quoted_intent(self):
        statements = (
            "أنا حزين ومحبط", "حاسس إني فاشل",
            "أنا مش ناوي أؤذي نفسي الآن", "لا أريد أن أقتل نفسي",
            "أنا لن أؤذي نفسي الآن", "I will not kill myself",
            'قرأت مثالاً: «أنا ناوي أؤذي نفسي الآن، رح أنتحر الليلة.»',
            'An example says: "I feel sad. I will kill myself now."',
            'هذا اقتباس: “أنا حزين، أنا ناوي أؤذي نفسي الآن.”',
        )
        for index, text in enumerate(statements):
            with self.subTest(case=index):
                self.assertFalse(safety_service.is_clearly_urgent(text))

    def test_immediate_intent_and_independent_danger_after_quote(self):
        statements = (
            "أنا ناوي أؤذي نفسي الآن", "انا ناويه اذي حالي هلق",
            '"أنا ناوي أؤذي نفسي الآن"',
            "أَنَا نَاوِي أُؤْذِي نَفْسِي الآن", "سأؤذي نفسي الآن",
            "أنا حزين، أنا ناوي أؤذي نفسي الآن",
            "أنا مش ناوي أؤذي نفسي، رح أنتحر الليلة",
            'قرأت «أنا بخير»؛ أنا ناوي أؤذي نفسي الآن',
            'An example says "I am fine". I will kill myself now.',
        )
        for index, text in enumerate(statements):
            with self.subTest(case=index):
                self.assertTrue(safety_service.is_clearly_urgent(text))

    def test_negated_or_quoted_physical_symptoms(self):
        statements = (
            "ما عندي ألم شديد في الصدر", "لا أعاني من صعوبة شديدة في التنفس",
            "ليس لدي ضيق شديد في التنفس", "لا يوجد ألم شديد في الصدر",
            "I have no severe chest pain", "I do not have severe chest pain",
            'قرأت عن «ألم شديد في الصدر»',
            'The example says "I cannot breathe".',
            "أنا حزين ومتوتر",
        )
        for index, text in enumerate(statements):
            with self.subTest(case=index):
                self.assertFalse(safety_service.has_urgent_physical_symptoms(text))

    def test_real_symptoms_are_not_suppressed_by_other_negation(self):
        statements = (
            "مش قادر أتنفس", "لا أستطيع التنفس",
            "ما عندي ألم شديد في الصدر لكن مش قادر أتنفس",
            "I have no severe chest pain but I cannot breathe",
            'قرأت «ألم شديد في الصدر»؛ عندي ضيق شديد في التنفس',
            "عندي ألم شديد في الصدر، لا أريد إكمال التمرين",
        )
        for index, text in enumerate(statements):
            with self.subTest(case=index):
                self.assertTrue(safety_service.has_urgent_physical_symptoms(text))
