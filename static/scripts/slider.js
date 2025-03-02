document.addEventListener("DOMContentLoaded", function () {
  const sliderContainer = document.querySelector(
    ".popular-health-plans .container"
  );
  const prevBtn = document.querySelector(".slider-btn--prev");
  const nextBtn = document.querySelector(".slider-btn--next");
  let currentIndex = 0;

  function updateSlider() {
    const slideWidth = sliderContainer.querySelector(
      ".health-plan-item-container"
    ).clientWidth;
    sliderContainer.style.transform = `translateX(-${
      currentIndex * slideWidth
    }px)`;
  }

  prevBtn.addEventListener("click", function () {
    if (currentIndex > 0) {
      currentIndex--;
      updateSlider();
    }
  });

  nextBtn.addEventListener("click", function () {
    if (currentIndex < sliderContainer.children.length - 2) {
      currentIndex++;
      updateSlider();
    }
  });

  window.addEventListener("resize", updateSlider);
});
