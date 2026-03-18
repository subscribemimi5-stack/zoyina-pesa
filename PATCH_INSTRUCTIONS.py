"""
=====================================================================
PATCH YA app.py — Ongeza routes 2 tu (kabla ya if __name__ == "__main__")
Hakuna kinachobadilishwa — chongeza mstari huu tu.
=====================================================================
"""

# ── Ongeza hii baada ya: @app.route('/level_card') ... ──

@app.route('/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json',
        mimetype='application/manifest+json')

# (Route ya sw.js ipo tayari mwishoni mwa app.py — hakuna haja ya kuiongeza tena)


"""
=====================================================================
PATCH YA templates/base.html — Ongeza ndani ya <head> ... </head>
=====================================================================

<!-- PWA Meta Tags -->
<link rel="manifest" href="/manifest.json">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="{{ site_name }}">
<link rel="apple-touch-icon" href="/static/icons/icon-192x192.png">
<meta name="theme-color" content="{{ primary_color }}">

<!-- Install Button Style -->
<style>
  #pwa-install-btn {
    display: none;
    position: fixed;
    bottom: 80px;
    right: 16px;
    z-index: 9999;
    background: #00C853;
    color: #000;
    border: none;
    border-radius: 50px;
    padding: 12px 20px;
    font-size: 0.9rem;
    font-weight: 700;
    cursor: pointer;
    box-shadow: 0 4px 20px rgba(0,200,83,0.5);
    animation: pulse-btn 2s infinite;
    align-items: center;
    gap: 8px;
  }
  #pwa-install-btn.visible { display: flex; }
  @keyframes pulse-btn {
    0%,100% { box-shadow: 0 4px 20px rgba(0,200,83,0.5); }
    50%      { box-shadow: 0 4px 32px rgba(0,200,83,0.85); }
  }
</style>

=====================================================================
PATCH YA templates/base.html — Ongeza kabla ya </body>
=====================================================================

<!-- PWA Install Button -->
<button id="pwa-install-btn" onclick="installPWA()">
  📲 <span>Install App</span>
</button>

<script>
// ── Service Worker Registration ──
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/sw.js')
      .then(reg => console.log('SW registered:', reg.scope))
      .catch(err => console.log('SW error:', err));
  });
}

// ── PWA Install Prompt ──
let _deferredPrompt = null;
const installBtn = document.getElementById('pwa-install-btn');

window.addEventListener('beforeinstallprompt', e => {
  e.preventDefault();
  _deferredPrompt = e;
  installBtn.classList.add('visible');
});

async function installPWA() {
  if (!_deferredPrompt) return;
  installBtn.classList.remove('visible');
  _deferredPrompt.prompt();
  const { outcome } = await _deferredPrompt.userChoice;
  console.log('PWA install outcome:', outcome);
  _deferredPrompt = null;
}

// Ficha kitufe baada ya kuinstall
window.addEventListener('appinstalled', () => {
  installBtn.classList.remove('visible');
  _deferredPrompt = null;
  console.log('Zoyina Pesa imeinstallwa!');
});
</script>
