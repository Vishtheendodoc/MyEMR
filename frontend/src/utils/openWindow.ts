/** Open an EMR route in a separate browser window (keeps the current chart/desk page). */
export function openAppWindow(path: string, title = 'Endo EMR') {
  const url = path.startsWith('http')
    ? path
    : `${window.location.origin}${path.startsWith('/') ? path : `/${path}`}${path.includes('?') ? '&' : '?'}popup=1`;
  const features = 'noopener,noreferrer,width=1100,height=800,menubar=no,toolbar=no,location=yes,status=yes';
  const win = window.open(url, title.replace(/\s+/g, '_'), features);
  if (!win) {
    window.alert('Allow pop-ups to open this in a new window.');
  }
  return win;
}
