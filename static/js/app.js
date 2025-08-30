const socket = io.connect(
  location.protocol + "//" + document.domain + ":" + location.port
);

socket.on("connect", function () {
  console.log("Connected to websocket!");
});

socket.on("generation_error", function (data) {});

socket.on("notification", function (data) {
  let container = document.querySelector(".message-container");

  let messageDiv = document.createElement("div");
  messageDiv.classList.add("card-panel", "teal", "dark-4", "notification");
  messageDiv.innerText = data.message;

  messageDiv.style.opacity = 0;
  messageDiv.style.transition = "opacity 0.5s";

  messageDiv.addEventListener("click", function() {
    this.remove();
  })
  container.appendChild(messageDiv);

  void messageDiv.offsetWidth;

  messageDiv.style.opacity = 1;

  setTimeout(() => {
    messageDiv.style.opacity = 0;
    messageDiv.remove()
  }, 2500);
});

function toggleFavorite(event) {
  const storyId = event.target.dataset.storyId;
  fetch("/api/toggle_favorite/" + storyId, { method: "POST" })
    .then(()=>{
      window.location.reload();
    })
}

function generateUUID() {
  // Generates a simple UUID string.
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
    let r = (Math.random() * 16) | 0,
      v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

function showSpinner() {
  const spinner = document.getElementById("spinner");
  if (spinner) spinner.style.display = "block";
}
function hideSpinner() {
  const spinner = document.getElementById("spinner");
  if (spinner) spinner.style.display = "none";
}

function getStoryId() {
  const parts = window.location.pathname.split("/");
  return parts[parts.length - 2];
}

document.addEventListener('DOMContentLoaded', () => {
  var elems = document.querySelectorAll('.sidenav');
  M.Sidenav.init(elems);
  var sidenavElems = document.querySelectorAll('.sidenav');
  M.Sidenav.init(sidenavElems);
  let msgContainer = document.querySelectorAll(".message-container .notification");
  msgContainer.forEach((element) =>{
    element.style.transition = "opacity 0.5s";
    void element.offsetWidth;
    setTimeout(() => {
      element.style.opacity = 0;
      element.remove();
    }, 2500);
  })
})