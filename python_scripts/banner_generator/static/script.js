document.addEventListener('DOMContentLoaded', () => {
    // Get modal elements
    const uploadModal = document.getElementById("uploadModal");
    const uploadModalTitle = document.getElementById("modalTitle");
    const uploadModalForm = document.getElementById("modalUploadForm");
    const uploadModalCloseBtn = uploadModal ? uploadModal.querySelector(".close-button") : null;

    const editModal = document.getElementById("editModal");
    const editModalTitle = document.getElementById("editModalTitle");
    const editModalForm = document.getElementById("editModalForm");
    const editModalCloseBtn = editModal ? editModal.querySelector(".close-button") : null;

    // Function to open the Excel Upload modal
    window.openUploadModal = function(templateId, templateName) {
        if (!uploadModal || !uploadModalTitle || !uploadModalForm) {
            console.error("Upload Modal elements missing!");
            return;
        }
        const escapedName = escapeHtml(templateName);
        uploadModalTitle.textContent = `Upload Excel for: ${escapedName}`;
        uploadModalForm.action = `/banner_generator/generate/${templateId}`;
        uploadModal.style.display = "block";
    }

    // Function to open the Edit Template modal
    window.openEditModal = function(templateId, templateName) {
        if (!editModal || !editModalTitle || !editModalForm) {
            console.error("Edit Modal elements missing!");
            return;
        }
        const escapedName = escapeHtml(templateName);
        editModalTitle.textContent = `Replace HTML for: ${escapedName}`;
        editModalForm.action = `/banner_generator/edit_template/${templateId}`; // Set correct action URL
        editModal.style.display = "block";
    }

    // Function to close ANY modal by its ID
    window.closeModal = function(modalId) {
        const modalToClose = document.getElementById(modalId);
        if (modalToClose) {
            modalToClose.style.display = "none";
            const fileInput = modalToClose.querySelector("input[type='file']");
            if (fileInput) { fileInput.value = ''; } // Clear file input
        }
    }

    // Assign close event listeners using the function
    if (uploadModalCloseBtn) {
        uploadModalCloseBtn.onclick = () => closeModal('uploadModal');
    }
    if (editModalCloseBtn) {
        editModalCloseBtn.onclick = () => closeModal('editModal');
    }

    // Close modal if background is clicked
    window.onclick = function(event) {
        if (event.target == uploadModal) closeModal('uploadModal');
        if (event.target == editModal) closeModal('editModal');
    }

    // Close modal on Escape key press
     document.addEventListener('keydown', function (event) {
        if (event.key === "Escape") {
            if (uploadModal && uploadModal.style.display === "block") closeModal('uploadModal');
            if (editModal && editModal.style.display === "block") closeModal('editModal');
        }
    });


    // Auto-hide flash messages
    const flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(flashMessage => {
        setTimeout(() => {
            flashMessage.classList.add('fade-out'); // Add class to trigger transition
            // Remove the element after the transition completes
            flashMessage.addEventListener('transitionend', () => flashMessage.remove());
        }, 5000); // Start fade out after 5 seconds
    });

    // Simple HTML escaping function
    function escapeHtml(unsafe) {
        if (!unsafe) return "";
        return unsafe
             .replace(/&/g, "&")
             .replace(/</g, "<")
             .replace(/>/g, ">")
             .replace(/"/g, "&quot;")
             .replace(/'/g, "'");
     }

}); // End DOMContentLoaded