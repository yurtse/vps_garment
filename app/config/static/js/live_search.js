document.addEventListener("DOMContentLoaded", function () {
    const searchInput = document.querySelector('#searchbar');  // main top search box
    const resultsTable = document.querySelector("#result_list");

    console.log("🔎 Looking for searchbar:", searchInput);
    console.log("🔎 Looking for result_list:", resultsTable);

    if (!searchInput || !resultsTable) {
        console.log("⚠️ Live search not active: element missing");
        return;
    }

    console.log("✅ Live search attached to searchbar");

    searchInput.addEventListener("keyup", function (event) {
        if (event.key === "Enter") return; // let default search happen

        const term = this.value.toLowerCase();
        const rows = resultsTable.querySelectorAll("tbody tr");

        rows.forEach(row => {
            const text = row.innerText.toLowerCase();
            row.style.display = text.includes(term) ? "" : "none";
        });
    });
});
