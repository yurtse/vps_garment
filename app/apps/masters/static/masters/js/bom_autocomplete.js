document.addEventListener("DOMContentLoaded", function () {
    const input = document.querySelector("#id_product_plant_name");
    const hiddenInput = document.querySelector("#id_product_plant");
    console.log("Input found:", !!input, "Hidden input found:", !!hiddenInput); // Debug
    if (!input || !hiddenInput) {
        console.error("Input or hidden input not found");
        return;
    }

    const dropdown = document.createElement("div");
    dropdown.className = 'autocomplete-dropdown';
	dropdown.style.position = 'absolute';
	dropdown.style.display = 'none';
	dropdown.style.zIndex = '2147483000';
	dropdown.style.background = 'rgba(255,255,255,0.96)';   // almost opaque so text is visible
	dropdown.style.boxSizing = 'border-box';
	dropdown.style.pointerEvents = 'auto';
	dropdown.style.maxHeight = '420px';
	dropdown.style.overflowY = 'auto';
	dropdown.style.padding = '4px 0';
	document.body.appendChild(dropdown);

    input.setAttribute("aria-controls", "autocomplete-dropdown");

    function positionDropdown() {
        const rect = input.getBoundingClientRect();
        const left = rect.left + window.scrollX;
        const top = rect.bottom + window.scrollY + 2;
        dropdown.style.left = `${left}px`;
        dropdown.style.top = `${top}px`;
        dropdown.style.minWidth = `${rect.width}px`;
        dropdown.style.maxWidth = `${Math.max(rect.width, 420)}px`;
    }

    window.addEventListener("resize", positionDropdown);
    window.addEventListener("scroll", positionDropdown, true);
    input.addEventListener("focus", positionDropdown);

    let currentIndex = -1;
    let results = [];
    let abortController = null;

    function clearDropdown() {
        dropdown.innerHTML = "";
        dropdown.style.display = "none";
        currentIndex = -1;
        results = [];
    }

    function renderDropdown(items) {
        dropdown.innerHTML = "";
        console.log("Rendering dropdown, items:", items.length); // Debug
        if (!items || items.length === 0) {
            console.log("No items to render");
            clearDropdown();
            return;
        }

		items.forEach((item, idx) => {
			const div = document.createElement('div');
			div.className = 'autocomplete-item';
			div.textContent = item.text || item.name || item.label || '';
			div.dataset.id = item.id;
			div.dataset.index = String(idx);
			div.setAttribute('role', 'option');
			div.tabIndex = -1;

			// Inline defaults so items are visible even if CSS missing/overridden
			div.style.display = 'block';
			div.style.background = 'transparent';
			div.style.color = '#111';           // visible dark text
			div.style.padding = '8px 12px';
			div.style.whiteSpace = 'nowrap';
			div.style.overflow = 'hidden';
			div.style.textOverflow = 'ellipsis';
			div.style.boxSizing = 'border-box';

			div.addEventListener('mousedown', (e) => {
				e.preventDefault();
				selectItem(idx);
			});
			dropdown.appendChild(div);
		});

        results = items.slice();
        currentIndex = -1;
        updateHighlight();
        positionDropdown();
        dropdown.style.display = "block";
    }

    function selectItem(index) {
        if (index < 0 || index >= results.length) return;
        const item = results[index];
        input.value = item.text || item.name || item.label || "";
        hiddenInput.value = item.id || "";

        const evHidden = new Event("change", { bubbles: true });
        hiddenInput.dispatchEvent(evHidden);
        const evInput = new Event("change", { bubbles: true });
        input.dispatchEvent(evInput);

        clearDropdown();
        input.blur();
    }

	function updateHighlight() {
		const children = Array.from(dropdown.querySelectorAll('.autocomplete-item'));
		if (!children || children.length === 0) return;

		// clamp currentIndex
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


    async function fetchResults(query) {
        if (abortController) abortController.abort();
        abortController = new AbortController();
        const url = `/masters/api/autocomplete/fg/?q=${encodeURIComponent(query)}&page=1`;
        try {
            const resp = await fetch(url, { signal: abortController.signal, credentials: "same-origin", headers: { "Accept": "application/json" } });
            if (!resp.ok) throw new Error("Network error: " + resp.status);
            const data = await resp.json();
            console.log("API response:", data); // Debug
            const items = data.results || [];
            renderDropdown(items);
        } catch (e) {
            if (e.name !== "AbortError") {
                console.error("Autocomplete fetch error:", e);
            }
            clearDropdown();
        }
    }

    let debounceTimer = null;
    input.addEventListener("input", function () {
        const q = this.value.trim();
        hiddenInput.value = "";
        if (debounceTimer) clearTimeout(debounceTimer);
        if (!q) {
            clearDropdown();
            return;
        }
        debounceTimer = setTimeout(() => fetchResults(q), 250);
    });

    input.addEventListener("keydown", function (e) {
        const key = e.key;
        console.log("Keydown detected, key:", key);
        if (["ArrowDown", "ArrowUp", "Enter", "Escape"].includes(key)) {
            e.preventDefault();
            e.stopImmediatePropagation();
        }
        if (dropdown.style.display !== "block" || !results.length) {
            if (key === "Escape") {
                clearDropdown();
            }
            return;
        }
        if (key === "ArrowDown") {
            currentIndex = Math.min(currentIndex + 1, results.length - 1);
            updateHighlight();
            positionDropdown();
        } else if (key === "ArrowUp") {
            currentIndex = Math.max(currentIndex - 1, -1);
            updateHighlight();
            positionDropdown();
        } else if (key === "Enter") {
            if (currentIndex === -1 && results.length > 0) currentIndex = 0;
            if (currentIndex !== -1) selectItem(currentIndex);
        } else if (key === "Escape") {
            clearDropdown();
        }
    }, true);

    document.addEventListener("click", function (e) {
        if (!dropdown.contains(e.target) && e.target !== input) {
            clearDropdown();
        }
    });
});