// Main JavaScript for Student Visualization Dashboard

// Wait until the DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // File upload preview
    const fileInput = document.getElementById('file');
    const fileLabel = document.querySelector('.custom-file-label');
    
    if (fileInput && fileLabel) {
        fileInput.addEventListener('change', function() {
            let fileName = this.files[0] ? this.files[0].name : 'Choose file';
            fileLabel.textContent = fileName;
        });
    }

    // Drag and drop upload zone
    const uploadZone = document.querySelector('.file-upload-wrapper');
    if (uploadZone) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadZone.addEventListener(eventName, preventDefaults, false);
        });

        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }

        ['dragenter', 'dragover'].forEach(eventName => {
            uploadZone.addEventListener(eventName, highlight, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            uploadZone.addEventListener(eventName, unhighlight, false);
        });

        function highlight() {
            uploadZone.classList.add('border-primary');
        }

        function unhighlight() {
            uploadZone.classList.remove('border-primary');
        }

        uploadZone.addEventListener('drop', handleDrop, false);

        function handleDrop(e) {
            const dt = e.dataTransfer;
            const files = dt.files;
            if (fileInput) {
                fileInput.files = files;
                fileLabel.textContent = files[0].name;
            }
        }
    }

    // Data table search functionality
    const searchInput = document.getElementById('student-search');
    if (searchInput) {
        searchInput.addEventListener('keyup', function() {
            const searchTerm = this.value.toLowerCase();
            const tableRows = document.querySelectorAll('tbody tr');
            
            tableRows.forEach(row => {
                const text = row.textContent.toLowerCase();
                if (text.includes(searchTerm)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    }

    // Export functions
    const exportCSVBtn = document.getElementById('export-csv');
    if (exportCSVBtn) {
        exportCSVBtn.addEventListener('click', function() {
            // This is a simple example - in a real app, you would make an API call
            // to get the data in CSV format
            alert('In a real application, this would download the data as CSV');
        });
    }

    const exportPDFBtn = document.getElementById('export-pdf');
    if (exportPDFBtn) {
        exportPDFBtn.addEventListener('click', function() {
            // This is a simple example - in a real app, you would make an API call
            // to get the data in PDF format
            alert('In a real application, this would download the data as PDF');
        });
    }

    const printDashboardBtn = document.getElementById('print-dashboard');
    if (printDashboardBtn) {
        printDashboardBtn.addEventListener('click', function() {
            window.print();
        });
    }

    // Filter application
    const applyFiltersBtn = document.getElementById('apply-filters');
    if (applyFiltersBtn) {
        applyFiltersBtn.addEventListener('click', function() {
            const program = document.getElementById('program-filter').value;
            const status = document.getElementById('status-filter').value;
            const year = document.getElementById('year-filter').value;
            
            // In a real app, this would make an API call with the filter parameters
            console.log(`Applying filters: Program=${program}, Status=${status}, Year=${year}`);
            
            // Reload visualizations with filtered data
            // This would normally make an API call to get filtered data
            alert(`Filters applied: Program=${program}, Status=${status}, Year=${year}`);
        });
    }

    const resetFiltersBtn = document.getElementById('reset-filters');
    if (resetFiltersBtn) {
        resetFiltersBtn.addEventListener('click', function() {
            const filters = document.querySelectorAll('select[id$="-filter"]');
            filters.forEach(filter => {
                filter.value = 'all';
            });
            
            // Reset visualizations to show all data
            // This would normally make an API call to get unfiltered data
            console.log('Filters reset');
        });
    }
});

// Function to format numbers with commas
function formatNumber(num) {
    return num.toString().replace(/(\d)(?=(\d{3})+(?!\d))/g, '$1,');
}

// Function to create a student detail modal dynamically
function showStudentDetails(studentId) {
    // In a real app, this would make an API call to get student details
    console.log(`Showing details for student ID: ${studentId}`);
    
    // This is just a placeholder for demonstration purposes
    const studentModal = new bootstrap.Modal(document.getElementById('studentDetailModal'));
    studentModal.show();
}