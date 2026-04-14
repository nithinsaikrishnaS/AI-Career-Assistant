document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('onboardingForm');
    const resumeInput = document.getElementById('resume');
    const uploadText = document.getElementById('uploadText');
    const submitBtn = document.getElementById('submitBtn');
    const statusDiv = document.getElementById('status');
    const API_BASE = '';

    // Assistant Cookie Helper (Requirement: Production CSRF Security)
    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
    }

    // Handle File Selection
    resumeInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            if (file.type !== 'application/pdf') {
                statusDiv.textContent = 'Error: Only PDF files are allowed.';
                statusDiv.className = 'status error';
                resumeInput.value = '';
                uploadText.textContent = 'Click to upload resume';
                return;
            }
            uploadText.textContent = file.name;
            statusDiv.textContent = '';
        }
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const csrfToken = getCookie('session_auth_key');
        console.log("Request started with CSRF context:", !!csrfToken);
        
        // Reset UI
        statusDiv.textContent = 'Processing...';
        statusDiv.className = 'status';
        submitBtn.disabled = true;

        const formData = new FormData(form);
        const preferences = {
            role: formData.get('role'),
            location: formData.get('location'),
            domain: formData.get('domain'),
            experience: formData.get('experience'),
            job_type: formData.get('job_type'),
            preferred_tech: formData.get('preferred_tech'),
            salary_range: formData.get('salary_range'),
            availability: formData.get('availability'),
            work_mode: formData.get('work_mode'),
            company_type: formData.get('company_type'),
            notifications: formData.get('notifications') === 'on',
            skills: [] // Add empty skills for backend validation
        };
        const resumeFile = formData.get('resume');

        // Add timeout handling (Requirement 4)
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 15000);

        try {
            // 1. POST Resume (Extract skills without resetting profile)
            if (resumeFile && resumeFile.size > 0) {
                const resumeFormData = new FormData();
                resumeFormData.append('file', resumeFile);

                const resumeRes = await fetch(`${API_BASE}/upload-resume`, {
                    method: 'POST',
                    headers: { 'X-CSRF-TOKEN': csrfToken },
                    body: resumeFormData,
                    credentials: 'include',
                    signal: controller.signal
                });
                
                const resumeData = await resumeRes.json();
                if (!resumeRes.ok) throw new Error(resumeData.detail || resumeData.message || 'Failed to analyze resume.');
                
                if (resumeData.profile && resumeData.profile.skills) {
                    preferences.skills = resumeData.profile.skills;
                }
            }

            // 2. POST Preferences
            const prefRes = await fetch(`${API_BASE}/profile`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'X-CSRF-TOKEN': csrfToken
                },
                body: JSON.stringify(preferences),
                credentials: 'include',
                signal: controller.signal
            });
            const prefData = await prefRes.json();
            if (!prefRes.ok) throw new Error(prefData.message || prefData.detail || 'Failed to save profile preferences.');

            // 3. POST Job Matching (Trigger automated discovery)
            const scanRes = await fetch(`${API_BASE}/trigger-scan`, {
                method: 'POST',
                headers: { 'X-CSRF-TOKEN': csrfToken },
                credentials: 'include',
                signal: controller.signal
            });
            if (!scanRes.ok) console.warn("Job matching scan failed to start.");

            // Fix frontend: Redirect on success (Requirement 3)
            statusDiv.textContent = 'Profile saved successfully! Redirecting...';
            statusDiv.className = 'status success';
            
            setTimeout(() => {
                window.location.href = 'dashboard.html';
            }, 1000);
            
        } catch (error) {
            // Fix frontend: Handle API response correctly
            if (error.name === 'AbortError') {
                statusDiv.textContent = 'Error: Request timed out. Please try again.';
            } else {
                statusDiv.textContent = 'Error: ' + error.message;
            }
            statusDiv.className = 'status error';
        } finally {
            clearTimeout(timeoutId);
            submitBtn.disabled = false;
            // Stop loading state (Requirement 3)
            if (typeof window.setLoading === 'function') window.setLoading(false);
            
            console.log("Request ended"); // Requirement 5
        }
    });
});
