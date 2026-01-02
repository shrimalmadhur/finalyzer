"""Tests for the parser validation module."""

import pytest
from datetime import date

from backend.parsers.validation import (
    ValidationError,
    validate_file_contents,
    validate_csv_contents,
    validate_amount,
    validate_date,
    validate_description,
    clean_amount_string,
    parse_amount_safe,
    normalize_description,
    is_likely_payment,
    ParseResult,
)


class TestValidateFileContents:
    """Test file contents validation."""

    def test_rejects_empty_contents(self):
        """Should reject empty file contents."""
        with pytest.raises(ValidationError, match="empty"):
            validate_file_contents(b"")

    def test_rejects_too_small_contents(self):
        """Should reject files smaller than minimum size."""
        with pytest.raises(ValidationError, match="too small"):
            validate_file_contents(b"abc", min_size=10)

    def test_accepts_valid_contents(self):
        """Should accept valid file contents."""
        validate_file_contents(b"Valid file contents here", min_size=10)


class TestValidateCsvContents:
    """Test CSV contents validation."""

    def test_decodes_utf8(self):
        """Should decode UTF-8 content."""
        result = validate_csv_contents(b"Date,Amount\n2024-01-01,100")
        assert "Date" in result

    def test_decodes_utf8_bom(self):
        """Should handle UTF-8 BOM."""
        result = validate_csv_contents(b"\xef\xbb\xbfDate,Amount\n2024-01-01,100")
        assert "Date" in result

    def test_rejects_invalid_csv(self):
        """Should reject files without delimiters."""
        with pytest.raises(ValidationError, match="not.*valid CSV"):
            validate_csv_contents(b"This is not a CSV file")

    def test_rejects_empty_csv(self):
        """Should reject empty content."""
        with pytest.raises(ValidationError, match="empty"):
            validate_csv_contents(b"")


class TestValidateAmount:
    """Test amount validation."""

    def test_accepts_normal_amounts(self):
        """Should accept normal transaction amounts."""
        assert validate_amount(100.0) is True
        assert validate_amount(-50.25) is True
        assert validate_amount(0) is True

    def test_accepts_large_amounts(self):
        """Should accept large but reasonable amounts."""
        assert validate_amount(50000.0) is True
        assert validate_amount(-100000.0) is True

    def test_rejects_extreme_amounts(self):
        """Should reject extremely large amounts."""
        assert validate_amount(2_000_000) is False
        assert validate_amount(-2_000_000) is False

    def test_rejects_nan(self):
        """Should reject NaN values."""
        assert validate_amount(float("nan")) is False

    def test_rejects_infinity(self):
        """Should reject infinity values."""
        assert validate_amount(float("inf")) is False
        assert validate_amount(float("-inf")) is False


class TestValidateDate:
    """Test date validation."""

    def test_accepts_recent_dates(self):
        """Should accept recent transaction dates."""
        assert validate_date(date(2024, 1, 15)) is True
        assert validate_date(date(2023, 12, 31)) is True

    def test_accepts_dates_in_range(self):
        """Should accept dates within the valid range."""
        assert validate_date(date(2000, 1, 1)) is True
        assert validate_date(date(2050, 12, 31)) is True

    def test_rejects_very_old_dates(self):
        """Should reject dates before 2000."""
        assert validate_date(date(1999, 12, 31)) is False
        assert validate_date(date(1990, 1, 1)) is False

    def test_rejects_future_dates(self):
        """Should reject far future dates."""
        assert validate_date(date(2101, 1, 1)) is False


class TestValidateDescription:
    """Test description validation."""

    def test_accepts_normal_descriptions(self):
        """Should accept normal transaction descriptions."""
        assert validate_description("STARBUCKS COFFEE") is True
        assert validate_description("UBER TRIP") is True

    def test_rejects_empty_descriptions(self):
        """Should reject empty descriptions."""
        assert validate_description("") is False
        assert validate_description("   ") is False

    def test_rejects_too_long_descriptions(self):
        """Should reject overly long descriptions."""
        long_desc = "A" * 600
        assert validate_description(long_desc) is False


class TestCleanAmountString:
    """Test amount string cleaning."""

    def test_removes_dollar_sign(self):
        """Should remove dollar sign."""
        assert clean_amount_string("$100.00") == "100.00"

    def test_removes_commas(self):
        """Should remove thousand separators."""
        assert clean_amount_string("1,234.56") == "1234.56"

    def test_handles_parentheses(self):
        """Should convert parentheses to negative."""
        assert clean_amount_string("(500.00)") == "-500.00"

    def test_handles_trailing_minus(self):
        """Should handle trailing minus sign."""
        assert clean_amount_string("100.00-") == "-100.00"

    def test_removes_whitespace(self):
        """Should remove whitespace."""
        assert clean_amount_string(" $ 100.00 ") == "100.00"

    def test_empty_returns_zero(self):
        """Should return '0' for empty string."""
        assert clean_amount_string("") == "0"


class TestParseAmountSafe:
    """Test safe amount parsing."""

    def test_parses_simple_amount(self):
        """Should parse simple amounts."""
        amount, valid = parse_amount_safe("100.50")
        assert valid is True
        assert amount == 100.50

    def test_parses_negative_amount(self):
        """Should parse negative amounts."""
        amount, valid = parse_amount_safe("-50.25")
        assert valid is True
        assert amount == -50.25

    def test_parses_formatted_amount(self):
        """Should parse formatted amounts."""
        amount, valid = parse_amount_safe("$1,234.56")
        assert valid is True
        assert amount == 1234.56

    def test_returns_default_for_invalid(self):
        """Should return default for invalid amounts."""
        amount, valid = parse_amount_safe("invalid")
        assert valid is False
        assert amount == 0.0

    def test_returns_zero_for_empty(self):
        """Should return 0 for empty string (0 is a valid amount)."""
        amount, valid = parse_amount_safe("")
        # Empty string parses to "0" which is valid
        assert amount == 0.0


class TestNormalizeDescription:
    """Test description normalization."""

    def test_removes_extra_whitespace(self):
        """Should normalize whitespace."""
        result = normalize_description("UBER   TRIP   123")
        assert "  " not in result

    def test_removes_trailing_numbers(self):
        """Should remove long trailing reference numbers."""
        result = normalize_description("STARBUCKS 1234567890123")
        assert "1234567890123" not in result

    def test_removes_store_numbers(self):
        """Should remove store number patterns."""
        result = normalize_description("SAFEWAY #1234")
        assert "#1234" not in result

    def test_empty_returns_empty(self):
        """Should return empty for empty input."""
        assert normalize_description("") == ""


class TestIsLikelyPayment:
    """Test payment detection."""

    def test_detects_payment_thank_you(self):
        """Should detect 'PAYMENT - THANK YOU' patterns."""
        assert is_likely_payment("AUTOPAY PAYMENT - THANK YOU") is True
        assert is_likely_payment("MOBILE PAYMENT - THANK YOU") is True

    def test_detects_autopay(self):
        """Should detect autopay patterns."""
        assert is_likely_payment("AUTOPAY PAYMENT") is True
        assert is_likely_payment("Automatic Payment") is True

    def test_detects_online_payment(self):
        """Should detect online payment patterns."""
        assert is_likely_payment("ONLINE PAYMENT") is True
        assert is_likely_payment("ACH Payment") is True

    def test_allows_regular_merchants(self):
        """Should allow regular merchant transactions."""
        assert is_likely_payment("STARBUCKS COFFEE") is False
        assert is_likely_payment("UBER TRIP") is False
        assert is_likely_payment("AMAZON.COM") is False

    def test_detects_category_payment(self):
        """Should detect payment category."""
        assert is_likely_payment("Some description", category="Payment") is True

    def test_case_insensitive(self):
        """Should be case insensitive."""
        assert is_likely_payment("autopay payment - thank you") is True
        assert is_likely_payment("ONLINE PAYMENT") is True


class TestParseResult:
    """Test ParseResult dataclass."""

    def test_calculates_success_rate(self):
        """Should calculate correct success rate."""
        result = ParseResult(
            transactions=[1, 2, 3],  # Mock transactions
            total_rows_processed=10,
            rows_skipped=7,
        )
        assert result.success_rate == 30.0

    def test_zero_processed_returns_zero_rate(self):
        """Should return 0% for no rows processed."""
        result = ParseResult(transactions=[], total_rows_processed=0)
        assert result.success_rate == 0.0

    def test_tracks_all_counters(self):
        """Should track all counter fields."""
        result = ParseResult(
            transactions=[],
            total_rows_processed=100,
            rows_skipped=20,
            payments_filtered=10,
            duplicates_filtered=5,
        )
        assert result.total_rows_processed == 100
        assert result.rows_skipped == 20
        assert result.payments_filtered == 10
        assert result.duplicates_filtered == 5

    def test_default_empty_lists(self):
        """Should initialize empty error and warning lists."""
        result = ParseResult(transactions=[])
        assert result.errors == []
        assert result.warnings == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
