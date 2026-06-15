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
})();
