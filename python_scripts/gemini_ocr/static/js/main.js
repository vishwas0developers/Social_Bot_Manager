// static/js/main.js

document.addEventListener('DOMContentLoaded', () => {
    console.log("DOM fully loaded and parsed");

    // --- Drag and Drop ---
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file');
    const fileNameDisplay = document.getElementById('file-name-display');
    const form = document.getElementById('upload-form');
    const submitButton = document.getElementById('submit-button');
    const progressArea = document.getElementById('progress-area');
    const progressBar = document.getElementById('progress-bar');
    const progressStatus = document.getElementById('progress-status');

    if (dropZone && fileInput && fileNameDisplay) {
        // Click drop zone to trigger file input
        dropZone.addEventListener('click', () => {
            fileInput.click();
        });

        // Highlight drop zone when dragging over
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault(); // Prevent default behavior (file open)
            dropZone.classList.add('dragover');
        });

        // Remove highlight when dragging leaves
        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('dragover');
        });

        // Handle file drop
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault(); // Prevent default behavior
            dropZone.classList.remove('dragover');

            if (e.dataTransfer.files.length) {
                fileInput.files = e.dataTransfer.files; // Assign dropped files to input
                fileNameDisplay.textContent = `Selected: ${fileInput.files[0].name}`;
                console.log("File dropped:", fileInput.files[0].name);
            }
        });

        // Update display when file is selected manually
        fileInput.addEventListener('change', () => {
            if (fileInput.files.length) {
                fileNameDisplay.textContent = `Selected: ${fileInput.files[0].name}`;
                console.log("File selected:", fileInput.files[0].name);
            } else {
                 fileNameDisplay.textContent = '';
            }
        });
    } else {
         console.warn("Drop zone or file input elements not found.");
    }

    // --- Form Submission & Progress (Basic Simulation) ---
    if (form && progressArea && progressBar && progressStatus && submitButton) {
        form.addEventListener('submit', (e) => {
            // Basic check if file is selected
            if (fileInput && fileInput.files.length === 0) {
                alert("Please select a file to upload.");
                e.preventDefault(); // Stop submission
                return;
            }

            console.log("Form submitted, showing progress area...");
            progressArea.style.display = 'block';
            submitButton.disabled = true; // Disable button during processing
            submitButton.textContent = 'Processing...';

            // Simulate progress updates (Replace with actual progress logic if implemented)
            let progress = 0;
            progressStatus.textContent = '📤 Uploading...';
            progressBar.style.width = '10%';
            progressBar.textContent = '10%';

            // You would need actual progress reporting (e.g., from AJAX upload or SSE)
            // to make this real. This is just a visual placeholder.
            setTimeout(() => {
                 progressStatus.textContent = '🤖 Sending to AI... (This might take a while)';
                 progressBar.style.width = '50%';
                 progressBar.textContent = '50%';
            }, 1500); // Simulate delay

            // NOTE: The form will submit normally after this point,
            // and the backend will take over. The progress bar here
            // won't reflect the actual backend processing without SSE/WebSockets.
        });
    }

    // --- Pagination and View Toggle (Placeholders on results page) ---
    // Logic for pagination clicks (if not using standard links) and view toggles
    // would go here, likely triggered by elements only present on results.html
    // Example:
    // const viewFullBtn = document.getElementById('view-full-btn');
    // if (viewFullBtn) {
    //     console.log("Results page detected (view button found).");
    //     // Add event listeners for toggle buttons etc.
    // }

});

console.log("main.js loaded");