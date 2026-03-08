function togglePassword() {
  const pass = document.getElementById("password");
  const icon = document.getElementById("eyeIcon");

  if (pass.type === "password") {
    pass.type = "text";
    icon.classList.replace("fa-eye","fa-eye-slash");
  } else {
    pass.type = "password";
    icon.classList.replace("fa-eye-slash","fa-eye");
  }
}