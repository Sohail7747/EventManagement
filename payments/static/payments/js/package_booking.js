(() => {
        const form = document.getElementById("packageBookingForm");
        const summary = document.querySelector(".booking-summary");
        if (!form || !summary) return;

        const guestCountInput = document.getElementById("id_guest_count");
        const startDateInput = document.getElementById("id_booking_date");
        const endDateInput = document.getElementById("id_booking_end_date");
        const packagePrice = Number(summary.dataset.packagePrice);
        const guestPrice = Number(summary.dataset.guestPrice);
        const money = new Intl.NumberFormat("en-IN", {
            style: "currency",
            currency: "INR",
            minimumFractionDigits: 2,
        });

        const updateSummary = () => {
            const guests = Math.max(1, Number(guestCountInput.value) || 1);
            const eventTotal = guestPrice * guests;
            const total = packagePrice + eventTotal;
            document.getElementById("summaryGuestCount").textContent = guests;
            document.getElementById("summaryGuestPrice").textContent = money.format(eventTotal);
            document.getElementById("summaryTotal").textContent = money.format(total);
            document.getElementById("mobileSummaryTotal").textContent = money.format(total);
            document.getElementById("summaryDue").textContent = money.format(total);
        };

        const updateEndDateMinimum = () => {
            endDateInput.min = startDateInput.value || startDateInput.min;
        };

        form.addEventListener("input", updateSummary);
        form.addEventListener("change", updateSummary);
        startDateInput.addEventListener("change", updateEndDateMinimum);
        updateEndDateMinimum();
        updateSummary();

        const optionsNode = document.getElementById("razorpay-options");
        if (optionsNode) {
            const options = JSON.parse(optionsNode.textContent);
            const errorBox = document.getElementById("paymentError");
            const button = form.querySelector(".booking-confirm-button");
            const csrfToken = form.querySelector("[name=csrfmiddlewaretoken]").value;
            const showPaymentError = (message) => {
                errorBox.textContent = message;
                errorBox.classList.remove("d-none");
                button.disabled = false;
            };

            if (typeof Razorpay === "undefined") {
                showPaymentError("Payment checkout could not load. Please refresh and try again.");
                return;
            }

            form.querySelectorAll("input:not([type=hidden]), select, textarea").forEach((field) => {
                field.disabled = true;
            });

            options.handler = async (response) => {
                button.disabled = true;
                button.textContent = "Verifying payment...";
                const body = new URLSearchParams({
                    attempt_id: String(options.attempt_id),
                    razorpay_order_id: response.razorpay_order_id,
                    razorpay_payment_id: response.razorpay_payment_id,
                    razorpay_signature: response.razorpay_signature,
                });
                try {
                    const result = await fetch(options.verify_url, {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/x-www-form-urlencoded",
                            "X-CSRFToken": csrfToken,
                        },
                        body: body.toString(),
                        credentials: "same-origin",
                    });
                    const data = await result.json();
                    if (!result.ok) {
                        throw new Error(data.error || "Payment verification failed.");
                    }
                    window.location.assign(data.redirect_url);
                } catch (error) {
                    showPaymentError(error.message || "Payment verification failed. If money was deducted, contact support.");
                    button.textContent = "Retry payment";
                }
            };
            options.modal = {
                ondismiss: () => {
                    button.disabled = false;
                    button.textContent = "Retry payment";
                },
            };
            options.theme = { color: "#aa8745" };
            const checkout = new Razorpay(options);
            const openCheckout = () => {
                button.disabled = true;
                button.textContent = "Opening secure checkout...";
                try {
                    checkout.open();
                } catch (error) {
                    showPaymentError("Checkout could not open. Please try again.");
                    button.textContent = "Retry payment";
                }
            };
            checkout.on("payment.failed", (response) => {
                showPaymentError(
                    response.error && response.error.description
                        ? response.error.description
                        : "Payment failed. Please try again."
                );
                button.textContent = "Retry payment";
            });
            form.addEventListener("submit", (event) => {
                event.preventDefault();
                openCheckout();
            });
            openCheckout();
        }
    })();
