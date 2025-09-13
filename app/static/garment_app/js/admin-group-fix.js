document.addEventListener('DOMContentLoaded', function () {
  // find the paginate button and the admin search form container
  const paginateBtn = document.getElementById('admin-toggle-paginate');
  const searchForm = document.querySelector('#changelist-search') || document.querySelector('.search-form') || document.querySelector('#changelist-form');

  if (!paginateBtn || !searchForm) return;

  // Ensure the button is appended inside the searchForm container
  // Also remove any stray textNodes/line breaks between elements that browsers render as small gaps
  // Append the button as the last child of the searchForm
  // If the searchBtn exists, insert after it
  const searchSubmit = searchForm.querySelector('input[type="submit"], button[type="submit"]');

  function removeInterveningTextNodes(parent) {
    for (let i = parent.childNodes.length - 1; i >= 0; i--) {
      const n = parent.childNodes[i];
      if (n.nodeType === Node.TEXT_NODE && !/\S/.test(n.nodeValue)) parent.removeChild(n);
    }
  }

  removeInterveningTextNodes(searchForm);

  if (searchSubmit && searchSubmit.parentNode === searchForm) {
    // insert after the submit button
    searchSubmit.insertAdjacentElement('afterend', paginateBtn);
  } else {
    // fallback: append to the form container
    searchForm.appendChild(paginateBtn);
  }

  // Remove any inline margin on paginate button (we control spacing via container)
  paginateBtn.style.marginLeft = '0';
});
