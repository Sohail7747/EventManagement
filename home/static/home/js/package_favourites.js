document.addEventListener("submit", async function (event) {
    const form = event.target.closest(".package-favourite-form");
    if (!form) return;

    event.preventDefault();
    const button = form.querySelector(".package-favourite-button");
    const status = document.getElementById("package-favourite-status");
    if (button.disabled) return;

    button.disabled = true;
    button.setAttribute("aria-busy", "true");

    try {
        const response = await fetch(form.action, {
            method: "POST",
            body: new FormData(form),
            headers: { "X-Requested-With": "XMLHttpRequest" },
            credentials: "same-origin",
        });
        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || "Could not update your favorites. Please try again.");
        }

        const icon = button.querySelector("i");
        button.classList.toggle("is-favourite", result.is_favourite);
        button.setAttribute("aria-pressed", String(result.is_favourite));
        button.title = result.is_favourite ? "Remove from favorites" : "Add to favorites";
        button.setAttribute(
            "aria-label",
            (result.is_favourite ? "Remove " : "Add ") +
                button.dataset.packageTitle +
                " " +
                (result.is_favourite ? "from" : "to") +
                " favorites"
        );
        icon.classList.toggle("bi-heart-fill", result.is_favourite);
        icon.classList.toggle("bi-heart", !result.is_favourite);
        status.replaceChildren();

        const message = document.createElement("span");
        message.textContent = result.message + " ";
        status.appendChild(message);
        if (result.is_favourite) {
            const link = document.createElement("a");
            link.href = result.favourites_url;
            link.textContent = "View favorites";
            status.appendChild(link);
        }
        status.classList.add("is-visible");
        window.clearTimeout(status.hideTimer);
        status.hideTimer = window.setTimeout(function () {
            status.classList.remove("is-visible");
        }, 5000);
    } catch (error) {
        status.textContent = error.message || "Could not update your favorites. Please try again.";
        status.classList.add("is-visible", "is-error");
        window.clearTimeout(status.hideTimer);
        status.hideTimer = window.setTimeout(function () {
            status.classList.remove("is-visible", "is-error");
        }, 6000);
    } finally {
        button.disabled = false;
        button.removeAttribute("aria-busy");
    }
});
