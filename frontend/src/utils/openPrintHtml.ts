/** Open HTML in a new tab for printing. Avoids blank about:blank from noopener + document.write. */
export function openPrintHtml(html: string, blockedMessage = 'Pop-up blocked. Allow pop-ups to print.') {
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const w = window.open(url, '_blank');
  if (!w) {
    URL.revokeObjectURL(url);
    alert(blockedMessage);
    return false;
  }
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  return true;
}
