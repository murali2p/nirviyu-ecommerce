// document.addEventListener("DOMContentLoaded", function () {
//   const navIcon = document.querySelector(".nav-icon");
//   const navList = document.querySelector(".nav-list");

//   navIcon.addEventListener("click", function () {
//     navList.classList.toggle("show");
//   });
// });

function toggleNav() {
  let sidebar = document.getElementById("sidebar");
  if (sidebar.style.width === "150px") {
    sidebar.style.width = "0";
  } else {
    sidebar.style.width = "150px";
  }
}
