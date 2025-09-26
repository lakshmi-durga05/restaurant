// Main JavaScript for Restaurant Booking System
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Chatbot functionality
    setupChatbot();
    
    // Initialize date picker with today's date
    initDatePicker();
    
    // Setup form validation
    setupFormValidation();
    
    // Handle section selection
    setupSectionSelection();
    
    // Handle time slot selection
    setupTimeSlotSelection();
    
    // Handle form submission
    setupFormSubmission();
    
    // Setup navigation between steps
    setupNavigation();
});

// Chatbot functionality
function setupChatbot() {
    const chatbotButton = document.getElementById('chatbotButton');
    const chatbotWindow = document.getElementById('chatbotWindow');
    const closeChatbot = document.getElementById('closeChatbot');
    const sendMessageBtn = document.getElementById('sendMessage');
    const userMessageInput = document.getElementById('userMessage');
    const chatMessages = document.getElementById('chatbotMessages');
    
    if (!chatbotButton) return;
    
    // Toggle chat window
    chatbotButton.addEventListener('click', function() {
        const isVisible = chatbotWindow.style.display === 'block';
        chatbotWindow.style.display = isVisible ? 'none' : 'block';
        
        if (!isVisible) {
            // Add welcome message if it's the first time opening
            if (chatMessages.children.length <= 1) { // Only the initial message exists
                addBotMessage("Hello! I'm your restaurant assistant. I can help you with reservations, menu questions, and more. How can I assist you today?");
            }
            
            // Auto-focus the input
            setTimeout(() => {
                userMessageInput.focus();
            }, 100);
        }
    });
    
    // Close chat window
    closeChatbot.addEventListener('click', function() {
        chatbotWindow.style.display = 'none';
    });
    
    // Send message on button click
    sendMessageBtn.addEventListener('click', sendMessage);
    
    // Send message on Enter key
    userMessageInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
    
    function sendMessage() {
        const message = userMessageInput.value.trim();
        if (message === '') return;
        
        // Add user message to chat
        addUserMessage(message);
        userMessageInput.value = '';
        
        // Process the message (in a real app, this would call your API)
        processUserMessage(message);
    }
    
    function addUserMessage(text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user';
        messageDiv.innerHTML = `<p>${escapeHtml(text)}</p>`;
        chatMessages.appendChild(messageDiv);
        scrollToBottom();
    }
    
    function addBotMessage(text, isTyping = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot';
        
        if (isTyping) {
            messageDiv.innerHTML = `
                <div class="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            `;
        } else {
            messageDiv.innerHTML = `<p>${text}</p>`;
        }
        
        chatMessages.appendChild(messageDiv);
        scrollToBottom();
        
        return messageDiv;
    }
    
    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    function processUserMessage(message) {
        // Show typing indicator
        const typingIndicator = addBotMessage('', true);
        
        // In a real app, you would send the message to your backend API
        // and handle the response asynchronously
        setTimeout(() => {
            // Remove typing indicator
            typingIndicator.remove();
            
            // Simple response logic (in a real app, this would be handled by your AI/NLP service)
            const lowerMessage = message.toLowerCase();
            let response = "";
            
            if (lowerMessage.includes('hello') || lowerMessage.includes('hi') || lowerMessage.includes('hey')) {
                response = "Hello! How can I assist you today? I can help with reservations, menu questions, or any other inquiries.";
            } else if (lowerMessage.includes('reservation') || lowerMessage.includes('book') || lowerMessage.includes('table')) {
                response = "You can make a reservation by clicking the 'Book a Table' button at the top of the page. Would you like me to take you there?";
            } else if (lowerMessage.includes('menu') || lowerMessage.includes('food') || lowerMessage.includes('drink')) {
                response = "Our menu features a variety of delicious dishes made with locally-sourced ingredients. You can view our full menu on the 'Menu' page. Is there anything specific you'd like to know about?";
            } else if (lowerMessage.includes('hours') || lowerMessage.includes('open') || lowerMessage.includes('close')) {
                response = "Our opening hours are:\n\nMonday - Friday: 11:00 AM - 10:00 PM\nSaturday - Sunday: 10:00 AM - 11:00 PM\n\nWe look forward to serving you!";
            } else if (lowerMessage.includes('contact') || lowerMessage.includes('phone') || lowerMessage.includes('email')) {
                response = "You can contact us at:\n\n📞 Phone: +1 234 567 8900\n📧 Email: info@lakesidebistro.com\n📍 Address: 123 Lakeview Drive, Lakeside\n\nIs there anything specific you'd like to know?";
            } else if (lowerMessage.includes('thank') || lowerMessage.includes('thanks')) {
                response = "You're welcome! Is there anything else I can help you with?";
            } else {
                response = "I'm sorry, I didn't understand that. I can help with reservations, menu questions, or general inquiries. Could you please rephrase your question?";
            }
            
            // Add bot's response
            addBotMessage(response);
        }, 1000);
    }
    
    // Helper function to escape HTML
    function escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;")
            .replace(/\n/g, "<br>");
    }
}

// Initialize date picker with today's date
function initDatePicker() {
    const dateInput = document.getElementById('reservationDate');
    if (!dateInput) return;
    
    // Set minimum date to today
    const today = new Date().toISOString().split('T')[0];
    dateInput.min = today;
    
    // Set default date to today
    dateInput.value = today;
    
    // Trigger change event to load available times
    dateInput.dispatchEvent(new Event('change'));
}

// Setup form validation
function setupFormValidation() {
    const form = document.querySelector('form');
    if (!form) return;
    
    // Add custom validation for phone number
    const phoneInput = document.getElementById('phone');
    if (phoneInput) {
        phoneInput.addEventListener('input', function(e) {
            // Remove any non-digit characters
            this.value = this.value.replace(/\D/g, '');
            
            // Format as (XXX) XXX-XXXX
            if (this.value.length > 3 && this.value.length <= 6) {
                this.value = `(${this.value.slice(0, 3)}) ${this.value.slice(3)}`;
            } else if (this.value.length > 6) {
                this.value = `(${this.value.slice(0, 3)}) ${this.value.slice(3, 6)}-${this.value.slice(6, 10)}`;
            }
        });
    }
    
    // Add custom validation for email
    const emailInput = document.getElementById('email');
    if (emailInput) {
        emailInput.addEventListener('blur', function() {
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (this.value && !emailRegex.test(this.value)) {
                this.setCustomValidity('Please enter a valid email address');
            } else {
                this.setCustomValidity('');
            }
        });
    }
}

// Handle section selection
function setupSectionSelection() {
    const sectionCards = document.querySelectorAll('.section-card');
    
    sectionCards.forEach(card => {
        card.addEventListener('click', function() {
            // Remove selected class from all cards
            sectionCards.forEach(c => c.classList.remove('selected'));
            
            // Add selected class to clicked card
            this.classList.add('selected');
            
            // Enable next button
            const nextButton = document.getElementById('nextToStep2');
            if (nextButton) {
                nextButton.disabled = false;
            }
            
            // Update summary
            updateSummary();
        });
    });
}

// Handle time slot selection
function setupTimeSlotSelection() {
    const timeSlotsContainer = document.getElementById('timeSlots');
    if (!timeSlotsContainer) return;
    
    // Delegate click events to time slots
    timeSlotsContainer.addEventListener('click', function(e) {
        const timeSlot = e.target.closest('.time-slot');
        if (!timeSlot) return;
        
        // Remove selected class from all time slots
        document.querySelectorAll('.time-slot').forEach(slot => {
            slot.classList.remove('selected');
        });
        
        // Add selected class to clicked time slot
        timeSlot.classList.add('selected');
        
        // Enable next button
        const nextButton = document.getElementById('nextToStep3');
        if (nextButton) {
            nextButton.disabled = false;
        }
        
        // Update summary
        updateSummary();
    });
    
    // Handle date change
    const dateInput = document.getElementById('reservationDate');
    const partySizeSelect = document.getElementById('partySize');
    
    if (dateInput && partySizeSelect) {
        const updateTimeSlots = debounce(function() {
            const date = dateInput.value;
            const partySize = partySizeSelect.value;
            
            if (!date) return;
            
            // Show loading state
            timeSlotsContainer.innerHTML = '<div class="text-center py-3"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div></div>';
            
            // In a real app, you would fetch available time slots from your API
            // For now, we'll simulate an API call with a delay
            setTimeout(() => {
                // This is just sample data - replace with actual API call
                const availableTimes = [
                    '11:00', '11:30', '12:00', '12:30', '13:00', '13:30', '14:00',
                    '18:00', '18:30', '19:00', '19:30', '20:00', '20:30', '21:00'
                ];
                
                // Randomly remove some time slots to simulate availability
                const filteredTimes = availableTimes.filter(() => Math.random() > 0.3);
                
                if (filteredTimes.length === 0) {
                    timeSlotsContainer.innerHTML = '<p class="text-muted">No available time slots for the selected date and party size. Please try another date.</p>';
                    return;
                }
                
                let timeSlotsHTML = '';
                filteredTimes.forEach(time => {
                    timeSlotsHTML += `<div class="time-slot" data-time="${time}">${time}</div>`;
                });
                
                timeSlotsContainer.innerHTML = timeSlotsHTML;
                
                // Update summary
                updateSummary();
            }, 800);
        }, 300);
        
        dateInput.addEventListener('change', updateTimeSlots);
        partySizeSelect.addEventListener('change', updateTimeSlots);
    }
}

// Handle form submission
function setupFormSubmission() {
    const form = document.querySelector('form');
    const confirmButton = document.getElementById('confirmBooking');
    
    if (!confirmButton) return;
    
    confirmButton.addEventListener('click', function(e) {
        e.preventDefault();
        
        // Validate form
        const fullName = document.getElementById('fullName').value.trim();
        const email = document.getElementById('email').value.trim();
        const phone = document.getElementById('phone').value.trim();
        const termsCheck = document.getElementById('termsCheck');
        
        // Basic validation
        if (!fullName || !email || !phone) {
            alert('Please fill in all required fields');
            return;
        }
        
        if (!termsCheck || !termsCheck.checked) {
            alert('Please agree to the terms and conditions');
            return;
        }
        
        // Get selected values
        const selectedSection = document.querySelector('.section-card.selected');
        const selectedDate = document.getElementById('reservationDate').value;
        const selectedTime = document.querySelector('.time-slot.selected')?.dataset.time;
        const partySize = document.getElementById('partySize').value;
        const specialRequests = document.getElementById('specialRequests').value.trim();
        
        if (!selectedSection || !selectedDate || !selectedTime) {
            alert('Please complete all reservation details');
            return;
        }
        
        // Prepare reservation data
        const reservationData = {
            section: selectedSection.dataset.section,
            date: selectedDate,
            time: selectedTime,
            partySize: parseInt(partySize),
            customerName: fullName,
            email: email,
            phone: phone,
            specialRequests: specialRequests
        };
        
        // Submit reservation
        submitReservation(reservationData);
    });
}

// Submit reservation to the server
function submitReservation(reservationData) {
    const submitBtn = document.getElementById('confirmBooking');
    const originalBtnText = submitBtn.innerHTML;
    
    // Show loading state
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';
    
    // In a real app, you would send this data to your API
    // For now, we'll simulate an API call with a delay
    setTimeout(() => {
        // Show success message
        const confirmation = document.getElementById('confirmation');
        const step3 = document.getElementById('step3');
        
        if (confirmation && step3) {
            // Hide the form and show confirmation
            step3.classList.add('d-none');
            
            // Format the reservation details for display
            const formattedDate = new Date(reservationData.date).toLocaleDateString('en-US', {
                weekday: 'long',
                year: 'numeric',
                month: 'long',
                day: 'numeric'
            });
            
            const sectionNames = {
                'lake-view': 'Lake View',
                'garden-view': 'Garden View',
                'indoors': 'Indoor Seating',
                'private': 'Private Room'
            };
            
            // Generate a random reservation number
            const reservationNumber = 'RS' + Math.floor(100000 + Math.random() * 900000);
            
            // Create the reservation details HTML
            const reservationDetails = `
                <div class="reservation-details">
                    <h5 class="mb-3">Reservation Confirmed!</h5>
                    <div class="card mb-3">
                        <div class="card-body">
                            <h6 class="card-subtitle mb-2 text-muted">Reservation #${reservationNumber}</h6>
                            <p class="card-text"><strong>Name:</strong> ${reservationData.customerName}</p>
                            <p class="card-text"><strong>Date & Time:</strong> ${formattedDate} at ${reservationData.time}</p>
                            <p class="card-text"><strong>Section:</strong> ${sectionNames[reservationData.section] || reservationData.section}</p>
                            <p class="card-text"><strong>Party Size:</strong> ${reservationData.partySize} ${reservationData.partySize === 1 ? 'person' : 'people'}</p>
                            ${reservationData.specialRequests ? `<p class="card-text"><strong>Special Requests:</strong> ${reservationData.specialRequests}</p>` : ''}
                        </div>
                    </div>
                    <p class="text-muted">A confirmation has been sent to <strong>${reservationData.email}</strong></p>
                    <div class="mt-4">
                        <a href="/" class="btn btn-primary me-2">Back to Home</a>
                        <a href="/book" class="btn btn-outline-secondary">Make Another Reservation</a>
                    </div>
                </div>
            `;
            
            // Update the confirmation section
            confirmation.innerHTML = reservationDetails;
            confirmation.classList.remove('d-none');
            
            // Scroll to top
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
        
        // Reset button state
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalBtnText;
        
        // In a real app, you would handle the API response here
        // For example:
        // fetch('/api/reservations', {
        //     method: 'POST',
        //     headers: {
        //         'Content-Type': 'application/json',
        //     },
        //     body: JSON.stringify(reservationData)
        // })
        // .then(response => response.json())
        // .then(data => {
        //     // Handle success
        //     showConfirmation(data);
        // })
        // .catch(error => {
        //     // Handle error
        //     console.error('Error:', error);
        //     alert('There was an error processing your reservation. Please try again.');
        //     submitBtn.disabled = false;
        //     submitBtn.innerHTML = originalBtnText;
        // });
        
    }, 1500);
}

// Setup navigation between steps
function setupNavigation() {
    // Step 1 to Step 2
    const nextToStep2 = document.getElementById('nextToStep2');
    if (nextToStep2) {
        nextToStep2.addEventListener('click', function(e) {
            e.preventDefault();
            navigateToStep(2);
        });
    }
    
    // Step 2 to Step 3
    const nextToStep3 = document.getElementById('nextToStep3');
    if (nextToStep3) {
        nextToStep3.addEventListener('click', function(e) {
            e.preventDefault();
            navigateToStep(3);
        });
    }
    
    // Back to Step 1
    const backToStep1 = document.getElementById('backToStep1');
    if (backToStep1) {
        backToStep1.addEventListener('click', function(e) {
            e.preventDefault();
            navigateToStep(1);
        });
    }
    
    // Back to Step 2
    const backToStep2 = document.getElementById('backToStep2');
    if (backToStep2) {
        backToStep2.addEventListener('click', function(e) {
            e.preventDefault();
            navigateToStep(2);
        });
    }
}

// Navigate between steps
function navigateToStep(step) {
    // Hide all steps
    document.querySelectorAll('[id^="step"]').forEach(stepEl => {
        stepEl.classList.add('d-none');
    });
    
    // Show the selected step
    const targetStep = document.getElementById(`step${step}`);
    if (targetStep) {
        targetStep.classList.remove('d-none');
    }
    
    // Update progress bar
    const progressBar = document.getElementById('progressBar');
    if (progressBar) {
        const progress = (step / 3) * 100;
        progressBar.style.width = `${progress}%`;
        progressBar.setAttribute('aria-valuenow', progress);
    }
    
    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Update reservation summary
function updateSummary() {
    const summaryText = document.getElementById('summaryText');
    if (!summaryText) return;
    
    const selectedSection = document.querySelector('.section-card.selected');
    const selectedDate = document.getElementById('reservationDate')?.value;
    const selectedTime = document.querySelector('.time-slot.selected')?.dataset.time;
    const partySize = document.getElementById('partySize')?.value;
    
    let summaryHTML = '';
    
    if (selectedSection) {
        const sectionName = selectedSection.querySelector('h4')?.textContent || 'Selected Section';
        summaryHTML += `<p><strong>Section:</strong> ${sectionName}</p>`;
    }
    
    if (selectedDate) {
        const dateObj = new Date(selectedDate);
        const formattedDate = dateObj.toLocaleDateString('en-US', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
        summaryHTML += `<p><strong>Date:</strong> ${formattedDate}</p>`;
    }
    
    if (selectedTime) {
        summaryHTML += `<p><strong>Time:</strong> ${selectedTime}</p>`;
    }
    
    if (partySize) {
        summaryHTML += `<p><strong>Party Size:</strong> ${partySize} ${partySize === '1' ? 'person' : 'people'}</p>`;
    }
    
    summaryText.innerHTML = summaryHTML || '<p class="text-muted">Your reservation details will appear here.</p>';
}

// Debounce function to limit how often a function can be called
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Initialize the application when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Any additional initialization code can go here
    console.log('Restaurant booking system initialized');
});
