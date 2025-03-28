document.addEventListener("DOMContentLoaded", function () {
  const productContainer = document.getElementById("productList");
  const prevButton = document.querySelector(".slider-btn--prev1");
  const nextButton = document.querySelector(".slider-btn--next1");

  const scrollAmount = 300; // Adjust scroll amount as needed

  nextButton.addEventListener("click", function () {
    productContainer.scrollBy({ left: scrollAmount, behavior: "smooth" });
  });

  prevButton.addEventListener("click", function () {
    productContainer.scrollBy({ left: -scrollAmount, behavior: "smooth" });
  });
});
