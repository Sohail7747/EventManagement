const dateElement = document.getElementById("todayDate");

        if (dateElement) {
            dateElement.textContent = new Date().toLocaleDateString(undefined, {
                day: "numeric",
                month: "short",
                year: "numeric"
            });
        }
