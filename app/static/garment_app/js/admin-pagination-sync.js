// admin-pagination-sync.js
(function () {
  "use strict";

  const BTN_ID = "admin-toggle-paginate";
  const SHOWALL_LINK_SELECTOR = "a.showall";

  function params() {
    return new URLSearchParams(window.location.search);
  }
  function hasAll() {
    return params().has("all");
  }

  function buildUrlWithAll(val) {
    const url = new URL(window.location.href);
    const ps = url.searchParams;
    if (val === null) ps.delete("all");
    else ps.set("all", val === true ? "1" : String(val));
    url.search = ps.toString();
    return url.toString();
  }

  function updateButtonState(btn) {
    if (!btn) return;
    if (hasAll()) {
      btn.textContent = "Paginate";
      btn.setAttribute("data-all", "1");
      btn.title = "Re-enable pagination";
    } else {
      btn.textContent = "Show all";
      btn.setAttribute("data-all", "0");
      btn.title = "Show all rows (disable pagination)";
    }
  }

  function onButtonClick(e) {
    const btn = e.currentTarget;
    const curAll = btn.getAttribute("data-all") === "1";
    // navigate to toggled URL
    const target = curAll ? buildUrlWithAll(null) : buildUrlWithAll(1);
    window.location.href = target;
  }

  function onShowAllLinkClick(e) {
    // The bottom link is about to navigate; update toolbar state so it matches intended navigation.
    // Determine whether the clicked link will add or remove the 'all' param.
    try {
      const href = e.currentTarget.getAttribute("href") || "";
      // if href contains 'all' param then the result will be show-all; otherwise it's ambiguous.
      const willHaveAll = /\ball\b/i.test(href) || href.indexOf("all=") !== -1 || href.indexOf("all") !== -1;
      const btn = document.getElementById(BTN_ID);
      // If the bottom link is toggling to 'all' present, toolbar should become 'Paginate' (opposite action).
      if (btn) {
        if (willHaveAll) {
          btn.textContent = "Paginate";
          btn.setAttribute("data-all", "1");
          btn.title = "Re-enable pagination";
        } else {
          btn.textContent = "Show all";
          btn.setAttribute("data-all", "0");
          btn.title = "Show all rows (disable pagination)";
        }
      }
    } catch (err) {
      // ignore
    }
    // let the navigation proceed
  }

  document.addEventListener("DOMContentLoaded", function () {
    const btn = document.getElementById(BTN_ID);

    if (btn) {
      // init state
      updateButtonState(btn);
      // ensure single handler
      btn.removeEventListener("click", onButtonClick);
      btn.addEventListener("click", onButtonClick);
    }

    // bind to existing bottom show-all links
    const showAllLinks = Array.from(document.querySelectorAll(SHOWALL_LINK_SELECTOR));
    showAllLinks.forEach(link => {
      // update toolbar earlier as user clicks the bottom link
      link.removeEventListener("click", onShowAllLinkClick);
      link.addEventListener("click", onShowAllLinkClick);
    });

    // handle back/forward
    window.addEventListener("popstate", function () {
      const b = document.getElementById(BTN_ID);
      updateButtonState(b);
    });
  });
})();
