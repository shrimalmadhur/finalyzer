"""Tests for the Amex Year-End Summary PDF parser."""

import pytest

from backend.parsers.amex_year_end_pdf import (
    is_amex_year_end_summary,
    _extract_year,
    _parse_date,
    _parse_amount,
    _clean_description,
    _is_header_or_label,
    _extract_category_from_context,
)


class TestIsAmexYearEndSummary:
    """Test detection of Amex Year-End Summary PDFs."""
    
    def test_detects_year_end_summary(self):
        """Should detect valid Amex Year-End Summary."""
        text = """
        2025 Year-End Summary
        Includes charges from January 1 through December 31, 2025
        Prepared for JOHN DOE
        """
        assert is_amex_year_end_summary(text) is True
    
    def test_detects_without_american_express_header(self):
        """Should detect even without 'AMERICAN EXPRESS' header."""
        text = """
        2025 Year-End Summary Page 1
        Includes charges from January 1 through December 31, 2025
        Prepared for JOHN SMITH Delta SkyMiles
        """
        assert is_amex_year_end_summary(text) is True
    
    def test_rejects_regular_statement(self):
        """Should reject regular Amex statements."""
        text = """
        AMERICAN EXPRESS
        Monthly Statement
        Account Summary
        """
        assert is_amex_year_end_summary(text) is False
    
    def test_case_insensitive(self):
        """Should be case insensitive."""
        text = """
        year-end summary
        includes charges from january 1
        """
        assert is_amex_year_end_summary(text) is True
    
    def test_detects_with_prepared_for_only(self):
        """Should detect with 'prepared for' even without 'includes charges'."""
        text = """
        2025 Year-End Summary
        Prepared for JOHN DOE
        """
        assert is_amex_year_end_summary(text) is True


class TestExtractYear:
    """Test year extraction from document text."""
    
    def test_extracts_year_from_title(self):
        """Should extract year from 'YYYY Year-End Summary'."""
        text = "2025 Year-End Summary"
        assert _extract_year(text) == 2025
    
    def test_extracts_year_from_date_range(self):
        """Should extract year from date range text."""
        text = "Includes charges from January 1 through December 31, 2024"
        assert _extract_year(text) == 2024
    
    def test_fallback_to_any_year(self):
        """Should fallback to finding any 4-digit year."""
        text = "Some document from 2023"
        assert _extract_year(text) == 2023


class TestParseDate:
    """Test date parsing."""
    
    def test_parses_mm_dd_yyyy(self):
        """Should parse MM/DD/YYYY format."""
        result = _parse_date("01/25/2025", 2025)
        assert result is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 25
    
    def test_parses_mm_dd_yy(self):
        """Should parse MM/DD/YY format."""
        result = _parse_date("01/25/25", 2025)
        assert result is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 25
    
    def test_invalid_date_returns_none(self):
        """Should return None for invalid dates."""
        result = _parse_date("invalid", 2025)
        assert result is None


class TestParseAmount:
    """Test amount parsing."""
    
    def test_parses_simple_amount(self):
        """Should parse simple dollar amount."""
        assert _parse_amount("401.97") == 401.97
    
    def test_parses_with_dollar_sign(self):
        """Should parse amount with dollar sign."""
        assert _parse_amount("$401.97") == 401.97
    
    def test_parses_with_commas(self):
        """Should parse amount with thousand separators."""
        assert _parse_amount("$1,401.97") == 1401.97
    
    def test_parses_negative_in_parentheses(self):
        """Should parse negative amounts in parentheses."""
        assert _parse_amount("($49.25)") == -49.25
    
    def test_empty_returns_zero(self):
        """Should return 0 for empty string."""
        assert _parse_amount("") == 0.0


class TestCleanDescription:
    """Test description cleaning."""
    
    def test_removes_extra_whitespace(self):
        """Should normalize whitespace."""
        result = _clean_description("DELTA   AIR   LINES")
        assert result == "DELTA AIR LINES"
    
    def test_removes_trailing_state_code(self):
        """Should remove trailing state codes."""
        result = _clean_description("STARBUCKS SEATTLE WA")
        assert result == "STARBUCKS SEATTLE"
    
    def test_removes_trailing_numbers(self):
        """Should remove trailing reference numbers."""
        result = _clean_description("UBER TRIP 123456789")
        assert result == "UBER TRIP"


class TestIsHeaderOrLabel:
    """Test header/label detection."""
    
    def test_detects_card_member_header(self):
        """Should detect 'Card Member' as header."""
        assert _is_header_or_label("Card Member JOHN DOE") is True
    
    def test_detects_subtotal(self):
        """Should detect subtotal labels."""
        assert _is_header_or_label("Subtotal $100.00") is True
    
    def test_detects_account_number(self):
        """Should detect account number labels."""
        assert _is_header_or_label("Account Number XXXX-1234") is True
    
    def test_allows_merchant_names(self):
        """Should allow valid merchant names."""
        assert _is_header_or_label("DELTA AIR LINES") is False
        assert _is_header_or_label("STARBUCKS") is False
        assert _is_header_or_label("UBER TRIP") is False


class TestExtractCategoryFromContext:
    """Test category extraction from surrounding text."""
    
    def test_extracts_airline_category(self):
        """Should extract Airline category."""
        text = """
        Travel
        Total Travel Spending $1,537.83
        
        Airline
        
        01/25/2025 February DELTA AIR LINES ATLANTA $401.97
        """
        position = text.find("01/25/2025")
        category = _extract_category_from_context(text, position)
        assert category == "Airline"
    
    def test_extracts_restaurant_category(self):
        """Should extract Restaurant category."""
        text = """
        Restaurant
        
        06/18/2025 July ApPay TST* HONOLULU $20.52
        """
        position = text.find("06/18/2025")
        category = _extract_category_from_context(text, position)
        assert category == "Restaurant"
    
    def test_extracts_transportation_category(self):
        """Should extract Transportation category."""
        text = """
        Transportation
        
        Taxis & Coach
        
        03/29/2025 April ApPay LYFT $67.14
        """
        position = text.find("03/29/2025")
        category = _extract_category_from_context(text, position)
        assert category == "Taxis & Coach"


class TestAmexYearEndPdfIntegration:
    """Integration tests for the parser (requires actual PDF)."""
    
    @pytest.mark.skip(reason="Requires actual PDF file")
    def test_parse_real_pdf(self):
        """Test parsing a real Amex Year-End Summary PDF."""
        # This test would require an actual PDF file
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

