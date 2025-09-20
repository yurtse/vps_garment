// /code/apps/masters/static/masters/js/bom_autocomplete.js
// Stable autocomplete adapted from your last-working file.
// - Keeps the exact keyboard behaviour (ArrowUp/Down/Enter/Escape)
// - Supports FG header (#id_product_plant_name) and inline component inputs
// - Calls endpoints at /masters/api/autocomplete/fg/ and /masters/api/autocomplete/components/
// - Shows server text (expects "text" field in results)

document.addEventListener("DOMContentLoaded", function () {
    // Header FG
    const headerInput = document.querySelector("#id_product_plant_name");
    const headerHidden = document.querySelector("#id_product_plant");

    // Inline component pickers (inputs must have data-autocomplete="masters-component" and data-hidden selector)
    const inlineInputs = Array.from(document.querySelectorAll('input[data-autocomplete="masters-component"]'));

    // If neither header nor any inline inputs exist, nothing to do
    if (!headerInput && inlineInputs.length === 0) {
        console.debug("bom_autocomplete: no target inputs found");
        return;
    }

    // core dropdown factory (creates one dropdown per input to avoid positioning conflicts)
    function makeDropdown() {
        const dropdown = document.createElement("div");
        dropdown.className = 'autocomplete-dropdown';
        dropdown.style.position = 'absolute';
        dropdown.style.display = 'none';
        dropdown.style.zIndex = '2147483000';
        dropdown.style.background = 'rgba(255,255,255,0.96)';
        dropdown.style.boxSizing = 'border-box';
        dropdown.style.pointerEvents = 'auto';
        dropdown.style.maxHeight = '420px';
        dropdown.style.overflowY = 'auto';
        dropdown.style.padding = '4px 0';
        document.body.appendChild(dropdown);
        return dropdown;
    }

    function positionDropdownForInput(dropdown, input) {
        const rect = input.getBoundingClientRect();
        const left = rect.left + window.scrollX;
        const top = rect.bottom + window.scrollY + 2;
        dropdown.style.left = `${left}px`;
        dropdown.style.top = `${top}px`;
        dropdown.style.minWidth = `${rect.width}px`;
        dropdown.style.maxWidth = `${Math.max(rect.width, 420)}px`;
    }

    // generic attach (kind: 'fg' or 'components', hiddenEl optional)
    function attachAutocompleteTo(input, hiddenEl, kind) {
        let results = [];
        let currentIndex = -1;
        let abortController = null;
        let debounceTimer = null;

        const dropdown = makeDropdown();

        function clearDropdown() {
            dropdown.innerHTML = "";
            dropdown.style.display = "none";
            currentIndex = -1;
            results = [];
        }

        function updateHighlight() {
            const children = Array.from(dropdown.querySelectorAll('.autocomplete-item'));
            if (!children || children.length === 0) return;

            if (currentIndex < -1) currentIndex = -1;
            if (currentIndex >= children.length) currentIndex = children.length - 1;

            children.forEach((c, i) => {
                const active = (i === currentIndex);
                c.classList.toggle('highlighted', active);

                if (active) {
                    // visible highlight inline (guaranteed)
                    c.style.background = 'rgba(0,123,255,0.95)';
                    c.style.color = '#ffffff';
                    c.style.fontWeight = '600';
                    c.scrollIntoView({ block: 'nearest' });
                    c.setAttribute('aria-selected', 'true');
                } else {
                    // reset to default inline appearance
                    c.style.background = 'transparent';
                    c.style.color = '#111';
                    c.style.fontWeight = '';
                    c.setAttribute('aria-selected', 'false');
                }
            });
        }

        function renderDropdown(items) {
            dropdown.innerHTML = "";
            if (!items || items.length === 0) {
                clearDropdown();
                return;
            }

            items.forEach((item, idx) => {
                const div = document.createElement('div');
                div.className = 'autocomplete-item';
                // Respect server "text" first, then fallback
                div.textContent = item.text || item.name || item.label || '';
                div.dataset.id = item.id;
                div.dataset.index = String(idx);
                div.setAttribute('role', 'option');
                div.tabIndex = -1;

                // inline style defaults to be robust if CSS fails
                div.style.display = 'block';
                div.style.background = 'transparent';
                div.style.color = '#111';
                div.style.padding = '8px 12px';
                div.style.whiteSpace = 'nowrap';
                div.style.overflow = 'hidden';
                div.style.textOverflow = 'ellipsis';
                div.style.boxSizing = 'border-box';
                div.style.cursor = 'pointer';

                div.addEventListener('mousedown', (e) => {
                    e.preventDefault(); // prevent blur
                    selectItem(idx);
                });

                div.addEventListener('mouseover', () => {
                    currentIndex = idx;
                    updateHighlight();
                });

                dropdown.appendChild(div);
            });

            results = items.slice();
            // keep previous index if valid, else reset
            if (currentIndex < 0 || currentIndex >= results.length) currentIndex = -1;
            updateHighlight();
            positionDropdownForInput(dropdown, input);
            dropdown.style.display = "block";
        }

        function selectItem(index) {
            if (index < 0 || index >= results.length) return;
            const item = results[index];
            input.value = item.text || item.name || item.label || "";
            if (hiddenEl) hiddenEl.value = item.id || "";

            // fire change events
            const evHidden = new Event("change", { bubbles: true });
            if (hiddenEl) hiddenEl.dispatchEvent(evHidden);
            const evInput = new Event("change", { bubbles: true });
            input.dispatchEvent(evInput);

            clearDropdown();
            input.blur();
        }

        async function fetchResults(query) {
            if (abortController) abortController.abort();
            abortController = new AbortController();

            // choose endpoint by kind
            const endpoint = (kind === 'components') ? 'components' : 'fg';
            // use masters root (project routes expect /masters/api/...)
            const url = `/masters/api/autocomplete/${endpoint}/?q=${encodeURIComponent(query)}&page=1`;
            try {
                const resp = await fetch(url, { signal: abortController.signal, credentials: "same-origin", headers: { "Accept": "application/json" } });
                if (!resp.ok) throw new Error("Network error: " + resp.status);
                const data = await resp.json();
                const items = data.results || [];
                renderDropdown(items);
            } catch (e) {
                if (e.name !== "AbortError") console.error("Autocomplete fetch error:", e);
                clearDropdown();
            }
        }

        // debounce wrapper for input event
        function scheduleFetch(q) {
            if (debounceTimer) clearTimeout(debounceTimer);
            if (!q) { clearDropdown(); return; }
            debounceTimer = setTimeout(() => fetchResults(q), 180);
        }

        // input events
        input.addEventListener("input", function () {
            // when user types, clear hidden selection
            if (hiddenEl) hiddenEl.value = "";
            const q = this.value.trim();
            scheduleFetch(q);
        });

        // focus/positioning
        input.addEventListener("focus", function () {
            positionDropdownForInput(dropdown, input);
            if (input.value && input.value.trim()) scheduleFetch(input.value.trim());
        });
        window.addEventListener("resize", () => { if (dropdown.style.display !== "none") positionDropdownForInput(dropdown, input); });
        window.addEventListener("scroll", () => { if (dropdown.style.display !== "none") positionDropdownForInput(dropdown, input); }, true);

        // keyboard handling: **exact behaviour from your last-working file**
        input.addEventListener("keydown", function (e) {
            const key = e.key;
            // only handle nav keys specially
            if (["ArrowDown", "ArrowUp", "Enter", "Escape"].includes(key)) {
                // prevent default navigation so arrow keys don't move page
                e.preventDefault();
                e.stopImmediatePropagation();
            }
            // if no dropdown open or no results, handle only Escape
            if (dropdown.style.display !== "block" || !results.length) {
                if (key === "Escape") {
                    clearDropdown();
                }
                return;
            }

            if (key === "ArrowDown") {
                currentIndex = Math.min(currentIndex + 1, results.length - 1);
                updateHighlight();
                positionDropdownForInput(dropdown, input);
            } else if (key === "ArrowUp") {
                currentIndex = Math.max(currentIndex - 1, -1);
                updateHighlight();
                positionDropdownForInput(dropdown, input);
            } else if (key === "Enter") {
                if (currentIndex === -1 && results.length > 0) currentIndex = 0;
                if (currentIndex !== -1) selectItem(currentIndex);
            } else if (key === "Escape") {
                clearDropdown();
            }
        }, true);

        // click outside closes dropdown
        document.addEventListener("click", function (e) {
            if (!dropdown.contains(e.target) && e.target !== input) {
                clearDropdown();
            }
        });

        // return object for debugging if needed
        return {
            input,
            dropdown,
            clear: clearDropdown
        };
    }

    // Attach to header FG if present
    if (headerInput && headerHidden) {
        attachAutocompleteTo(headerInput, headerHidden, 'fg');
    }

    // Attach to inline component inputs
    inlineInputs.forEach(inp => {
        const hidSelector = inp.dataset.hidden || null;
        const hidEl = hidSelector ? document.querySelector(hidSelector) : null;
        attachAutocompleteTo(inp, hidEl, 'components');
    });

}); // DOMContentLoaded
