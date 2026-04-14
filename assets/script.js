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
        
        const authToken = getCookie('session_auth_key');
        const csrfToken = getCookie('session_auth_key'); // They share the same secret for simplicity
        
        console.log("Request started. Auth context:", !!authToken);
        
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
            // 1. POST Resume
            if (resumeFile && resumeFile.size > 0) {
                const resumeFormData = new FormData();
                resumeFormData.append('file', resumeFile);

                const resumeRes = await fetch(`${API_BASE}/upload-resume`, {
                    method: 'POST',
                    headers: { 
                        'X-CSRF-TOKEN': csrfToken,
                        'X-API-KEY': authToken 
                    },
                    body: resumeFormData,
                    credentials: 'include',
                    signal: controller.signal
                });
                
                const resumeData = await resumeRes.json();
                if (!resumeRes.ok) {
                    const msg = resumeData.detail || resumeData.message || 'Failed to analyze resume.';
                    throw new Error(typeof msg === 'object' ? JSON.stringify(msg) : msg);
                }
                
                if (resumeData.profile && resumeData.profile.skills) {
                    preferences.skills = resumeData.profile.skills;
                }
            }

            // 2. POST Preferences
            const prefRes = await fetch(`${API_BASE}/profile`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'X-CSRF-TOKEN': csrfToken,
                    'X-API-KEY': authToken 
                },
                body: JSON.stringify(preferences),
                credentials: 'include',
                signal: controller.signal
            });
            const prefData = await prefRes.json();
            if (!prefRes.ok) {
                const msg = prefData.detail || prefData.message || 'Failed to save profile preferences.';
                throw new Error(typeof msg === 'object' ? JSON.stringify(msg) : msg);
            }

            // 3. POST Job Matching
            const scanRes = await fetch(`${API_BASE}/trigger-scan`, {
                method: 'POST',
                headers: { 
                    'X-CSRF-TOKEN': csrfToken,
                    'X-API-KEY': authToken 
                },
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
            console.error("Critical submission failure:", error);
            
            let finalMsg = "Unknown Error";
            
            if (error.name === 'AbortError') {
                finalMsg = "Timeout: The server is taking too long. Try refreshing.";
            } else if (error instanceof Error) {
                finalMsg = error.message;
            } else if (typeof error === 'object') {
                finalMsg = JSON.stringify(error);
            } else {
                finalMsg = String(error);
            }

            // Final safety check for [object Object]
            if (finalMsg === "[object Object]") {
                finalMsg = "Connection failed or validation error. Check console.";
            }

            statusDiv.textContent = 'Error: ' + finalMsg;
            statusDiv.className = 'status error';
        } finally {
            clearTimeout(timeoutId);
            submitBtn.disabled = false;
            // Stop loading state (Requirement 3)
            if (typeof window.setLoading === 'function') window.setLoading(false);
            
            console.log("Request ended"); 
        }
    });
});
