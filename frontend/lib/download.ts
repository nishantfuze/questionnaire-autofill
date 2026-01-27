export function downloadCSV(csvContent: string, originalFilename: string): void {
  // Generate filename: filled_<original>_<date>.csv
  const baseName = originalFilename.replace(/\.[^/.]+$/, ''); // Remove extension
  const date = new Date().toISOString().split('T')[0]; // YYYY-MM-DD
  const downloadFilename = `filled_${baseName}_${date}.csv`;

  // Create blob and download
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);

  const link = document.createElement('a');
  link.href = url;
  link.download = downloadFilename;
  link.style.display = 'none';

  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  // Revoke blob URL after download
  setTimeout(() => URL.revokeObjectURL(url), 100);
}
