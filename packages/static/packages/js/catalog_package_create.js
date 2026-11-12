document.addEventListener("DOMContentLoaded", function () {

    // Dropdown open/close
    document.querySelectorAll(".section-toggle").forEach(function (button) {
        button.addEventListener("click", function () {
            const panel = document.getElementById(button.dataset.target);
            const isOpen = panel.classList.toggle("is-open");

            button.setAttribute("aria-expanded", String(isOpen));
            button.querySelector(".toggle-arrow").textContent =
                isOpen ? "−" : "＋";
        });
    });

    const checkboxes = document.querySelectorAll(".service-checkbox");
    const selectedServices = document.getElementById("selectedServices");
    const noServicesMessage = document.getElementById("noServicesMessage");
    const totalDisplay = document.getElementById("packageTotal");
    const packageForm = document.getElementById("packageForm");

    function updateTotal() {
        let total = 0;
        let count = 0;

        checkboxes.forEach(function (checkbox) {
            if (!checkbox.checked) return;

            count++;

            const priceInput = document.getElementById("price_" + checkbox.value);

            if (priceInput && priceInput.value.trim() !== "") {
                const price = Number(priceInput.value);

                if (Number.isFinite(price) && price >= 0) {
                    total += price;
                }
            }
        });

        noServicesMessage.style.display = count === 0 ? "block" : "none";
        totalDisplay.textContent = "₹" + total.toFixed(2);
    }

    // Remove a selected service and its price input
    function removeService(serviceId) {
        const checkbox = document.getElementById("service_" + serviceId);
        const row = document.getElementById("selected_service_" + serviceId);

        if (checkbox) {
            checkbox.checked = false;
        }

        if (row) {
            row.remove();
        }

        updateTotal();
    }

    checkboxes.forEach(function (checkbox) {
        checkbox.addEventListener("change", function () {
            const serviceId = checkbox.value;
            const rowId = "selected_service_" + serviceId;

            if (checkbox.checked) {
                // Prevent duplicate rows
                if (document.getElementById(rowId)) {
                    updateTotal();
                    return;
                }

                const label = checkbox.closest("label");
                const nameElement = label.querySelector("strong");
                const serviceName = nameElement
                    ? nameElement.textContent.trim()
                    : label.textContent.trim();

                const row = document.createElement("div");
                row.id = rowId;
                row.className = "selected-service-row";

                const name = document.createElement("span");
                name.className = "selected-service-name";
                name.textContent = serviceName;

                const priceInput = document.createElement("input");
                priceInput.type = "number";
                priceInput.name = "price_" + serviceId;
                priceInput.id = "price_" + serviceId;
                priceInput.className = "form-control selected-service-price";
                priceInput.min = "0";
                priceInput.step = "0.01";
                priceInput.placeholder = "Enter price (₹)";
                priceInput.required = true;

                priceInput.addEventListener("input", updateTotal);

                // Cancel/remove button
                const cancelButton = document.createElement("button");
                cancelButton.type = "button";
                cancelButton.textContent = "✕";
                cancelButton.className =
                    "btn btn-sm btn-outline-danger remove-service-btn";
                cancelButton.title = "Remove this service";
                cancelButton.setAttribute("aria-label", "Remove " + serviceName);

                cancelButton.addEventListener("click", function () {
                    removeService(serviceId);
                });

                row.appendChild(name);
                row.appendChild(priceInput);
                row.appendChild(cancelButton);
                selectedServices.appendChild(row);

            } else {
                const row = document.getElementById(rowId);

                if (row) {
                    row.remove();
                }
            }

            updateTotal();
        });
    });

    // Do not submit a package without at least one selected service.
    packageForm.addEventListener("submit", function (event) {
        const hasSelectedService = Array.from(checkboxes).some(function (checkbox) {
            return checkbox.checked;
        });

        if (!hasSelectedService) {
            event.preventDefault();

            document.getElementById("serviceSection").classList.add("is-open");
            document.querySelector('[data-target="serviceSection"]')
                .setAttribute("aria-expanded", "true");
            document.querySelector('[data-target="serviceSection"] .toggle-arrow');

            alert("Please select at least one service before creating the package.");
        }
    });

    updateTotal();
});
