(() => {
    const loader = document.querySelector(".page-loader");
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

    if (loader) {
        loader.classList.add("is-visible");
        window.setTimeout(() => loader.classList.remove("is-visible"), 360);

        window.addEventListener("pageshow", (event) => {
            if (event.persisted) {
                loader.classList.remove("is-visible");
            }
        });
    }

    document.body.classList.add("motion-ready");

    const revealElements = document.querySelectorAll(
        ".section-space .container > .row, " +
        ".section-space .section-top, " +
        ".planning-step, .celebration-promise, " +
        ".listing-card, .service-card, .package-card, .cta-inner"
    );

    revealElements.forEach((element, index) => {
        element.dataset.reveal = "";
        element.style.transitionDelay = `${Math.min(index % 4, 3) * 70}ms`;
    });

    if (reduceMotion.matches || !("IntersectionObserver" in window)) {
        revealElements.forEach((element) => element.classList.add("is-revealed"));
    } else {
        const observer = new IntersectionObserver((entries, currentObserver) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    entry.target.classList.add("is-revealed");
                    currentObserver.unobserve(entry.target);
                }
            });
        }, { threshold: 0.12 });

        revealElements.forEach((element) => observer.observe(element));
    }

    document.addEventListener("click", (event) => {
        const link = event.target.closest("a[href]");
        if (
            !loader ||
            !link ||
            event.defaultPrevented ||
            event.button !== 0 ||
            event.metaKey ||
            event.ctrlKey ||
            event.shiftKey ||
            event.altKey ||
            link.target ||
            link.hasAttribute("download")
        ) {
            return;
        }

        const destination = new URL(link.href, window.location.href);
        if (
            destination.origin !== window.location.origin ||
            (destination.pathname === window.location.pathname &&
                destination.search === window.location.search)
        ) {
            return;
        }

        event.preventDefault();
        loader.classList.add("is-visible");
        window.setTimeout(() => {
            window.location.assign(destination.href);
        }, 170);
    });
})();
