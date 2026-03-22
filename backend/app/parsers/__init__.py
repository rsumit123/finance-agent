"""PDF parsers — lazy imports to avoid loading pdfplumber at module level."""


def parse_bank_statement(pdf_path):
    from .bank_parser import parse_bank_statement as _parse
    return _parse(pdf_path)


def parse_credit_card_statement(pdf_path):
    from .credit_card_parser import parse_credit_card_statement as _parse
    return _parse(pdf_path)


def parse_upi_statement(pdf_path):
    from .upi_parser import parse_upi_statement as _parse
    return _parse(pdf_path)


def detect_and_parse(pdf_path):
    from .auto_detect import detect_and_parse as _detect
    return _detect(pdf_path)
