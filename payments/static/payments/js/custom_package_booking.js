(() => {
            const optionsNode = document.getElementById("razorpay-options");
            const form = document.getElementById("customPackageBookingForm");
            const button = document.getElementById("customPaymentButton");
            const errorBox = document.getElementById("customPaymentError");
            const statusBox = document.getElementById("customPaymentStatus");
            let options = {};
            const money = new Intl.NumberFormat("en-IN", {
                style: "currency",
                currency: "INR",
                minimumFractionDigits: 2,
            });
            const showError = (message) => {
                errorBox.textContent = message;
                errorBox.classList.remove("d-none");
                statusBox.textContent = "";
                button.disabled = false;
                const amount = Number(options.amount || 0) / 100;
                button.textContent = amount
                    ? "Pay " + money.format(amount) + " securely"
                    : "Retry payment";
            };
            try {
                options = JSON.parse(optionsNode.textContent);
            } catch (error) {
                console.error("Could not read Razorpay checkout options.", error);
                showError("Checkout details could not be loaded. Refresh this page and try again.");
                return;
            }
            const attemptId = options.attempt_id;
            const verifyUrl = options.verify_url;
            delete options.attempt_id;
            delete options.verify_url;
            if (!options.key || !options.order_id || !attemptId || !verifyUrl) {
                showError("The payment order is incomplete. Refresh the page and try again.");
                return;
            }
            const csrfToken = form.querySelector("[name=csrfmiddlewaretoken]").value;

            if (typeof Razorpay === "undefined") {
                showError("Razorpay checkout did not load. Check your internet connection, disable script blockers for this site, then refresh.");
                return;
            }

            options.handler = async (response) => {
                button.disabled = true;
                button.textContent = "Verifying payment...";
                statusBox.textContent = "Payment received. Verifying securely…";
                const body = new URLSearchParams({
                    attempt_id: String(attemptId),
                    razorpay_order_id: response.razorpay_order_id,
                    razorpay_payment_id: response.razorpay_payment_id,
                    razorpay_signature: response.razorpay_signature,
                });
                try {
                    const result = await fetch(verifyUrl, {
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
                    console.error("Razorpay payment verification failed.", error);
                    showError(error.message || "Payment verification failed. Contact support if money was deducted.");
                }
            };
            options.modal = {
                ondismiss: () => {
                    button.disabled = false;
                    button.textContent = "Pay " + money.format(Number(options.amount) / 100) + " securely";
                    statusBox.textContent = "Checkout was closed. Your booking details are saved; you can try again.";
                },
            };
            let checkout;
            try {
                checkout = new Razorpay(options);
                checkout.on("payment.failed", (response) => {
                    console.error("Razorpay reported a failed payment.", response.error);
                    showError(response.error?.description || "Payment failed. Please try again.");
                });
            } catch (error) {
                console.error("Could not initialize Razorpay checkout.", error);
                showError("Secure checkout could not be started. Please refresh the page and try again.");
                return;
            }
            form.querySelectorAll("input, select, textarea").forEach((field) => {
                if (field.type !== "hidden") field.disabled = true;
            });
            const openCheckout = () => {
                button.disabled = true;
                button.textContent = "Opening payment options...";
                errorBox.classList.add("d-none");
                statusBox.textContent = "Connecting to Razorpay securely…";
                try {
                    checkout.open();
                } catch (error) {
                    console.error("Could not open Razorpay checkout.", error);
                    showError("Checkout could not open. Please try again.");
                }
            };
            button.addEventListener("click", openCheckout);
            openCheckout();
        })();
