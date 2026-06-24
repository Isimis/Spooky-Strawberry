/* Edytor maili panelu Spooky — toolbar, pola scalania, podgląd na żywo. */
(function () {
    "use strict";

    function highlightMergeTags(html) {
        return html.replace(/{{\s*([\w.]+)\s*}}/g, '<span class="mailcomposer__merge">{{ $1 }}</span>');
    }

    function initComposer(root) {
        var area = root.querySelector("[data-mc-area]");
        var input = root.querySelector("[data-mc-input]");
        var subject = root.querySelector("[data-mc-subject]");
        var previewBody = root.querySelector("[data-mc-preview-body]");
        var previewSubject = root.querySelector("[data-mc-preview-subject]");
        if (!area || !input) return;

        var sourceMode = false;
        var savedRange = null;

        function currentHtml() {
            return sourceMode ? input.value : area.innerHTML;
        }

        function syncInput() {
            if (!sourceMode) input.value = area.innerHTML;
        }

        function renderPreview() {
            var html = currentHtml().trim();
            if (previewBody) {
                previewBody.innerHTML = html
                    ? highlightMergeTags(html)
                    : '<p class="mailcomposer__mail-empty">Treść wiadomości pojawi się tutaj…</p>';
            }
            if (previewSubject) {
                var subj = subject ? subject.value.trim() : "";
                previewSubject.innerHTML = subj
                    ? highlightMergeTags(subj.replace(/</g, "&lt;"))
                    : '<span class="mailcomposer__mail-empty">(brak tematu)</span>';
            }
        }

        function update() {
            syncInput();
            renderPreview();
        }

        function saveRange() {
            var sel = window.getSelection();
            if (sel && sel.rangeCount && area.contains(sel.anchorNode)) {
                savedRange = sel.getRangeAt(0);
            }
        }

        // --- pasek narzędzi -------------------------------------------------
        root.querySelectorAll(".mailcomposer__tool[data-cmd]").forEach(function (btn) {
            btn.addEventListener("click", function () {
                if (sourceMode) return;
                area.focus();
                if (savedRange) {
                    var sel = window.getSelection();
                    sel.removeAllRanges();
                    sel.addRange(savedRange);
                }
                var cmd = btn.dataset.cmd;
                var val = btn.dataset.val || null;
                if (cmd === "createLink") {
                    val = window.prompt("Adres linku (URL):", "https://");
                    if (!val) return;
                }
                document.execCommand(cmd, false, val);
                saveRange();
                update();
            });
        });

        // --- pola scalania --------------------------------------------------
        root.querySelectorAll("[data-mc-tag]").forEach(function (btn) {
            btn.addEventListener("click", function () {
                var tag = btn.dataset.mcTag;
                if (sourceMode) {
                    var pos = input.selectionStart != null ? input.selectionStart : input.value.length;
                    input.value = input.value.slice(0, pos) + tag + input.value.slice(input.selectionEnd);
                    input.focus();
                    input.selectionStart = input.selectionEnd = pos + tag.length;
                    renderPreview();
                    return;
                }
                area.focus();
                if (savedRange) {
                    var sel = window.getSelection();
                    sel.removeAllRanges();
                    sel.addRange(savedRange);
                }
                document.execCommand("insertText", false, tag);
                saveRange();
                update();
            });
        });

        // --- przełącznik kodu HTML -----------------------------------------
        var sourceBtn = root.querySelector("[data-mc-source]");
        if (sourceBtn) {
            sourceBtn.addEventListener("click", function () {
                sourceMode = !sourceMode;
                sourceBtn.classList.toggle("is-active", sourceMode);
                if (sourceMode) {
                    input.value = area.innerHTML;
                    input.hidden = false;
                    area.hidden = true;
                    input.focus();
                } else {
                    area.innerHTML = input.value;
                    input.hidden = true;
                    area.hidden = false;
                    area.focus();
                }
                renderPreview();
            });
        }

        // --- zdarzenia ------------------------------------------------------
        area.addEventListener("input", update);
        area.addEventListener("keyup", saveRange);
        area.addEventListener("mouseup", saveRange);
        area.addEventListener("focus", saveRange);
        input.addEventListener("input", renderPreview);
        if (subject) subject.addEventListener("input", renderPreview);

        var form = root.closest("form");
        if (form) form.addEventListener("submit", syncInput);

        renderPreview();
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("[data-mailcomposer]").forEach(initComposer);
    });
})();
