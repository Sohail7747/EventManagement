(() => {
    const calendar = document.getElementById("availability-calendar");
    if (!calendar) return;

    const grid = document.getElementById("availability-calendar-grid");
    const monthLabel = document.getElementById("availability-month");
    const status = document.getElementById("availability-message");
    const startInput = document.getElementById("id_booking_date");
    const endInput = document.getElementById("id_booking_end_date");
    const previousButton = document.getElementById("availability-previous");
    const nextButton = document.getElementById("availability-next");
    if (!grid || !monthLabel || !status || !startInput || !endInput) return;

    const minDate = calendar.dataset.minDate;
    const today = new Date(`${minDate}T00:00:00`);
    const selected = calendar.dataset.selectedDate || startInput.value;
    let displayedMonth = selected
        ? new Date(`${selected}T00:00:00`)
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

    const dateString = (year, month, day) =>
        `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;

    const syncCalendarToDateInput = () => {
        const [year, month, day] = startInput.value.split("-").map(Number);
        const selectedDate = new Date(year, month - 1, day);
        if (
            startInput.value &&
            selectedDate.getFullYear() === year &&
            selectedDate.getMonth() === month - 1 &&
            selectedDate.getDate() === day
        ) {
            displayedMonth = new Date(year, month - 1, 1);
        }
        calendar.dataset.selectedDate = startInput.value;
        renderCalendar();
    };

    const renderCalendar = async () => {
        const year = displayedMonth.getFullYear();
        const month = displayedMonth.getMonth();
        const monthValue = `${year}-${String(month + 1).padStart(2, "0")}`;
        monthLabel.textContent = monthNames.format(displayedMonth);
        status.textContent = "Loading availability…";
        grid.replaceChildren();

        weekdays.forEach((weekday) => {
            const label = document.createElement("span");
            label.className = "availability-calendar-weekday";
            label.setAttribute("role", "columnheader");
            label.textContent = weekday;
            grid.appendChild(label);
        });

        let unavailable = new Set();
        try {
            const url = new URL(calendar.dataset.apiUrl, window.location.origin);
            url.searchParams.set("month", monthValue);
            const response = await fetch(url, {
                credentials: "same-origin",
                headers: { Accept: "application/json" },
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || "Availability could not be loaded.");
            }
            unavailable = new Set(data.unavailable_dates);
        } catch (error) {
            status.textContent = error.message || "Availability could not be loaded.";
            return;
        }

        const firstWeekday = new Date(year, month, 1).getDay();
        const daysInMonth = new Date(year, month + 1, 0).getDate();
        for (let blank = 0; blank < firstWeekday; blank += 1) {
            const placeholder = document.createElement("span");
            placeholder.className = "availability-calendar-day is-outside";
            placeholder.setAttribute("aria-hidden", "true");
            grid.appendChild(placeholder);
        }
        for (let day = 1; day <= daysInMonth; day += 1) {
            const value = dateString(year, month, day);
            const button = document.createElement("button");
            button.type = "button";
            button.className = "availability-calendar-day";
            button.setAttribute("role", "gridcell");
            button.textContent = String(day);
            button.setAttribute("aria-label", value);
            button.dataset.date = value;
            button.disabled = value < minDate || unavailable.has(value);
            if (value === startInput.value) {
                button.classList.add("is-selected");
                button.setAttribute("aria-pressed", "true");
            }
            if (unavailable.has(value)) {
                button.title = "Unavailable";
            }
            button.addEventListener("click", () => {
                startInput.value = value;
                startInput.dispatchEvent(new Event("change", { bubbles: true }));
                if (!endInput.value || endInput.value < value) {
                    endInput.value = value;
                    endInput.dispatchEvent(new Event("change", { bubbles: true }));
                }
            });
            grid.appendChild(button);
        }

        status.textContent = unavailable.size
            ? "Choose an available date. Crossed-out dates are already booked or blocked by the seller."
            : "Choose any available date. Dates booked by the seller will be marked unavailable.";
    };

    previousButton.addEventListener("click", () => {
        const previous = new Date(
            displayedMonth.getFullYear(),
            displayedMonth.getMonth() - 1,
            1
        );
        if (
            previous.getFullYear() > today.getFullYear() ||
            previous.getMonth() >= today.getMonth()
        ) {
            displayedMonth = previous;
            renderCalendar();
        }
    });
    nextButton.addEventListener("click", () => {
        displayedMonth = new Date(
            displayedMonth.getFullYear(),
            displayedMonth.getMonth() + 1,
            1
        );
        renderCalendar();
    });
    startInput.addEventListener("change", syncCalendarToDateInput);
    renderCalendar();
})();
