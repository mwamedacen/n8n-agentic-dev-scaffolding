/**
 * Prepare validated purchase order data for AI categorization.
 * Hydrated into n8n Code nodes via the js placeholder system.
 */
function prepareReconciliationData(validatedData) {
  const records = validatedData.validated_records || [];

  // Filter to valid records only
  const validRecords = records.filter(r => r.is_valid);

  // Group by vendor
  const byVendor = {};
  validRecords.forEach(record => {
    const vendor = record.vendor || 'UNKNOWN';
    if (!byVendor[vendor]) {
      byVendor[vendor] = { count: 0, total: 0, records: [] };
    }
    byVendor[vendor].count++;
    byVendor[vendor].total += record.amount || 0;
    byVendor[vendor].records.push({
      po_number: record.po_number,
      amount: record.amount,
      date: record.date,
      description: record.description,
      status: record.status,
    });
  });

  // Identify potential duplicates (same vendor + same amount + same date)
  const potentialDuplicates = [];
  const seen = new Map();
  validRecords.forEach(record => {
    const key = `${record.vendor}|${record.amount}|${record.date}`;
    if (seen.has(key)) {
      potentialDuplicates.push({
        original_po: seen.get(key),
        duplicate_po: record.po_number,
        vendor: record.vendor,
        amount: record.amount,
        date: record.date,
      });
    } else {
      seen.set(key, record.po_number);
    }
  });

  return {
    vendor_summary: byVendor,
    potential_duplicates: potentialDuplicates,
    total_valid_records: validRecords.length,
    total_amount: validRecords.reduce((sum, r) => sum + (r.amount || 0), 0),
    records_for_categorization: validRecords.map(r => ({
      po_number: r.po_number,
      vendor: r.vendor,
      amount: r.amount,
      description: r.description,
    })),
  };
}
