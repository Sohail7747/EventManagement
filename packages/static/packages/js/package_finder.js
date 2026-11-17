(() => {
    const budgetInput = document.getElementById("user-budget");
    const guestCountInput = document.getElementById("guest-count");
    const eventDateInput = document.getElementById("event-date");
    const serviceToggle = document.getElementById("service-picker-toggle");
    const serviceMenu = document.getElementById("service-picker-menu");
    const serviceLabel = document.getElementById("service-picker-label");
    const serviceInputs = Array.from(
        document.querySelectorAll(".service-checkbox")
    );
    const results = document.getElementById("offer-results");
    const resultsHeading = document.getElementById("offer-results-heading");
    const stageDescription = document.getElementById("offer-stage-description");
    const count = document.getElementById("offer-count");
    const message = document.getElementById("offer-message");
    const offerGrid = document.getElementById("offer-grid");
    const packageNameWrap = document.getElementById("package-name-wrap");
    const packageNameInput = document.getElementById("package-name");
    const createUrlInput = document.getElementById("create-package-url");
    const csrfInput = document.querySelector(
        "#csrf-token-form [name=csrfmiddlewaretoken]"
    );
    const offeringsNode = document.getElementById("service-offerings-data");
    const availabilityCalendar = document.getElementById("package-availability-calendar");
    const calendarGrid = document.getElementById("finder-calendar-grid");
    const calendarMonthLabel = document.getElementById("finder-calendar-month");
    const calendarMessage = document.getElementById("finder-calendar-message");
    const calendarPrevious = document.getElementById("finder-calendar-previous");
    const calendarNext = document.getElementById("finder-calendar-next");
    const budgetLiveValue = document.getElementById("budget-live-value");
    const resultsBudgetValue = document.getElementById("results-budget-value");
    const selectedServiceChips = document.getElementById("selected-service-chips");
    const progressSteps = [
        document.getElementById("progress-budget"),
        document.getElementById("progress-services"),
        document.getElementById("progress-date"),
    ];

    if (
        !budgetInput ||
        !guestCountInput ||
        !eventDateInput ||
        !serviceToggle ||
        !serviceMenu ||
        !serviceLabel ||
        !results ||
        !resultsHeading ||
        !stageDescription ||
        !count ||
        !message ||
        !offerGrid ||
        !packageNameWrap ||
        !packageNameInput ||
        !createUrlInput ||
        !csrfInput ||
        !offeringsNode ||
        !budgetLiveValue ||
        !resultsBudgetValue ||
        !selectedServiceChips ||
        progressSteps.some((step) => !step) ||
        !availabilityCalendar ||
        !calendarGrid ||
        !calendarMonthLabel ||
        !calendarMessage ||
        !calendarPrevious ||
        !calendarNext
    ) {
        return;
    }

    let offerings;
    try {
        offerings = JSON.parse(offeringsNode.textContent || "[]");
    } catch (error) {
        console.error("Could not read seller service offerings.", error);
        results.hidden = false;
        message.textContent =
            "Seller service options could not be loaded. Please refresh and try again.";
        return;
    }

    const selectedCategories = () =>
        serviceInputs
            .filter((input) => input.checked)
            .map((input) => input.value);
    const currentBudget = () => {
        const budget = Number(budgetInput.value);
        return Number.isFinite(budget) && budget > 0 ? budget : null;
    };
    const money = (value) =>
        new Intl.NumberFormat("en-IN", {
            style: "currency",
            currency: "INR",
            maximumFractionDigits: 2,
        }).format(value);
    const minorUnits = (value) => Math.round(Number(value) * 100);
    const minDate = availabilityCalendar.dataset.minDate;
    const today = new Date(`${minDate}T00:00:00`);
    const selectedInitialDate = eventDateInput.value;
    let displayedMonth = selectedInitialDate
        ? new Date(`${selectedInitialDate}T00:00:00`)
        : new Date(today.getFullYear(), today.getMonth(), 1);
    displayedMonth = new Date(
        displayedMonth.getFullYear(),
        displayedMonth.getMonth(),
        1
    );
    const monthNames = new Intl.DateTimeFormat("en", {
        month: "long",
        year: "numeric",
    });
    const weekdays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
    let availabilityRequest = 0;
    let availabilityCacheKey = "";
    let availabilityBySeller = null;
    let availabilityError = "";
    let refreshOffersAfterAvailability = false;
    const availabilityCache = new Map();
    const dateString = (year, month, day) =>
        `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;

    const clearGrid = () => offerGrid.replaceChildren();

    const updateBuilderDetails = (categories, budget, dateSelected) => {
        const budgetReady = budget !== null;
        const servicesReady = categories.length > 0;
        const progressState = [
            budgetReady,
            servicesReady,
            budgetReady && dateSelected && servicesReady,
        ];
        let currentStep = progressState.findIndex((complete) => !complete);
        if (currentStep === -1) currentStep = progressState.length - 1;
        progressSteps.forEach((step, index) => {
            step.classList.toggle("is-complete", progressState[index]);
            step.classList.toggle("is-current", index === currentStep);
        });

        budgetLiveValue.textContent = budgetReady
            ? money(budget)
            : "Set a service budget";
        resultsBudgetValue.textContent = budgetReady
            ? `Service budget · ${money(budget)}`
            : "Service budget not set";

        selectedServiceChips.replaceChildren();
        if (!servicesReady) {
            const emptyMessage = document.createElement("span");
            emptyMessage.className = "finder-selected-empty";
            emptyMessage.textContent = "Your chosen services will appear here.";
            selectedServiceChips.append(emptyMessage);
        } else {
            categories.forEach((category) => {
                const input = serviceInputs.find((option) => option.value === category);
                const chip = document.createElement("span");
                chip.className = "finder-selected-chip";
                const icon = document.createElement("i");
                icon.className = "bi bi-check-circle-fill";
                icon.setAttribute("aria-hidden", "true");
                const label = document.createElement("span");
                label.textContent = input.dataset.serviceName;
                chip.append(icon, label);
                selectedServiceChips.append(chip);
            });
        }

        serviceInputs.forEach((input) => {
            const priceLabel = input
                .closest(".service-option")
                .querySelector(".service-option-price");
            if (!priceLabel) return;
            const lowestPrice = offerings
                .filter((offer) => offer.category === input.value)
                .reduce(
                    (lowest, offer) => Math.min(lowest, Number(offer.price)),
                    Number.POSITIVE_INFINITY
                );
            priceLabel.textContent = Number.isFinite(lowestPrice)
                ? `From ${money(lowestPrice)}`
                : "";
        });
    };

    const hasAvailableCombination = (categories, budget, date, unavailableBySeller) => {
        const categoryOffers = getCategoryOffers(categories, budget);
        if (categoryOffers.some((offers) => offers.length === 0)) return false;
        const isUnavailable = (sellerId) =>
            (unavailableBySeller[String(sellerId)] || []).includes(date);
        const canComplete = (categoryIndex, totalMinor = 0) => {
            if (categoryIndex === categoryOffers.length) return true;
            return categoryOffers[categoryIndex].some(
                (offer) => {
                    const nextTotalMinor = totalMinor + minorUnits(offer.price);
                    return (
                        nextTotalMinor <= minorUnits(budget) &&
                        !isUnavailable(offer.seller_id) &&
                        canComplete(categoryIndex + 1, nextTotalMinor)
                    );
                }
            );
        };
        return canComplete(0);
    };

    const isCombinationAvailable = (offers, date, unavailableBySeller) =>
        offers.every(
            (offer) =>
                !(unavailableBySeller[String(offer.seller_id)] || []).includes(date)
        );

    const renderCalendar = async () => {
        const categories = selectedCategories();
        const budget = currentBudget();
        const year = displayedMonth.getFullYear();
        const month = displayedMonth.getMonth();
        const monthValue = `${year}-${String(month + 1).padStart(2, "0")}`;
        calendarMonthLabel.textContent = monthNames.format(displayedMonth);
        calendarGrid.replaceChildren();

        weekdays.forEach((weekday) => {
            const label = document.createElement("span");
            label.className = "finder-calendar-weekday";
            label.setAttribute("role", "columnheader");
            label.textContent = weekday;
            calendarGrid.append(label);
        });

        if (!budget || categories.length === 0) {
            calendarMessage.textContent =
                "Set your budget and select services to check availability.";
            availabilityRequest += 1;
            availabilityCacheKey = "";
            availabilityBySeller = null;
            availabilityError = "";
            renderCalendarDays(year, month, null);
            return;
        }

        const cacheKey = `${monthValue}|${minorUnits(budget)}|${categories.slice().sort().join(",")}`;
        if (cacheKey !== availabilityCacheKey) {
            availabilityRequest += 1;
            const requestId = availabilityRequest;
            availabilityCacheKey = cacheKey;
            availabilityBySeller = availabilityCache.get(cacheKey) || null;
            availabilityError = "";
            if (!availabilityBySeller) {
                calendarMessage.textContent = "Checking seller availability…";
                const url = new URL(availabilityCalendar.dataset.apiUrl, window.location.origin);
                try {
                    const response = await fetch(url, {
                        method: "POST",
                        credentials: "same-origin",
                        headers: {
                            "Content-Type": "application/json",
                            "X-CSRFToken": csrfInput.value,
                            Accept: "application/json",
                        },
                        body: JSON.stringify({
                            categories,
                            budget: budgetInput.value,
                            month: monthValue,
                        }),
                    });
                    const data = await response.json();
                    if (!response.ok) {
                        throw new Error(data.error || "Availability could not be loaded.");
                    }
                    if (requestId !== availabilityRequest) return;
                    availabilityBySeller = data.unavailable_by_seller;
                    availabilityCache.set(cacheKey, availabilityBySeller);
                    refreshOffersAfterAvailability = true;
                } catch (error) {
                    if (requestId !== availabilityRequest) return;
                    availabilityError = error instanceof Error
                        ? error.message
                        : "Availability could not be loaded.";
                }
            }
        }

        if (availabilityError) {
            calendarMessage.textContent = availabilityError;
            renderCalendarDays(year, month, null, true);
            return;
        }
        if (!availabilityBySeller) {
            calendarMessage.textContent = "Checking seller availability…";
            renderCalendarDays(year, month, null, true);
            return;
        }

        if (
            eventDateInput.value &&
            !hasAvailableCombination(
                categories,
                budget,
                eventDateInput.value,
                availabilityBySeller
            )
        ) {
            eventDateInput.value = "";
            availabilityCalendar.dataset.selectedDate = "";
            eventDateInput.dispatchEvent(new Event("change", { bubbles: true }));
        }

        renderCalendarDays(year, month, {
            categories,
            budget,
            unavailableBySeller: availabilityBySeller,
        });
        if (refreshOffersAfterAvailability) {
            refreshOffersAfterAvailability = false;
            render();
        }
    };

    const renderCalendarDays = (year, month, availability, loading = false) => {
        const firstWeekday = new Date(year, month, 1).getDay();
        const daysInMonth = new Date(year, month + 1, 0).getDate();
        for (let blank = 0; blank < firstWeekday; blank += 1) {
            const placeholder = document.createElement("span");
            placeholder.className = "finder-calendar-day is-outside";
            placeholder.setAttribute("aria-hidden", "true");
            calendarGrid.append(placeholder);
        }
        for (let day = 1; day <= daysInMonth; day += 1) {
            const value = dateString(year, month, day);
            const button = document.createElement("button");
            button.type = "button";
            button.className = "finder-calendar-day";
            button.setAttribute("role", "gridcell");
            button.textContent = String(day);
            button.setAttribute("aria-label", value);
            button.dataset.date = value;

            const isPast = value < minDate;
            const isAvailable = availability
                ? hasAvailableCombination(
                    availability.categories,
                    availability.budget,
                    value,
                    availability.unavailableBySeller
                )
                : false;
            button.disabled = isPast || loading || !availability || !isAvailable;
            if (loading) {
                button.classList.add("is-loading");
                button.title = "Checking availability";
            } else if (availability && !isPast && !isAvailable) {
                button.classList.add("is-unavailable");
                button.title = "No complete selected seller combination is available";
            } else if (isPast) {
                button.title = "Past date";
            } else if (isAvailable) {
                button.title = "Available for at least one complete seller combination";
            }
            if (value === eventDateInput.value) {
                button.classList.add("is-selected");
                button.setAttribute("aria-pressed", "true");
            }
            if (!button.disabled) {
                button.addEventListener("click", () => {
                    eventDateInput.value = value;
                    availabilityCalendar.dataset.selectedDate = value;
                    eventDateInput.dispatchEvent(new Event("change", { bubbles: true }));
                });
            }
            calendarGrid.append(button);
        }

        if (loading) {
            calendarMessage.textContent = "Checking selected sellers for this month…";
        } else if (!availability) {
            calendarMessage.textContent =
                "Select a budget and services to see green available dates.";
        } else {
            calendarMessage.textContent =
                "Green dates have at least one complete seller combination available. Black dates are unavailable.";
        }
    };

    const COMBINATIONS_PER_PAGE = 24;

    function* enumerateCombinations(
        categoryOffers,
        budgetMinor,
        categoryIndex = 0,
        chosen = [],
        totalMinor = 0
    ) {
        if (categoryIndex === categoryOffers.length) {
            yield {
                offers: [...chosen],
                total: totalMinor / 100,
            };
            return;
        }

        for (const offer of categoryOffers[categoryIndex]) {
            const nextTotalMinor = totalMinor + minorUnits(offer.price);
            if (nextTotalMinor <= budgetMinor) {
                yield* enumerateCombinations(
                    categoryOffers,
                    budgetMinor,
                    categoryIndex + 1,
                    [...chosen, offer],
                    nextTotalMinor
                );
            }
        }
    }

    const getCategoryOffers = (categories, budget) =>
        categories.map((category) =>
            offerings
                .filter((offer) => offer.category === category)
                .filter((offer) => minorUnits(offer.price) <= minorUnits(budget))
                .sort((first, second) => Number(first.price) - Number(second.price))
        );

    const currentGuestCount = () =>
        Math.max(1, Number.parseInt(guestCountInput.value, 10) || 1);
    const guestPrice = Number(guestCountInput.dataset.guestPrice);
    const estimatedBookingTotal = (servicesTotal) =>
        servicesTotal + guestPrice * currentGuestCount();

    const updateGuestEstimates = (root = offerGrid) => {
        const guestCount = currentGuestCount();
        const guestFee = guestPrice * guestCount;
        root.querySelectorAll(".offer-card").forEach((card) => {
            const servicesTotal = Number(card.dataset.servicesTotal);
            card.querySelector(".offer-guest-label").textContent =
                `Guest fee (${money(guestPrice)} × ${guestCount})`;
            card.querySelector(".offer-guest-price").textContent =
                money(guestFee);
            card.querySelector(".offer-estimated-total").textContent =
                money(servicesTotal + guestFee);
            card.querySelector(".book-package-button").textContent =
                `Book now · ${money(servicesTotal + guestFee)}`;
        });
    };

    const createBookButton = (offers, total, budget) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "book-package-button";
        button.textContent = `Book now · ${money(estimatedBookingTotal(total))}`;
        button.addEventListener("click", async () => {
            if (!guestCountInput.reportValidity()) return;
            button.disabled = true;
            offerGrid
                .querySelectorAll(".book-package-button")
                .forEach((otherButton) => {
                    otherButton.disabled = true;
                });
            button.textContent = "Preparing your booking…";
            message.hidden = false;
            message.textContent = "Creating your package…";
            try {
                const response = await fetch(createUrlInput.value, {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": csrfInput.value,
                    },
                    body: JSON.stringify({
                        event_date: eventDateInput.value,
                        budget: budgetInput.value,
                        guest_count: guestCountInput.value,
                        package_title:
                            packageNameInput.value.trim() || "My package",
                        services: offers.map((offer) => ({
                            service_id: offer.service_id,
                            seller_id: offer.seller_id,
                            offer_type: offer.offer_type,
                            offer_id: offer.offer_id,
                        })),
                    }),
                });
                let result;
                try {
                    result = await response.json();
                } catch {
                    throw new Error(
                        response.redirected
                            ? "Your session may have expired. Sign in again and retry booking."
                            : "The booking service returned an invalid response. Please retry."
                    );
                }
                if (!response.ok) {
                    throw new Error(
                        result.error || "Could not prepare this booking."
                    );
                }
                if (
                    typeof result.booking_url !== "string" ||
                    !result.booking_url.startsWith("/")
                ) {
                    throw new Error(
                        "Your package was created, but the booking page could not be opened. Please open My Packages and continue from there."
                    );
                }
                window.location.assign(result.booking_url);
            } catch (error) {
                message.textContent =
                    error instanceof Error
                        ? error.message
                        : "Could not prepare this booking. Please try again.";
                offerGrid
                    .querySelectorAll(".book-package-button")
                    .forEach((otherButton) => {
                        otherButton.disabled = false;
                    });
                button.textContent =
                    `Book now · ${money(estimatedBookingTotal(total))}`;
            }
        });
        return button;
    };

    const createCombinationCard = (combination, index, budget) => {
        const card = document.createElement("article");
        card.className = "offer-card";
        const heading = document.createElement("h3");
        heading.textContent = `Package option ${index + 1}`;
        card.append(heading);

        const serviceList = document.createElement("div");
        serviceList.className = "offer-service-list";
        combination.offers.forEach((offer) => {
            const item = document.createElement("div");
            item.className = "offer-service-item";
            const imageWrap = document.createElement("div");
            imageWrap.className = "offer-service-image";
            if (offer.image_url) {
                const image = document.createElement("img");
                image.src = offer.image_url;
                image.alt = offer.service_name;
                image.loading = "lazy";
                imageWrap.append(image);
            } else {
                const placeholder = document.createElement("span");
                placeholder.className = "offer-service-image-placeholder";
                placeholder.setAttribute("aria-hidden", "true");
                const icon = document.createElement("i");
                icon.className = "bi bi-stars";
                placeholder.append(icon);
                imageWrap.append(placeholder);
            }
            const copy = document.createElement("div");
            copy.className = "offer-service-copy";
            const serviceName = document.createElement("strong");
            serviceName.textContent = offer.service_name;
            const sellerName = document.createElement("span");
            sellerName.textContent = offer.seller_name;
<<<<<<< HEAD
            const rating = document.createElement("span");
            rating.className = "offer-service-rating";
            rating.textContent = offer.review_count
                ? `${Number(offer.rating_average).toFixed(1)} ★ · ${offer.review_count} verified review${offer.review_count === 1 ? "" : "s"}`
                : "No reviews yet";
            copy.append(serviceName, sellerName, rating);
            (offer.reviews || []).forEach((review) => {
                if (!review.comment) return;
                const comment = document.createElement("span");
                comment.className = "offer-service-review";
                comment.textContent = `“${review.comment}” — ${review.reviewer}`;
                copy.append(comment);
            });
=======
            copy.append(serviceName, sellerName);
>>>>>>> 94851330fda38d03375e41cc7ee79f674bd05b01
            const price = document.createElement("strong");
            price.textContent = money(Number(offer.price));
            item.append(imageWrap, copy, price);
            serviceList.append(item);
        });
        card.append(serviceList);

        const total = document.createElement("div");
        total.className = "offer-total";
        const totalLabel = document.createElement("span");
        totalLabel.textContent = "Services total";
        const totalAmount = document.createElement("strong");
        totalAmount.textContent = money(combination.total);
        total.append(totalLabel, totalAmount);
        card.append(total);
        const guestFee = document.createElement("div");
        guestFee.className = "offer-total";
        const guestFeeLabel = document.createElement("span");
        guestFeeLabel.className = "offer-guest-label";
        const guestFeeAmount = document.createElement("strong");
        guestFeeAmount.className = "offer-guest-price";
        guestFee.append(guestFeeLabel, guestFeeAmount);
        card.append(guestFee);
        const estimatedTotal = document.createElement("div");
        estimatedTotal.className = "offer-total";
        const estimatedLabel = document.createElement("span");
        estimatedLabel.textContent = "Estimated total";
        const estimatedAmount = document.createElement("strong");
        estimatedAmount.className = "offer-estimated-total";
        estimatedTotal.append(estimatedLabel, estimatedAmount);
        card.append(estimatedTotal);
        card.dataset.servicesTotal = String(combination.total);
        card.append(
            createBookButton(combination.offers, combination.total, budget)
        );
        return card;
    };

    const render = () => {
        const categories = selectedCategories();
        const budget = currentBudget();
        const dateSelected = Boolean(eventDateInput.value);
        updateBuilderDetails(categories, budget, dateSelected);
        serviceLabel.textContent = categories.length
            ? `${categories.length} service${categories.length === 1 ? "" : "s"} selected`
            : "Select one or more services";
        serviceToggle.disabled = budget === null;
        renderCalendar();

        results.hidden = categories.length === 0;
        packageNameWrap.hidden = true;
        count.hidden = true;
        clearGrid();
        if (categories.length === 0) {
            return;
        }

        resultsHeading.textContent = "Services and seller combinations";
        stageDescription.textContent =
            "Each package option combines one seller offer for every selected service.";

        if (budget === null) {
            message.textContent = "Enter your budget to see package options.";
            message.hidden = false;
            return;
        }
        if (!dateSelected) {
            message.textContent = "Choose your event date to see package options.";
            message.hidden = false;
            return;
        }

        const categoryOffers = getCategoryOffers(categories, budget);
        const combinations = enumerateCombinations(
            categoryOffers,
            minorUnits(budget)
        );
        const loadNextPage = (pageIndex = 0) => {
            let added = 0;
            let next;
            while (added < COMBINATIONS_PER_PAGE) {
                next = combinations.next();
                if (next.done) {
                    break;
                }
                if (
                    dateSelected &&
                    availabilityBySeller &&
                    !isCombinationAvailable(
                        next.value.offers,
                        eventDateInput.value,
                        availabilityBySeller
                    )
                ) {
                    continue;
                }
                offerGrid.append(
                    createCombinationCard(
                        next.value,
                        pageIndex * COMBINATIONS_PER_PAGE + added,
                        budget
                    )
                );
                updateGuestEstimates();
                added += 1;
            }
            return { added, hasMore: !next?.done };
        };
        const firstPage = loadNextPage();
        if (firstPage.added === 0) {
            message.textContent =
                dateSelected
                    ? "No complete seller combination is available on this date within your budget. Choose another green date or change your services."
                    : "No complete service combination fits your budget. Increase your budget or change your service selections.";
            message.hidden = false;
            return;
        }

        message.hidden = true;
        packageNameWrap.hidden = false;
        count.hidden = false;
        count.textContent = `Showing ${firstPage.added} package combination${firstPage.added === 1 ? "" : "s"}`;
        if (firstPage.hasMore) {
            const loadMore = document.createElement("button");
            loadMore.type = "button";
            loadMore.className = "offer-action";
            loadMore.textContent = "Load more combinations";
            loadMore.addEventListener("click", () => {
                const nextPage = loadNextPage(
                    Math.ceil(offerGrid.querySelectorAll(".offer-card").length / COMBINATIONS_PER_PAGE)
                );
                const shown = offerGrid.querySelectorAll(".offer-card").length;
                count.textContent = `Showing ${shown} package combination${shown === 1 ? "" : "s"}`;
                if (!nextPage.hasMore) {
                    loadMore.remove();
                }
            });
            offerGrid.append(loadMore);
        }
    };

    serviceToggle.addEventListener("click", () => {
        const expanded = serviceToggle.getAttribute("aria-expanded") === "true";
        serviceToggle.setAttribute("aria-expanded", String(!expanded));
        serviceMenu.hidden = expanded;
    });

    document.addEventListener("click", (event) => {
        if (!serviceMenu.contains(event.target) && !serviceToggle.contains(event.target)) {
            serviceMenu.hidden = true;
            serviceToggle.setAttribute("aria-expanded", "false");
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !serviceMenu.hidden) {
            serviceMenu.hidden = true;
            serviceToggle.setAttribute("aria-expanded", "false");
            serviceToggle.focus();
        }
    });

    [budgetInput, eventDateInput].forEach((input) => {
        input.addEventListener("input", render);
        input.addEventListener("change", render);
    });
    guestCountInput.addEventListener("input", updateGuestEstimates);
    calendarPrevious.addEventListener("click", () => {
        const previous = new Date(
            displayedMonth.getFullYear(),
            displayedMonth.getMonth() - 1,
            1
        );
        if (previous >= new Date(today.getFullYear(), today.getMonth(), 1)) {
            displayedMonth = previous;
            renderCalendar();
        }
    });
    calendarNext.addEventListener("click", () => {
        displayedMonth = new Date(
            displayedMonth.getFullYear(),
            displayedMonth.getMonth() + 1,
            1
        );
        renderCalendar();
    });
    serviceInputs.forEach((input) => input.addEventListener("change", render));
    render();
})();
