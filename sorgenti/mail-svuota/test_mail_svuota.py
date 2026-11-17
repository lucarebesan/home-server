import unittest

import mail_svuota


class ClassifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules, _ = mail_svuota.load_rules()

    def classify(self, headers, labels=None):
        return mail_svuota.classify(
            headers.encode("utf-8"), labels or {"\\inbox"}, self.rules
        )[:2]

    def test_promotional_bulk_message_is_candidate(self):
        result = self.classify(
            "From: Offerte <news@example.com>\r\n"
            "Subject: Black Friday: sconto speciale\r\n"
            "List-Unsubscribe: <mailto:unsubscribe@example.com>\r\n\r\n"
        )
        self.assertEqual(result[0], "candidate")

    def test_order_from_same_commercial_sender_is_kept(self):
        result = self.classify(
            "From: Offerte <news@example.com>\r\n"
            "Subject: Conferma ordine e spedizione\r\n"
            "List-Unsubscribe: <mailto:unsubscribe@example.com>\r\n\r\n"
        )
        self.assertEqual(result[0], "keep")

    def test_protected_label_wins_over_promotion(self):
        result = self.classify(
            "From: News <news@example.com>\r\n"
            "Subject: Offerta Black Friday\r\n"
            "List-Unsubscribe: <mailto:unsubscribe@example.com>\r\n\r\n",
            {"\\inbox", "enea"},
        )
        self.assertEqual(result[0], "keep")

    def test_reply_is_kept(self):
        result = self.classify(
            "From: Persona <person@example.com>\r\n"
            "Subject: Offerta\r\n"
            "In-Reply-To: <id@example.com>\r\n"
            "List-Unsubscribe: <mailto:unsubscribe@example.com>\r\n\r\n"
        )
        self.assertEqual(result[0], "keep")

    def test_bulk_without_promotion_needs_review(self):
        result = self.classify(
            "From: News <news@example.com>\r\n"
            "Subject: Aggiornamenti tecnici\r\n"
            "List-Unsubscribe: <mailto:unsubscribe@example.com>\r\n\r\n"
        )
        self.assertEqual(result[0], "review")

    def test_personal_share_without_bulk_needs_review(self):
        result = self.classify(
            "From: Pinterest <notify@example.com>\r\n"
            "Subject: Alice vorrebbe farti vedere una foto\r\n\r\n"
        )
        self.assertEqual(result[0], "review")

    def test_black_friday_training_offer_is_candidate_despite_security_word(self):
        result = self.classify(
            "From: Beta Formazione <dem@betaformazione.com>\r\n"
            "Subject: Black Friday: formazione e sicurezza in sconto\r\n\r\n"
        )
        self.assertEqual(result[0], "candidate")

    def test_personal_discount_attribution_is_kept(self):
        result = self.classify(
            "From: Servizio clienti <noreply@example.com>\r\n"
            "Subject: Attribuzione sconto sulla tua fornitura\r\n\r\n"
        )
        self.assertEqual(result[0], "keep")

    def test_generic_product_release_needs_review(self):
        result = self.classify(
            "From: AMV <segreteria@amv.it>\r\n"
            "Subject: Novità di rilascio del software\r\n"
            "List-Unsubscribe: <mailto:unsubscribe@example.com>\r\n\r\n"
        )
        self.assertEqual(result[0], "review")

    def test_personalized_offer_without_bulk_needs_review(self):
        result = self.classify(
            "From: Hotel <info@example.com>\r\n"
            "Subject: Ecco l'offerta per il tuo soggiorno\r\n\r\n"
        )
        self.assertEqual(result[0], "review")


class FetchTests(unittest.TestCase):
    def test_fetch_parses_gmail_metadata_without_marking_read(self):
        values, header = mail_svuota.parse_fetch(
            [
                (
                    b'1 (UID 42 X-GM-MSGID 1278455344230334865 FLAGS (\\Seen) '
                    b'X-GM-LABELS (\\Inbox) BODY[HEADER] {17}',
                    b"Subject: Test\r\n\r\n",
                ),
                b")",
            ]
        )
        self.assertEqual(values["uid"], b"42")
        self.assertEqual(values["msgid"], b"1278455344230334865")
        self.assertEqual(header, b"Subject: Test\r\n\r\n")


if __name__ == "__main__":
    unittest.main()
