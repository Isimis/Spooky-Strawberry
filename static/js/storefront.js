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
  document.addEventListener("click", function (e) {
    var thumb = e.target.closest("[data-gallery-thumb]");
    if (!thumb) return;
    var main = document.getElementById("pdpMain");
    var src = thumb.getAttribute("data-full");
    if (main && src) main.src = src;
  });

  // --- Baner cookie ---
  var COOKIE_KEY = "ss_cookie_consent";
  function hideCookieBar() {
    var bar = document.getElementById("cookieBar");
    if (bar) bar.hidden = true;
  }
  window.ssCookie = function (level) {
    try { localStorage.setItem(COOKIE_KEY, level); } catch (err) {}
    hideCookieBar();
  };
  window.ssSaveCookiePrefs = function (acceptAll) {
    var prefs = { essential: true };
    document.querySelectorAll(".switch[data-pref]").forEach(function (sw) {
      prefs[sw.getAttribute("data-pref")] = acceptAll ? true : sw.classList.contains("on");
      if (acceptAll) sw.classList.add("on");
    });
    try { localStorage.setItem(COOKIE_KEY, JSON.stringify(prefs)); } catch (err) {}
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
    if (!consent) bar.hidden = false;
  })();

  // --- Toast "Dodano do koszyka" ---
  var CHECK_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>';
  var toastTimer;
  function showToast(msg) {
    var wrap = document.getElementById("toastWrap");
    if (!wrap) {
      wrap = document.createElement("div");
      wrap.id = "toastWrap";
      wrap.className = "toast-wrap";
      document.body.appendChild(wrap);
    }
    wrap.innerHTML =
      '<div class="toast"><span class="tk">' + CHECK_SVG + "</span>" +
      (msg || "Dodano do koszyka") +
      ' <a href="/koszyk/">Zobacz koszyk</a></div>';
    var t = wrap.firstElementChild;
    requestAnimationFrame(function () { t.classList.add("show"); });
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.classList.remove("show"); }, 3200);
  }
  window.ssShowToast = showToast;

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
        showToast(data.message || "Dodano do koszyka 🍓");
      })
      .catch(function () { form.submit(); });
  });
})();
