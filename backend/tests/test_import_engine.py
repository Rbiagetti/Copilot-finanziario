"""Regressioni per backend/core/import_engine.py — coprono due bug reali trovati
testando l'AI Importer con file veri (export FinCopilot e Revolut consolidated statement,
2026-08-22): date ISO scambiate mese/giorno da dateutil, e mesi italiani non riconosciuti."""
import pytest
from backend.core.import_engine import (
    _parse_date, _parse_amount, _extract_csv_table, split_expenses_and_income,
)


class TestParseDateISO:
    def test_iso_date_not_swapped(self):
        # Bug reale: dateutil con dayfirst=True leggeva "2026-08-03" come 2026-03-08
        assert _parse_date("2026-08-03") == "2026-08-03"

    def test_iso_date_day_over_12_not_lost(self):
        # Bug reale: "2026-07-30" scambiato produceva mese=30 (invalido) -> riga scartata
        assert _parse_date("2026-07-30") == "2026-07-30"

    def test_iso_date_with_slashes(self):
        assert _parse_date("2026/08/03") == "2026-08-03"

    def test_iso_invalid_date_rejected(self):
        assert _parse_date("2026-13-40") is None

    def test_iso_future_date_rejected(self):
        assert _parse_date("2099-01-01") is None


class TestParseDateItalianMonths:
    def test_abbreviated_month(self):
        # Bug reale: "1 gen 2026" veniva letto come 2026-01-22 (giorno di oggi come fallback)
        assert _parse_date("1 gen 2026") == "2026-01-01"

    def test_full_month_name(self):
        assert _parse_date("28 gennaio 2026") == "2026-01-28"

    def test_various_abbreviations(self):
        # Anno fisso nel passato per tutti i 12 mesi, per non dipendere dalla data di oggi
        # (la guardia anti-data-futura in _parse_date scarterebbe altrimenti i mesi non
        # ancora raggiunti nell'anno corrente).
        cases = {
            "3 gen 2020": "2020-01-03", "3 feb 2020": "2020-02-03", "3 mar 2020": "2020-03-03",
            "3 apr 2020": "2020-04-03", "3 mag 2020": "2020-05-03", "3 giu 2020": "2020-06-03",
            "3 lug 2020": "2020-07-03", "3 ago 2020": "2020-08-03", "3 set 2020": "2020-09-03",
            "3 ott 2020": "2020-10-03", "3 nov 2020": "2020-11-03", "3 dic 2020": "2020-12-03",
        }
        for raw, expected in cases.items():
            assert _parse_date(raw) == expected, f"{raw} -> atteso {expected}"


class TestParseDateOtherFormats:
    def test_dd_mm_yyyy_dayfirst(self):
        assert _parse_date("15/01/2026") == "2026-01-15"

    def test_dd_mm_yy_dotted(self):
        assert _parse_date("15.01.26") == "2026-01-15"

    def test_empty_and_none(self):
        assert _parse_date("") is None
        assert _parse_date(None) is None


class TestParseAmount:
    def test_italian_format_preserves_sign(self):
        assert _parse_amount("-45,30") == -45.30
        assert _parse_amount("2.025,90") == 2025.90

    def test_us_format(self):
        assert _parse_amount("1,234.56") == 1234.56

    def test_zero_and_invalid(self):
        assert _parse_amount("") is None
        assert _parse_amount("-") is None


class TestSplitExpensesIncome:
    def test_mixed_signs_keeps_only_negative_as_expense(self):
        rows = [{"amount": -10.0}, {"amount": 500.0}, {"amount": -5.0}]
        kept, skipped = split_expenses_and_income(rows)
        assert skipped == 1
        assert [r["amount"] for r in kept] == [10.0, 5.0]

    def test_all_positive_kept_as_is(self):
        # Formato con colonna "Uscite" già solo positiva (nessuna colonna Entrate mappata):
        # non c'è modo di distinguere spesa/entrata dal segno, quindi non scarta nulla.
        rows = [{"amount": 10.0}, {"amount": 20.0}]
        kept, skipped = split_expenses_and_income(rows)
        assert skipped == 0
        assert len(kept) == 2


class TestExtractCsvTableWithPreamble:
    def test_finds_table_after_preamble(self):
        text = (
            "Conti correnti Riepiloghi,,,\n"
            ",,,\n"
            "Saldo di apertura,100,,\n"
            ",,,\n"
            "Data,Descrizione,Categoria,Importo\n"
            "1 gen 2026,Bar,Esercente,-3,50\n"
            "2 gen 2026,Market,Esercente,-10,00\n"
            "\n"
            "---------,,,\n"
        )
        df = _extract_csv_table(text)
        assert df is not None
        assert list(df.columns) == ["Data", "Descrizione", "Categoria", "Importo"]
        assert len(df) == 2

    def test_clean_csv_with_header_at_row_zero_returns_none(self):
        # Header già in riga 0: nessun preambolo da saltare, deve tornare None
        # (segnale per usare il path pd.read_csv normale, non cambiare comportamento).
        text = "data,importo,descrizione\n2026-01-01,10.0,test\n"
        assert _extract_csv_table(text) is None

    def test_no_recognizable_header_returns_none(self):
        text = "foo,bar,baz\n1,2,3\n"
        assert _extract_csv_table(text) is None


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
