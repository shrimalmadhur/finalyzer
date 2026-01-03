"""Tests for the Amex CSV parser."""

import pytest

from backend.parsers.amex_csv import (
    _build_header_map,
    _clean_description,
    _is_payment,
    _parse_date,
    parse_amex_csv,
)
from backend.parsers.validation import parse_amount_safe


class TestBuildHeaderMap:
    """Test header mapping for different CSV formats."""

    def test_maps_standard_headers(self):
        """Should map standard Amex headers."""
        headers = ["Date", "Description", "Amount", "Category"]
        header_map = _build_header_map(headers)

        assert header_map["date"] == "Date"
        assert header_map["description"] == "Description"
        assert header_map["amount"] == "Amount"
        assert header_map["category"] == "Category"

    def test_maps_statement_view_headers(self):
        """Should map statement view headers with Card Member."""
        headers = ["Date", "Description", "Card Member", "Account #", "Amount"]
        header_map = _build_header_map(headers)

        assert header_map["date"] == "Date"
        assert header_map["description"] == "Description"
        assert header_map["amount"] == "Amount"
        assert header_map["card_member"] == "Card Member"
        assert header_map["account"] == "Account #"

    def test_case_insensitive(self):
        """Should handle different cases."""
        headers = ["DATE", "description", "AMOUNT"]
        header_map = _build_header_map(headers)

        assert header_map["date"] == "DATE"
        assert header_map["description"] == "description"
        assert header_map["amount"] == "AMOUNT"


class TestParseDate:
    """Test date parsing."""

    def test_parses_mm_dd_yyyy(self):
        """Should parse MM/DD/YYYY format."""
        result = _parse_date("12/31/2024")
        assert result is not None
        assert result.year == 2024
        assert result.month == 12
        assert result.day == 31

    def test_parses_mm_dd_yy(self):
        """Should parse MM/DD/YY format."""
        result = _parse_date("12/31/24")
        assert result is not None
        assert result.year == 2024
        assert result.month == 12
        assert result.day == 31

    def test_parses_yyyy_mm_dd(self):
        """Should parse YYYY-MM-DD format."""
        result = _parse_date("2024-12-31")
        assert result is not None
        assert result.year == 2024
        assert result.month == 12
        assert result.day == 31

    def test_invalid_date_returns_none(self):
        """Should return None for invalid dates."""
        assert _parse_date("invalid") is None
        assert _parse_date("") is None


class TestParseAmount:
    """Test amount parsing."""

    def test_parses_positive_amount(self):
        """Should parse positive amounts."""
        amount, valid = parse_amount_safe("49.25")
        assert valid
        assert amount == 49.25

    def test_parses_negative_amount(self):
        """Should parse negative amounts."""
        amount, valid = parse_amount_safe("-349.91")
        assert valid
        assert amount == -349.91

    def test_parses_with_dollar_sign(self):
        """Should handle dollar sign."""
        amount, valid = parse_amount_safe("$100.00")
        assert valid
        assert amount == 100.00

    def test_parses_with_commas(self):
        """Should handle thousand separators."""
        amount, valid = parse_amount_safe("1,234.56")
        assert valid
        assert amount == 1234.56

    def test_parses_parentheses_as_negative(self):
        """Should parse parentheses as negative."""
        amount, valid = parse_amount_safe("(100.00)")
        assert valid
        assert amount == -100.00


class TestIsPayment:
    """Test payment detection."""

    def test_detects_autopay_payment(self):
        """Should detect autopay payments."""
        assert _is_payment("AUTOPAY PAYMENT - THANK YOU") is True

    def test_detects_mobile_payment(self):
        """Should detect mobile payments."""
        assert _is_payment("MOBILE PAYMENT - THANK YOU") is True

    def test_allows_regular_transactions(self):
        """Should allow regular merchant transactions."""
        assert _is_payment("DELTA AIR LINES ATLANTA") is False
        assert _is_payment("UBER") is False
        assert _is_payment("SAFEWAY #1993 1993 SEATTLE WA") is False

    def test_case_insensitive(self):
        """Should be case insensitive."""
        assert _is_payment("autopay payment - thank you") is True
        assert _is_payment("AUTOPAY PAYMENT - THANK YOU") is True


class TestCleanDescription:
    """Test description cleaning."""

    def test_removes_extra_whitespace(self):
        """Should normalize whitespace."""
        result = _clean_description("DELTA   AIR   LINES")
        assert result == "DELTA AIR LINES"

    def test_strips_leading_trailing(self):
        """Should strip leading/trailing whitespace."""
        result = _clean_description("  UBER  ")
        assert result == "UBER"


class TestParseAmexCsv:
    """Integration tests for the full parser."""

    def test_parses_statement_view_format(self):
        """Should parse statement view CSV format."""
        csv_content = b"""Date,Description,Card Member,Account #,Amount
12/31/2024,AIRBNB * HMJ3AF2BTZ SAN FRANCISCO       CA,JANE DOE,-23013,49.25
12/19/2024,DELTA AIR LINES     ATLANTA,JOHN SMITH,-21009,-349.91
12/17/2024,AUTOPAY PAYMENT - THANK YOU,JOHN SMITH,-21009,-178.92
"""
        transactions = parse_amex_csv(csv_content, "test-hash")

        # Should have 2 transactions (payment filtered out)
        assert len(transactions) == 2

        # Check first transaction (Airbnb - charge)
        assert transactions[0].description == "AIRBNB * HMJ3AF2BTZ SAN FRANCISCO CA"
        assert transactions[0].amount == -49.25  # Charge is negative

        # Check second transaction (Delta - refund)
        assert "DELTA" in transactions[1].description
        assert transactions[1].amount == 349.91  # Credit is positive

    def test_parses_activity_download_format(self):
        """Should parse activity download CSV format."""
        csv_content = b"""Date,Description,Amount,Category
01/15/2024,STARBUCKS STORE #1234,6.50,Food & Drink
01/14/2024,UBER TRIP,25.00,Transportation
"""
        transactions = parse_amex_csv(csv_content, "test-hash")

        assert len(transactions) == 2
        assert transactions[0].amount == -6.50
        assert transactions[0].raw_category == "Food & Drink"

    def test_filters_payments(self):
        """Should filter out all payment types."""
        csv_content = b"""Date,Description,Card Member,Account #,Amount
12/17/2024,AUTOPAY PAYMENT - THANK YOU,JOHN SMITH,-21009,-178.92
06/13/2024,MOBILE PAYMENT - THANK YOU,JOHN SMITH,-21009,-3535.19
03/03/2024,MOBILE PAYMENT - THANK YOU,JOHN SMITH,-21009,-3749.33
12/06/2024,UBER,JANE DOE,-23013,35.99
"""
        transactions = parse_amex_csv(csv_content, "test-hash")

        # Only Uber should remain
        assert len(transactions) == 1
        assert "UBER" in transactions[0].description

    def test_handles_credits_correctly(self):
        """Should handle credits (negative amounts in CSV) correctly."""
        csv_content = b"""Date,Description,Card Member,Account #,Amount
06/30/2024,YMCA OF GREATER SEATSEATTLE             WA,JANE DOE,-23013,-150.00
04/16/2024,YMCA OF GREATER SEATSEATTLE             WA,JANE DOE,-23013,-225.00
"""
        transactions = parse_amex_csv(csv_content, "test-hash")

        # Credits should be positive in our system
        assert len(transactions) == 2
        assert transactions[0].amount == 150.00
        assert transactions[1].amount == 225.00

    def test_handles_empty_csv(self):
        """Should handle empty CSV gracefully."""
        csv_content = b"""Date,Description,Amount"""
        transactions = parse_amex_csv(csv_content, "test-hash")
        assert len(transactions) == 0

    def test_handles_malformed_rows(self):
        """Should skip malformed rows."""
        csv_content = b"""Date,Description,Amount
12/31/2024,Valid Transaction,100.00
invalid,Missing Amount,
12/30/2024,Another Valid,50.00
"""
        transactions = parse_amex_csv(csv_content, "test-hash")
        assert len(transactions) == 2


class TestRealWorldScenarios:
    """Test real-world transaction patterns."""

    def test_uber_transactions(self):
        """Should correctly parse Uber transactions."""
        csv_content = b"""Date,Description,Card Member,Account #,Amount
12/06/2024,UBER,JANE DOE,-23013,35.99
12/03/2024,UBER,JANE DOE,-23013,25.21
"""
        transactions = parse_amex_csv(csv_content, "test-hash")

        assert len(transactions) == 2
        for txn in transactions:
            assert "UBER" in txn.description
            assert txn.amount < 0  # Charges are negative

    def test_airline_transactions(self):
        """Should correctly parse airline transactions."""
        csv_content = b"""Date,Description,Card Member,Account #,Amount
09/15/2024,DELTA AIR LINES,JOHN SMITH,-21009,338.48
05/28/2024,DELTA AIR LINES,JOHN SMITH,-21009,395.90
"""
        transactions = parse_amex_csv(csv_content, "test-hash")

        assert len(transactions) == 2
        for txn in transactions:
            assert "DELTA" in txn.description

    def test_grocery_transactions(self):
        """Should correctly parse grocery transactions."""
        csv_content = b"""Date,Description,Card Member,Account #,Amount
12/14/2024,AplPay SAFEWAY #1993SEATTLE             WA,JOHN SMITH,-21009,74.40
01/08/2024,SAFEWAY #1993 1993  SEATTLE             WA,JANE DOE,-23013,77.95
"""
        transactions = parse_amex_csv(csv_content, "test-hash")

        assert len(transactions) == 2
        for txn in transactions:
            assert "SAFEWAY" in txn.description


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
