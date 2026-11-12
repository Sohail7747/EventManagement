(() => {
    const form = document.getElementById("packageBuilderForm");
    if (!form) return;

    const eventInputs = Array.from(form.querySelectorAll(".event-option-input"));
    const serviceInputs = Array.from(form.querySelectorAll(".service-option-input"));
    const serviceCategories = Array.from(form.querySelectorAll(".service-category"));
    const eventDate = form.querySelector("#event-date");
    const summaryItems = form.querySelector("#packageSummaryItems");
    const totalDisplay = form.querySelector("#packageTotal");
    const createButton = form.querySelector("#createPackageButton");
    const currency = new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        minimumFractionDigits: 2,
    });

    const selectedEvent = () => eventInputs.find((input) => input.checked);
    const selectedServices = () => serviceInputs.filter((input) => input.checked);

    const parseMoney = (value) => {
        if (value === "") return null;
        const amount = Number(value);
        return Number.isFinite(amount) && amount >= 0
            ? Math.round(amount * 100)
            : null;
    };

    const filterCategory = (category) => {
        const minimumInput = category.querySelector(".service-budget-min");
        const maximumInput = category.querySelector(".service-budget-max");
        const minimum = parseMoney(minimumInput.value);
        const maximum = parseMoney(maximumInput.value);
        const validRange = minimum !== null && maximum !== null && minimum <= maximum;
        let matchingCount = 0;

        category.querySelectorAll(".service-option-input").forEach((input) => {
            const price = parseMoney(input.dataset.servicePrice);
            const matches = validRange && price >= minimum && price <= maximum;
            const column = input.closest(".service-option-column");
            column.hidden = !matches;

            if (matches) {
                matchingCount += 1;
            } else {
                input.checked = false;
            }
        });

        const notice = category.querySelector(".service-no-matches");
        notice.hidden = validRange && matchingCount > 0;
        notice.textContent = validRange
            ? "No offerings are available in this budget range."
            : "Enter a valid minimum and maximum budget to see matching offerings.";
    };

    serviceInputs
        .filter((input) => input.checked)
        .forEach((input) => {
            const category = input.closest(".service-category");
            if (category) category.open = true;
        });

    const addSummaryItem = (name, packageName, seller, amount) => {
        const item = document.createElement("li");
        const details = document.createElement("div");
        details.className = "package-summary-item-details";

        const title = document.createElement("strong");
        title.textContent = name;
        details.appendChild(title);

        if (packageName) {
            const packageDetails = document.createElement("span");
            packageDetails.textContent = `Package: ${packageName}`;
            details.appendChild(packageDetails);
        }

        if (seller) {
            const sellerDetails = document.createElement("span");
            sellerDetails.textContent = `Seller: ${seller}`;
            details.appendChild(sellerDetails);
        }

        const price = document.createElement("strong");
        price.className = "package-summary-item-price";
        price.textContent = currency.format(amount);
        item.append(details, price);
        summaryItems.appendChild(item);
    };

    const updateSummary = () => {
        const event = selectedEvent();
        const services = selectedServices();
        let total = 0;
        summaryItems.replaceChildren();

        if (event) {
            const price = Number(event.dataset.eventPrice);
            total += price;
            addSummaryItem(event.dataset.eventTitle, "", "", price);
        }

        services.forEach((service) => {
            const price = Number(service.dataset.servicePrice);
            total += price;
            addSummaryItem(
                service.dataset.serviceName,
                service.dataset.servicePackage,
                service.dataset.serviceSeller,
                price
            );
        });

        if (!event && services.length === 0) {
            const empty = document.createElement("li");
            empty.className = "summary-empty";
            empty.textContent = "Choose an event and services to see your package here.";
            summaryItems.appendChild(empty);
        }

        totalDisplay.textContent = currency.format(total);
        createButton.disabled = !event || !eventDate.value || services.length === 0;
    };

    serviceCategories.forEach((category) => {
        category.querySelectorAll(".service-budget-input").forEach((input) => {
            input.addEventListener("input", () => {
                filterCategory(category);
                updateSummary();
            });
        });
        filterCategory(category);
    });

    eventInputs.forEach((input) => {
        input.addEventListener("change", updateSummary);
    });

    serviceInputs.forEach((input) => {
        input.addEventListener("change", () => {
            if (input.checked) {
                serviceInputs.forEach((otherInput) => {
                    if (
                        otherInput !== input &&
                        otherInput.dataset.category === input.dataset.category
                    ) {
                        otherInput.checked = false;
                    }
                });
            }
            updateSummary();
        });
    });

    eventDate.addEventListener("input", updateSummary);
    form.addEventListener("submit", (event) => {
        if (!selectedEvent() || !eventDate.value || selectedServices().length === 0) {
            event.preventDefault();
            form.reportValidity();
            if (selectedServices().length === 0) {
                document.querySelector("#service-options-heading").scrollIntoView({
                    behavior: "smooth",
                    block: "center",
                });
            }
        }
    });
    updateSummary();
})();
