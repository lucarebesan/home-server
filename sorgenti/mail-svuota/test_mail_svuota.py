import unittest
from unittest.mock import patch

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

    def test_personal_share_from_pinterest_is_kept(self):
        result = self.classify(
            "From: Alice tramite Pinterest <notify@example.com>\r\n"
            "Subject: Alice vorrebbe farti vedere una foto\r\n\r\n"
        )
        self.assertEqual(result[0], "keep")

    def test_pinterest_message_reminder_is_kept(self):
        result = self.classify(
            "From: Pinterest <activity@notifications.pinterest.com>\r\n"
            "Subject: Non dimenticare di rispondere al messaggio di Alice!\r\n\r\n"
        )
        self.assertEqual(result[0], "keep")

    def test_pec_account_access_alert_is_kept(self):
        result = self.classify(
            "From: comunicazioni@amministrazionepec.it\r\n"
            "Subject: Accessi eseguiti da un nuovo dispositivo\r\n\r\n"
        )
        self.assertEqual(result[0], "keep")

    def test_amazon_cancellation_is_kept(self):
        result = self.classify(
            "From: Amazon.it <order-update@amazon.it>\r\n"
            "Subject: Articoli annullati correttamente\r\n\r\n"
        )
        self.assertEqual(result[0], "keep")

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


class MoveTests(unittest.TestCase):
    def test_move_does_not_require_inbox_in_gmail_label_list(self):
        class Connection:
            mailbox = "INBOX"
            moved = False

            def uid(self, command, *args):
                if command == "MOVE":
                    self.moved = True
                    return "OK", []
                if command == "SEARCH":
                    return "OK", [b"77" if self.mailbox == "SVUOTA" else b""]
                raise AssertionError(command)

            def select(self, mailbox, readonly=False):
                self.mailbox = mailbox
                return "OK", [b"1"]

        metadata = [
            ("123", {"\\important"}, {"\\seen"}),
            ("123", {"\\important", "\\inbox"}, {"\\seen"}),
        ]
        with patch.object(mail_svuota, "current_labels", side_effect=metadata):
            conn = Connection()
            mail_svuota.apply_move(conn, 42, "123",
                                  {"protected_labels": ["ENEA", "legale"]})
            self.assertTrue(conn.moved)
            self.assertEqual(conn.mailbox, "INBOX")


if __name__ == "__main__":
    unittest.main()
