def validate_purchase_orders(records: list) -> dict:
    """
    Validate and normalize purchase order records.

    Args:
        records: List of dicts from Excel rows with keys like
                 po_number, vendor, amount, date, status, line_items

    Returns:
        Dict with validated records, validation errors, and summary stats
    """
    validated = []
    errors = []

    for i, record in enumerate(records):
        row_errors = []

        # Required fields check
        for field in ['po_number', 'vendor', 'amount']:
            if not record.get(field):
                row_errors.append(f"Missing required field: {field}")

        # Amount validation
        amount = record.get('amount')
        if amount is not None:
            try:
                amount = float(str(amount).replace(',', '').replace('$', ''))
                if amount < 0:
                    row_errors.append(f"Negative amount: {amount}")
            except (ValueError, TypeError):
                row_errors.append(f"Invalid amount format: {amount}")
                amount = None

        # Normalize record
        normalized = {
            'row_index': i,
            'po_number': str(record.get('po_number', '')).strip(),
            'vendor': str(record.get('vendor', '')).strip().upper(),
            'amount': amount,
            'date': str(record.get('date', '')).strip(),
            'status': str(record.get('status', 'PENDING')).strip().upper(),
            'description': str(record.get('description', '')).strip(),
            'is_valid': len(row_errors) == 0,
        }

        validated.append(normalized)

        if row_errors:
            errors.append({
                'row_index': i,
                'po_number': record.get('po_number', f'row_{i}'),
                'errors': row_errors
            })

    return {
        'validated_records': validated,
        'validation_errors': errors,
        'summary': {
            'total_records': len(records),
            'valid_count': sum(1 for r in validated if r['is_valid']),
            'error_count': len(errors),
            'total_amount': sum(r['amount'] for r in validated if r['amount'] is not None),
        }
    }
