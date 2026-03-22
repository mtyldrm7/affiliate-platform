(function () {
  'use strict';

  /* ── Ayarlar ──────────────────────────────────────────────────────────── */
  var WINDOWS = [
    { start: '11:30', end: '13:00' },
    { start: '18:00', end: '20:00' }
  ];
  var STORAGE_KEY = 'aff_v1';

  /* ── Script tag'inden ref kodu al ────────────────────────────────────── */
  var scriptTag = document.currentScript ||
    (function () {
      var scripts = document.getElementsByTagName('script');
      return scripts[scripts.length - 1];
    })();
  var refCode = scriptTag.getAttribute('data-ref') || '';
  var affiliateUrl = scriptTag.getAttribute('data-url') || 'https://www.yemeksepeti.com';

  if (!refCode) return; // ref kodu yoksa hiç çalışma

  /* ── Zaman kontrolü ──────────────────────────────────────────────────── */
  function toMinutes(hhmm) {
    var parts = hhmm.split(':');
    return parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
  }

  function isInWindow() {
    var now = new Date();
    var current = now.getHours() * 60 + now.getMinutes();
    return WINDOWS.some(function (w) {
      return current >= toMinutes(w.start) && current <= toMinutes(w.end);
    });
  }

  /* ── LocalStorage yardımcıları ───────────────────────────────────────── */
  function todayKey() {
    var d = new Date();
    return d.getFullYear() + '-' + (d.getMonth() + 1) + '-' + d.getDate();
  }

  function getState() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    } catch (e) {
      return {};
    }
  }

  function setState(obj) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(obj));
    } catch (e) {}
  }

  function hasSeenToday() {
    return getState()[todayKey()] !== undefined;
  }

  function markSeen(dismissed) {
    var state = getState();
    state[todayKey()] = dismissed ? 'dismissed' : 'closed';
    setState(state);
  }

  /* ── Banner oluştur ──────────────────────────────────────────────────── */
  function buildBanner() {
    /* Stil */
    var style = document.createElement('style');
    style.textContent = [
      '#aff-banner{',
        'position:fixed;bottom:20px;right:20px;',
        'width:300px;',
        'background:#1a1a2e;',
        'border:1px solid #ff6b35;',
        'border-radius:12px;',
        'padding:14px 16px;',
        'box-shadow:0 4px 24px rgba(0,0,0,.5);',
        'font-family:system-ui,sans-serif;',
        'font-size:14px;',
        'color:#e0e0f0;',
        'z-index:2147483647;',
        'animation:aff-slide .35s ease;',
        'line-height:1.4;',
      '}',
      '@keyframes aff-slide{',
        'from{opacity:0;transform:translateY(16px)}',
        'to{opacity:1;transform:translateY(0)}',
      '}',
      '#aff-banner.aff-hide{',
        'animation:aff-fade .3s ease forwards;',
      '}',
      '@keyframes aff-fade{',
        'to{opacity:0;transform:translateY(12px)}',
      '}',
      '#aff-banner .aff-close{',
        'position:absolute;top:8px;right:10px;',
        'background:none;border:none;color:#8080a0;',
        'font-size:18px;cursor:pointer;line-height:1;padding:0;',
      '}',
      '#aff-banner .aff-close:hover{color:#e0e0f0}',
      '#aff-banner .aff-logo{',
        'font-size:11px;color:#ff6b35;font-weight:700;',
        'letter-spacing:.5px;margin-bottom:6px;',
      '}',
      '#aff-banner .aff-msg{margin-bottom:12px;color:#c0c0d8}',
      '#aff-banner .aff-btns{display:flex;gap:8px}',
      '#aff-banner .aff-yes{',
        'flex:1;padding:7px;border:none;border-radius:7px;',
        'background:#ff6b35;color:#fff;font-size:13px;',
        'font-weight:600;cursor:pointer;',
      '}',
      '#aff-banner .aff-yes:hover{background:#e55a24}',
      '#aff-banner .aff-no{',
        'flex:1;padding:7px;border:1px solid #3a3a5a;border-radius:7px;',
        'background:transparent;color:#8080a0;font-size:13px;cursor:pointer;',
      '}',
      '#aff-banner .aff-no:hover{color:#c0c0d0;border-color:#6060a0}',
    ].join('');
    document.head.appendChild(style);

    /* Banner HTML */
    var banner = document.createElement('div');
    banner.id = 'aff-banner';
    banner.setAttribute('role', 'dialog');
    banner.setAttribute('aria-label', 'Yemeksepeti indirim teklifi');
    banner.innerHTML =
      '<button class="aff-close" aria-label="Kapat">×</button>' +
      '<div class="aff-logo">🍔 YEMEKSEPETI</div>' +
      '<div class="aff-msg">Şu an siparişlerde <strong>özel indirimler</strong> var! Hemen göz atmak ister misin?</div>' +
      '<div class="aff-btns">' +
        '<button class="aff-yes">Siparişe Git</button>' +
        '<button class="aff-no">Hayır teşekkürler</button>' +
      '</div>';

    document.body.appendChild(banner);

    /* Olaylar */
    function dismiss(permanently) {
      banner.classList.add('aff-hide');
      markSeen(permanently);
      setTimeout(function () {
        if (banner.parentNode) banner.parentNode.removeChild(banner);
      }, 320);
    }

    banner.querySelector('.aff-close').addEventListener('click', function () {
      dismiss(false); // sadece kapat — yarın tekrar göster
    });

    banner.querySelector('.aff-no').addEventListener('click', function () {
      dismiss(true); // "hayır" — bugün bir daha gösterme
    });

    banner.querySelector('.aff-yes').addEventListener('click', function () {
      markSeen(true);
      window.open(affiliateUrl + '?ref=' + refCode, '_blank', 'noopener');
      dismiss(true);
    });
  }

  /* ── Ana akış ─────────────────────────────────────────────────────────── */
  function maybeShow() {
    if (hasSeenToday()) return;  // bugün zaten gördü
    if (!isInWindow()) return;   // zaman dilimi dışında

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', buildBanner);
    } else {
      // Sayfa yüklendikten 1 saniye sonra göster — oyun/uygulama kesilmesin
      setTimeout(buildBanner, 1000);
    }
  }

  maybeShow();

})();
