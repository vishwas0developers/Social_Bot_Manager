// Run Script Function
function runScript(folderName) {
  window.location.href = `/${folderName}`;
}

// Confirm Delete Script
function confirmDelete(event, folderName) {
  event.stopPropagation();
  if (confirm(`Are you sure you want to delete '${folderName}'?`)) {
    fetch(`/delete/${folderName}`)
      .then(response => response.json())
      .then(data => {
        alert(data.message);
        location.reload();
      })
      .catch(error => console.error("Error deleting script:", error));
  }
}

// Edit Script Function
function editScript(event, folderName, buttonName) {
  event.stopPropagation();
  document.getElementById("editFolderName").value = folderName;
  document.getElementById("newButtonName").value = buttonName;
  document.getElementById("editModal").style.display = "block";
}

// Save Edit Changes
function saveEdit() {
  const folderName = document.getElementById("editFolderName").value;
  const newButtonName = document.getElementById("newButtonName").value;
  const newZipFile = document.getElementById("newZipFile").files[0];
  const newImageFile = document.getElementById("newImage").files[0];

  const formData = new FormData();
  formData.append("button_name", newButtonName);
  if (newZipFile) formData.append("zip_file", newZipFile);
  if (newImageFile) formData.append("image", newImageFile);

  fetch(`/edit/${folderName}`, {
    method: "POST",
    body: formData
  })
    .then(response => response.json())
    .then(data => {
      if (data.status === "success") {
        alert(data.message);
        closeModal("editModal");
        location.reload();
      } else {
        alert(`Error: ${data.message}`);
      }
    })
    .catch(error => {
      console.error("Error:", error);
      alert("Error updating script. Please try again.");
    });
}

// Close Modal
function closeModal(modalId) {
  document.getElementById(modalId).style.display = "none";
}

// Upload with Progress Bar
function uploadWithProgress(event) {
  event.preventDefault();
  const formData = new FormData(document.getElementById("upload-form"));

  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/upload", true);

  document.getElementById("progress-container").style.display = "block";

  xhr.upload.onprogress = function (event) {
    if (event.lengthComputable) {
      const percent = (event.loaded / event.total) * 100;
      document.getElementById("progress-bar").style.width = percent + "%";
      document.getElementById("progress-text").innerText = Math.round(percent) + "%";
    }
  };

  xhr.onload = function () {
    if (xhr.status == 200) {
      alert("Upload successful!");
      window.location.reload();
    } else {
      alert("Error during upload.");
    }
  };

  xhr.send(formData);
}

// Attach handler
document.getElementById("upload-form").onsubmit = uploadWithProgress;
