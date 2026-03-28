/**
 * Process raw Excel data into a summary structure.
 * Hydrated into n8n Code nodes via the js placeholder system.
 */
function processExcelData(rows) {
  // Filter out empty/header rows
  const dataRows = rows.filter(row => row.date && row.amount);

  // Calculate summary metrics
  const totalAmount = dataRows.reduce((sum, row) => sum + (parseFloat(row.amount) || 0), 0);
  const rowCount = dataRows.length;
  const avgAmount = rowCount > 0 ? totalAmount / rowCount : 0;

  // Group by category
  const byCategory = {};
  dataRows.forEach(row => {
    const cat = row.category || 'Uncategorized';
    if (!byCategory[cat]) byCategory[cat] = { count: 0, total: 0 };
    byCategory[cat].count++;
    byCategory[cat].total += parseFloat(row.amount) || 0;
  });

  return {
    totalAmount: Math.round(totalAmount * 100) / 100,
    rowCount,
    avgAmount: Math.round(avgAmount * 100) / 100,
    categories: byCategory,
    processedAt: new Date().toISOString()
  };
}
