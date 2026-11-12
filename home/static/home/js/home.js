(() => {
    const slider = document.querySelector("[data-hero-slider]");
    if (!slider) return;

    const backgrounds = Array.from(slider.querySelectorAll(".hero-slide"));
    const contents = Array.from(slider.querySelectorAll("[data-hero-content]"));
    const dots = Array.from(slider.querySelectorAll("[data-hero-to]"));
    const previousButton = slider.querySelector("[data-hero-previous]");
    const nextButton = slider.querySelector("[data-hero-next]");
    const pauseButton = slider.querySelector("[data-hero-pause]");
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

    if (!backgrounds.length || backgrounds.length !== contents.length) return;

    let activeIndex = 0;
    let timerId;
    let pausedByUser = false;
    let pointerInside = false;
    let focusInside = false;

    const stopTimer = () => {
        window.clearTimeout(timerId);
    };

    const scheduleNext = () => {
        stopTimer();
        if (pausedByUser || pointerInside || focusInside || reduceMotion.matches) return;

        timerId = window.setTimeout(() => {
            if (document.visibilityState === "visible") {
                showSlide(activeIndex + 1);
            } else {
                scheduleNext();
            }
        }, 3000);
    };

    const showSlide = (index) => {
        activeIndex = (index + backgrounds.length) % backgrounds.length;
        backgrounds.forEach((slide, slideIndex) => {
            slide.classList.toggle("is-active", slideIndex === activeIndex);
        });
        contents.forEach((slide, slideIndex) => {
            const isActive = slideIndex === activeIndex;
            slide.classList.toggle("is-active", isActive);
            slide.setAttribute("aria-hidden", String(!isActive));
        });
        dots.forEach((dot, dotIndex) => {
            const isActive = dotIndex === activeIndex;
            dot.classList.toggle("is-active", isActive);
            if (isActive) {
                dot.setAttribute("aria-current", "true");
            } else {
                dot.removeAttribute("aria-current");
            }
        });
        scheduleNext();
    };

    previousButton.addEventListener("click", () => showSlide(activeIndex - 1));
    nextButton.addEventListener("click", () => showSlide(activeIndex + 1));
    dots.forEach((dot) => {
        dot.addEventListener("click", () => showSlide(Number(dot.dataset.heroTo)));
    });

    pauseButton.addEventListener("click", () => {
        pausedByUser = !pausedByUser;
        pauseButton.setAttribute(
            "aria-label",
            pausedByUser ? "Resume slideshow" : "Pause slideshow"
        );
        pauseButton.innerHTML = pausedByUser
            ? '<i class="bi bi-play-fill"></i>'
            : '<i class="bi bi-pause-fill"></i>';
        scheduleNext();
    });

    slider.addEventListener("mouseenter", () => {
        pointerInside = true;
        stopTimer();
    });
    slider.addEventListener("mouseleave", () => {
        pointerInside = false;
        scheduleNext();
    });
    slider.addEventListener("focusin", () => {
        focusInside = true;
        stopTimer();
    });
    slider.addEventListener("focusout", (event) => {
        if (!slider.contains(event.relatedTarget)) {
            focusInside = false;
            scheduleNext();
        }
    });
    document.addEventListener("visibilitychange", scheduleNext);
    if (typeof reduceMotion.addEventListener === "function") {
        reduceMotion.addEventListener("change", scheduleNext);
    } else if (typeof reduceMotion.addListener === "function") {
        reduceMotion.addListener(scheduleNext);
    }

    scheduleNext();
})();

(() => {
    const carousels = document.querySelectorAll("[data-home-carousel]");

    carousels.forEach((carousel) => {
        const track = carousel.querySelector(".home-carousel-track");
        const section = carousel.closest("section");
        const previousButton = section?.querySelector("[data-home-carousel-prev]");
        const nextButton = section?.querySelector("[data-home-carousel-next]");
        const controls = section?.querySelector(".home-carousel-controls");

        if (!track) return;

        const getStep = () => {
            const firstItem = track.querySelector(".home-carousel-item");
            if (!firstItem) return 320;
            const style = window.getComputedStyle(track);
            const gap = parseFloat(style.columnGap || style.gap) || 20;
            return firstItem.getBoundingClientRect().width + gap;
        };

        const scrollNext = () => {
            const maxScroll = track.scrollWidth - track.clientWidth;
            if (maxScroll <= 10) return;
            const step = getStep();
            if (track.scrollLeft >= maxScroll - 15) {
                track.scrollTo({ left: 0, behavior: "smooth" });
            } else {
                track.scrollBy({ left: step, behavior: "smooth" });
            }
        };

        const scrollPrev = () => {
            const maxScroll = track.scrollWidth - track.clientWidth;
            if (maxScroll <= 10) return;
            const step = getStep();
            if (track.scrollLeft <= 15) {
                track.scrollTo({ left: maxScroll, behavior: "smooth" });
            } else {
                track.scrollBy({ left: -step, behavior: "smooth" });
            }
        };

        // 1-second auto-slide timer
        let autoSlideTimer = null;
        let isUserInteracting = false;

        const startAutoSlide = () => {
            stopAutoSlide();
            if (isUserInteracting) return;
            autoSlideTimer = setInterval(() => {
                if (document.visibilityState === "visible" && !isUserInteracting) {
                    scrollNext();
                }
            }, 2000);
        };

        const stopAutoSlide = () => {
            if (autoSlideTimer) {
                clearInterval(autoSlideTimer);
                autoSlideTimer = null;
            }
        };

        if (previousButton) {
            previousButton.disabled = false;
            previousButton.addEventListener("click", (e) => {
                e.preventDefault();
                scrollPrev();
                startAutoSlide();
            });
        }

        if (nextButton) {
            nextButton.disabled = false;
            nextButton.addEventListener("click", (e) => {
                e.preventDefault();
                scrollNext();
                startAutoSlide();
            });
        }

        // Pause on mouse hover / touch, resume on leave
        carousel.addEventListener("mouseenter", () => {
            isUserInteracting = true;
            stopAutoSlide();
        });

        carousel.addEventListener("mouseleave", () => {
            isUserInteracting = false;
            startAutoSlide();
        });

        carousel.addEventListener("focusin", () => {
            isUserInteracting = true;
            stopAutoSlide();
        });

        carousel.addEventListener("focusout", () => {
            isUserInteracting = false;
            startAutoSlide();
        });

        carousel.addEventListener("touchstart", () => {
            isUserInteracting = true;
            stopAutoSlide();
        }, { passive: true });

        carousel.addEventListener("touchend", () => {
            isUserInteracting = false;
            startAutoSlide();
        }, { passive: true });

        // Mouse drag swipe support
        let isMouseDown = false;
        let startX = 0;
        let scrollStart = 0;

        track.addEventListener("mousedown", (e) => {
            isMouseDown = true;
            startX = e.pageX - track.offsetLeft;
            scrollStart = track.scrollLeft;
            isUserInteracting = true;
            stopAutoSlide();
        });

        window.addEventListener("mouseup", () => {
            if (isMouseDown) {
                isMouseDown = false;
                isUserInteracting = false;
                startAutoSlide();
            }
        });

        track.addEventListener("mousemove", (e) => {
            if (!isMouseDown) return;
            e.preventDefault();
            const x = e.pageX - track.offsetLeft;
            const walk = (x - startX) * 1.5;
            track.scrollLeft = scrollStart - walk;
        });

        // Initialize and start sliding
        startAutoSlide();
    });
})();
