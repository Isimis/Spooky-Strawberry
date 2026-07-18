/* Spooky Strawberry — interakcje frontu sklepu */
(function () {
  "use strict";

  // --- Mobilna szuflada menu ---
  window.ssToggleDrawer = function (open) {
    var d = document.getElementById("mobileDrawer");
    if (!d) return;
    d.classList.toggle("open", open);
    document.body.style.overflow = open ? "hidden" : "";
  };

  // --- Arkusz filtrów (katalog, mobile) ---
  window.ssToggleSheet = function (open) {
    var s = document.getElementById("filterSheet");
    if (!s) return;
    s.classList.toggle("open", open);
    document.body.style.overflow = open ? "hidden" : "";
  };

  document.addEventListener("click", function (e) {
    // Akordeony (PDP / FAQ)
    var head = e.target.closest(".acc-h, .faq-h");
    if (head) {
      var body = head.nextElementSibling;
      if (body) {
        var isOpen = body.classList.toggle("open");
        var icon = head.querySelector(".acc-ic");
        if (icon) icon.textContent = isOpen ? "–" : "+";
      }
    }
  });

  // --- Licznik ilości (PDP) ---
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-qty]");
    if (!btn) return;
    var wrap = btn.closest(".qty");
    if (!wrap) return;
    var span = wrap.querySelector("span");
    var input = document.querySelector(wrap.dataset.input || "#qtyInput");
    var val = parseInt(span.textContent, 10) || 1;
    val += btn.dataset.qty === "inc" ? 1 : -1;
    if (val < 1) val = 1;
    span.textContent = val;
    if (input) input.value = val;
  });

  // --- Galeria PDP: kliknięcie miniatury podmienia główne zdjęcie ---
  function ssSetVariantTag(value) {
    var tag = document.getElementById("pdpVariantTag");
    if (!tag) return;
    var v = (value || "").trim();
    tag.textContent = v;
    tag.hidden = !v;
  }
  document.addEventListener("click", function (e) {
    var thumb = e.target.closest("[data-gallery-thumb]");
    if (!thumb) return;
    var main = document.getElementById("pdpMain");
    var src = thumb.getAttribute("data-full");
    if (main && src) main.src = src;
    if (main) main.setAttribute("data-variant", thumb.getAttribute("data-variant") || "");
    ssSetVariantTag(thumb.getAttribute("data-variant"));
  });
  // Inicjalizacja znacznika wariantu z głównego zdjęcia.
  (function () {
    var main = document.getElementById("pdpMain");
    if (main) ssSetVariantTag(main.getAttribute("data-variant"));
  })();

  // --- Lightbox PDP: klik w główne zdjęcie otwiera galerię na środku ekranu ---
  (function pdpLightbox() {
    var media = document.querySelector(".pdp-media");
    if (!media) return;
    var sources = Array.prototype.map.call(
      media.querySelectorAll("[data-gallery-src]"),
      function (el) {
        return { full: el.getAttribute("data-full"), alt: el.getAttribute("data-alt") || "" };
      }
    );
    if (!sources.length) return;

    var main = document.getElementById("pdpMain");
    var current = 0;
    var overlay = null;
    var imgEl = null;
    var countEl = null;

    function build() {
      overlay = document.createElement("div");
      overlay.className = "lightbox";
      overlay.innerHTML =
        '<button class="lb-close" type="button" aria-label="Zamknij">×</button>' +
        '<button class="lb-nav lb-prev" type="button" aria-label="Poprzednie zdjęcie">‹</button>' +
        '<figure class="lb-stage"><img alt=""></figure>' +
        '<button class="lb-nav lb-next" type="button" aria-label="Następne zdjęcie">›</button>' +
        '<div class="lb-count"></div>';
      document.body.appendChild(overlay);
      imgEl = overlay.querySelector("img");
      countEl = overlay.querySelector(".lb-count");
      overlay.querySelector(".lb-close").addEventListener("click", close);
      overlay.querySelector(".lb-prev").addEventListener("click", function (e) {
        e.stopPropagation();
        show(current - 1);
      });
      overlay.querySelector(".lb-next").addEventListener("click", function (e) {
        e.stopPropagation();
        show(current + 1);
      });
      overlay.addEventListener("click", function (e) {
        if (e.target === overlay || e.target.classList.contains("lb-stage")) close();
      });
    }

    function show(index) {
      var n = sources.length;
      current = ((index % n) + n) % n;
      imgEl.src = sources[current].full;
      imgEl.alt = sources[current].alt;
      countEl.textContent = current + 1 + " / " + n;
      countEl.hidden = n < 2;
      var hideNav = n < 2;
      overlay.querySelector(".lb-prev").hidden = hideNav;
      overlay.querySelector(".lb-next").hidden = hideNav;
    }

    function open(index) {
      if (!overlay) build();
      show(index);
      overlay.classList.add("open");
      document.body.style.overflow = "hidden";
    }

    function close() {
      if (overlay) overlay.classList.remove("open");
      document.body.style.overflow = "";
    }

    function currentMainIndex() {
      if (!main) return 0;
      var src = main.getAttribute("src");
      for (var i = 0; i < sources.length; i++) {
        if (sources[i].full === src) return i;
      }
      return 0;
    }

    if (main) {
      main.style.cursor = "zoom-in";
      main.addEventListener("click", function () {
        open(currentMainIndex());
      });
    }

    document.addEventListener("keydown", function (e) {
      if (!overlay || !overlay.classList.contains("open")) return;
      if (e.key === "ArrowLeft") show(current - 1);
      else if (e.key === "ArrowRight") show(current + 1);
      else if (e.key === "Escape") close();
    });
  })();

  // --- Baner cookie ---
  var COOKIE_KEY = "ss_cookie_consent";
  var ANALYTICS_COOKIE = "ss_analytics_consent";
  var COOKIE_MAX_AGE = 60 * 60 * 24 * 365;

  function setConsentCookie(name, value) {
    var cookie = name + "=" + encodeURIComponent(value) + "; Max-Age=" + COOKIE_MAX_AGE + "; Path=/; SameSite=Lax";
    if (window.location.protocol === "https:") cookie += "; Secure";
    document.cookie = cookie;
  }

  function storedAnalyticsConsent(consent) {
    if (!consent) return null;
    if (consent === "all") return true;
    if (consent === "essential") return false;
    try {
      return JSON.parse(consent).analytics === true;
    } catch (err) {
      return false;
    }
  }

  function syncAnalyticsConsent(consent) {
    var analytics = storedAnalyticsConsent(consent);
    if (analytics !== null) setConsentCookie(ANALYTICS_COOKIE, analytics ? "1" : "0");
  }

  function hideCookieBar() {
    var bar = document.getElementById("cookieBar");
    if (bar) bar.hidden = true;
  }
  window.ssCookie = function (level) {
    try { localStorage.setItem(COOKIE_KEY, level); } catch (err) {}
    syncAnalyticsConsent(level);
    hideCookieBar();
  };
  window.ssSaveCookiePrefs = function (acceptAll) {
    var prefs = { essential: true };
    document.querySelectorAll(".switch[data-pref]").forEach(function (sw) {
      prefs[sw.getAttribute("data-pref")] = acceptAll ? true : sw.classList.contains("on");
      if (acceptAll) sw.classList.add("on");
    });
    try { localStorage.setItem(COOKIE_KEY, JSON.stringify(prefs)); } catch (err) {}
    syncAnalyticsConsent(JSON.stringify(prefs));
    hideCookieBar();
    var note = document.getElementById("cookieSaved");
    if (note) note.style.display = "block";
  };

  // Przełączniki preferencji cookie (poza zablokowanymi)
  document.addEventListener("click", function (e) {
    var sw = e.target.closest(".switch[data-pref]");
    if (!sw || sw.classList.contains("lock")) return;
    sw.classList.toggle("on");
  });

  (function initCookiePrefs() {
    var switches = document.querySelectorAll(".switch[data-pref]");
    if (!switches.length) return;
    var consent = null;
    try { consent = localStorage.getItem(COOKIE_KEY); } catch (err) {}
    var prefs = {};
    if (consent === "all") {
      switches.forEach(function (sw) { prefs[sw.getAttribute("data-pref")] = true; });
    } else if (consent && consent !== "essential") {
      try { prefs = JSON.parse(consent) || {}; } catch (err) { prefs = {}; }
    }
    switches.forEach(function (sw) {
      sw.classList.toggle("on", prefs[sw.getAttribute("data-pref")] === true);
    });
  })();

  // Radio-cards (dostawa / płatność): zaznaczenie wizualne
  document.addEventListener("change", function (e) {
    var input = e.target.closest('.radio-card input[type="radio"]');
    if (!input) return;
    document
      .querySelectorAll('.radio-card input[name="' + input.name + '"]')
      .forEach(function (other) {
        var card = other.closest(".radio-card");
        if (card) card.classList.toggle("sel", other.checked);
      });
  });

  // Pokaż baner, jeśli brak zapisanej zgody
  (function initCookieBar() {
    var bar = document.getElementById("cookieBar");
    if (!bar) return;
    var consent = null;
    try { consent = localStorage.getItem(COOKIE_KEY); } catch (err) {}
    syncAnalyticsConsent(consent);
    if (!consent) bar.hidden = false;
  })();

  // --- Toast "Dodano do koszyka" ---
  var CHECK_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>';
  // Toast siada nad paskiem cookie (jeśli widoczny), żeby się z nim nie zlewał.
  function toastBottomOffset() {
    var bar = document.getElementById("cookieBar");
    if (bar && !bar.hidden) return bar.offsetHeight + 16;
    return 26;
  }
  function ensureToastWrap() {
    var wrap = document.getElementById("toastWrap");
    if (!wrap) {
      wrap = document.createElement("div");
      wrap.id = "toastWrap";
      wrap.className = "toast-wrap";
      document.body.appendChild(wrap);
    }
    wrap.style.bottom = toastBottomOffset() + "px";
    return wrap;
  }
  function showToast(msg, opts) {
    opts = opts || {};
    var wrap = ensureToastWrap();
    var toast = document.createElement("div");
    toast.className = "toast";
    toast.innerHTML = '<span class="tk">' + CHECK_SVG + '</span><span class="toast-msg"></span>';
    toast.querySelector(".toast-msg").textContent = msg || "";
    if (opts.link) {
      var a = document.createElement("a");
      a.href = opts.link.href;
      a.textContent = opts.link.label;
      toast.appendChild(a);
    }
    wrap.appendChild(toast);
    requestAnimationFrame(function () { toast.classList.add("show"); });
    setTimeout(function () {
      toast.classList.remove("show");
      setTimeout(function () { if (toast.parentNode) toast.parentNode.removeChild(toast); }, 350);
    }, opts.duration || 3400);
  }
  window.ssShowToast = showToast;

  // Komunikaty Django (np. „Konto założone") pokazujemy jako toasty w tym samym miejscu.
  (function () {
    var box = document.getElementById("djangoMessages");
    if (!box) return;
    var nodes = box.querySelectorAll("span");
    Array.prototype.forEach.call(nodes, function (n, i) {
      setTimeout(function () { showToast(n.textContent); }, i * 260);
    });
  })();

  function updateCartCount(count) {
    var dot = document.getElementById("cartCount");
    if (!dot) return;
    dot.textContent = count;
    dot.hidden = !count;
  }

  // Dodawanie do koszyka bez przeładowania (AJAX) — z degradacją do zwykłego POST
  document.addEventListener("submit", function (e) {
    var form = e.target.closest("form.js-cart-add");
    if (!form) return;
    e.preventDefault();
    var btn = form.querySelector('[type="submit"]');
    if (btn && btn.disabled) return;
    fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      headers: { "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
    })
      .then(function (r) { return r.ok ? r.json() : Promise.reject(); })
      .then(function (data) {
        if (data.cart_count !== undefined) updateCartCount(data.cart_count);
        // Na stronie koszyka dodanie polecanej rzeczy odświeża widok, żeby od razu
        // pojawiła się na liście i przeliczyło się podsumowanie.
        if (data.ok !== false && form.dataset.cartReload) {
          window.location.reload();
          return;
        }
        showToast(data.message || "Dodano do koszyka 🍓", { link: { href: "/koszyk/", label: "Zobacz koszyk" } });
      })
      .catch(function () { form.submit(); });
  });

  // Zapis do newslettera bez przeładowania — zamienia kafelek na potwierdzenie
  document.addEventListener("submit", function (e) {
    var form = e.target.closest("form.js-newsletter-form");
    if (!form) return;
    e.preventDefault();
    var card = form.closest(".nl");
    fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      headers: { "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
    })
      .then(function (r) { return r.ok ? r.json() : Promise.reject(); })
      .then(function (data) {
        if (!data.ok || !card) { form.submit(); return; }
        card.innerHTML =
          '<div class="nl-deco"></div>' +
          '<div class="nl-chip">' + CHECK_SVG + " Klub Spooky</div>" +
          "<h3></h3><p></p>" +
          '<div class="fine">Nie widzisz maila? Sprawdź folder spam.</div>';
        card.querySelector("h3").textContent = data.heading || "Jesteś w klubie! 🍓";
        card.querySelector("p").textContent = data.message || "";
      })
      .catch(function () { form.submit(); });
  });
})();
