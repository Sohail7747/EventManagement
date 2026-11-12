document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("sellerPackageForm");
    const checkboxes = document.querySelectorAll(".service-checkbox");
    const selectedContainer = document.getElementById("selectedServices");
    const totalDisplay = document.getElementById("packageTotal");
    const noServicesMessage = document.getElementById("noServicesMessage");
    const picker = document.getElementById("servicePicker");
    const pickerToggle = document.getElementById("servicePickerToggle");
    const pickerMenu = document.getElementById("servicePickerMenu");
    const pickerSummary = document.getElementById("servicePickerSummary");
    const pickerHint = document.getElementById("servicePickerHint");
    const serviceSearch = document.getElementById("serviceSearch");
    const searchEmpty = document.getElementById("serviceSearchEmpty");

    // Prices passed from the server when editing an existing package.
    const existingPrices = JSON.parse(document.getElementById("existingPackagePrices").textContent);

    function updateServicePicker() {
        if (!picker) return;
        const selected = Array.from(checkboxes).filter(checkbox => checkbox.checked);
        pickerSummary.textContent = selected.length
            ? selected.length + (selected.length === 1 ? " service selected" : " services selected")
            : "Choose services";
        pickerHint.textContent = selected.length
            ? selected.map(checkbox => checkbox.closest(".service-choice").querySelector(".service-info strong").textContent.trim()).join(", ")
            : "Select one or more services for this package";
    }

    function updateTotal() {
        let total = 0;
        let count = 0;

        checkboxes.forEach(function (checkbox) {
            if (!checkbox.checked) return;
            count++;

            const input = document.getElementById("price_" + checkbox.value);
            if (input && input.value.trim() !== "") {
                const value = Number(input.value);
                if (Number.isFinite(value) && value >= 0) total += value;
            }
        });

        noServicesMessage.style.display = count ? "none" : "block";
        totalDisplay.textContent = "₹" + total.toFixed(2);
    }

    function addPriceRow(checkbox) {
        const id = checkbox.value;
        const rowId = "price_row_" + id;

        if (document.getElementById(rowId)) return;

        const label = checkbox.closest(".service-choice");
        const serviceName = label.querySelector(".service-info strong").textContent.trim();

        const row = document.createElement("div");
        row.className = "selected-service-row";
        row.id = rowId;

        const name = document.createElement("label");
        name.htmlFor = "price_" + id;
        name.textContent = serviceName;

        const input = document.createElement("input");
        input.type = "number";
        input.name = "price_" + id;
        input.id = "price_" + id;
        input.className = "form-control";
        input.min = "0";
        input.step = "0.01";
        input.required = true;
        input.placeholder = "Enter price (₹)";
        input.value = existingPrices[id] || "";

        input.addEventListener("input", updateTotal);

        row.appendChild(name);
        row.appendChild(input);
        selectedContainer.appendChild(row);
    }

    function removePriceRow(checkbox) {
        const row = document.getElementById("price_row_" + checkbox.value);
        if (row) row.remove();
    }

    checkboxes.forEach(function (checkbox) {
        checkbox.addEventListener("change", function () {
            if (checkbox.checked) {
                addPriceRow(checkbox);
            } else {
                removePriceRow(checkbox);
            }
            updateServicePicker();
            updateTotal();
        });

        if (checkbox.checked) addPriceRow(checkbox);
    });

    if (picker) {
        pickerToggle.addEventListener("click", function () {
            const isExpanded = pickerToggle.getAttribute("aria-expanded") === "true";
            pickerToggle.setAttribute("aria-expanded", String(!isExpanded));
            pickerMenu.hidden = isExpanded;
            if (!isExpanded) serviceSearch.focus();
        });

        serviceSearch.addEventListener("input", function () {
            const query = serviceSearch.value.trim().toLowerCase();
            let visibleCount = 0;
            picker.querySelectorAll(".service-choice").forEach(function (choice) {
                const matches = choice.dataset.serviceName.includes(query);
                choice.hidden = !matches;
                if (matches) visibleCount++;
            });
            searchEmpty.hidden = visibleCount > 0;
        });

        document.addEventListener("click", function (event) {
            if (!picker.contains(event.target)) {
                pickerToggle.setAttribute("aria-expanded", "false");
                pickerMenu.hidden = true;
            }
        });

        picker.addEventListener("keydown", function (event) {
            if (event.key === "Escape") {
                pickerToggle.setAttribute("aria-expanded", "false");
                pickerMenu.hidden = true;
                pickerToggle.focus();
            }
        });
    }

    updateServicePicker();

    form.addEventListener("submit", function (event) {
        const selected = Array.from(checkboxes).filter(c => c.checked);

        if (selected.length === 0) {
            event.preventDefault();
            alert("Please select at least one service.");
            return;
        }

        let valid = true;
        selected.forEach(function (checkbox) {
            const input = document.getElementById("price_" + checkbox.value);
            const value = input ? input.value.trim() : "";

            if (!value || !Number.isFinite(Number(value)) ||
                Number(value) < 0 || !/^\d+(\.\d{1,2})?$/.test(value)) {
                valid = false;
                if (input) input.classList.add("is-invalid");
            } else if (input) {
                input.classList.remove("is-invalid");
            }
        });

        if (!valid) {
            event.preventDefault();
            alert("Please enter a valid non-negative price with at most two decimal places for every selected service.");
        }
    });

    updateTotal();
});
