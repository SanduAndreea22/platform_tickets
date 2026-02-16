const chatBox = document.getElementById("chatBox");

function scrollToBottom(force = false) {
  if (!chatBox) return;

  const nearBottom =
    chatBox.scrollHeight - chatBox.scrollTop - chatBox.clientHeight < 80;

  if (force || nearBottom) {
    chatBox.scrollTo({
      top: chatBox.scrollHeight,
      behavior: "smooth"
    });
  }
}

// scroll la load
window.addEventListener("load", () => scrollToBottom(true));
