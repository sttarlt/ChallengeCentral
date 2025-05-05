document.addEventListener('DOMContentLoaded', function() {
    // Handle reward redemption confirmation
    const redeemButtons = document.querySelectorAll('.redeem-button');
    
    redeemButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            const rewardName = this.getAttribute('data-reward-name');
            const pointsCost = this.getAttribute('data-points-cost');
            const userPoints = this.getAttribute('data-user-points');
            
            if (parseInt(userPoints) < parseInt(pointsCost)) {
                e.preventDefault();
                
                // Show insufficient points modal
                const insufficientModal = new bootstrap.Modal(document.getElementById('insufficient-points-modal'));
                const modalBody = document.querySelector('#insufficient-points-modal .modal-body');
                modalBody.textContent = `عذراً، لا تملك نقاط كافية لاستبدال ${rewardName}. أنت تحتاج ${pointsCost} نقطة وتملك حالياً ${userPoints} نقطة فقط.`;
                
                insufficientModal.show();
            } else {
                // Show confirmation modal
                e.preventDefault();
                
                const confirmModal = new bootstrap.Modal(document.getElementById('confirm-redemption-modal'));
                
                // Update modal content
                document.getElementById('reward-name').textContent = rewardName;
                document.getElementById('points-cost').textContent = pointsCost;
                document.getElementById('remaining-points').textContent = parseInt(userPoints) - parseInt(pointsCost);
                
                // Set the form action to the correct URL
                const rewardId = this.getAttribute('data-reward-id');
                document.getElementById('redemption-form').setAttribute('action', `/rewards/redeem/${rewardId}`);
                
                confirmModal.show();
            }
        });
    });
    
    // Animate reward cards on hover
    const rewardCards = document.querySelectorAll('.card-reward');
    
    rewardCards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-10px)';
            this.style.boxShadow = '0 15px 25px rgba(0, 0, 0, 0.15)';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
            this.style.boxShadow = '0 5px 15px rgba(0, 0, 0, 0.08)';
        });
    });
    
    // Search and filter rewards
    const searchInput = document.getElementById('reward-search');
    const filterSelect = document.getElementById('reward-filter');
    
    if (searchInput && filterSelect) {
        const filterRewards = () => {
            const searchTerm = searchInput.value.toLowerCase();
            const filterValue = filterSelect.value;
            
            rewardCards.forEach(card => {
                const rewardName = card.querySelector('.card-title').textContent.toLowerCase();
                const rewardPoints = parseInt(card.getAttribute('data-points'));
                
                let showCard = rewardName.includes(searchTerm);
                
                if (filterValue === 'low-to-high') {
                    // Already sorted in the DOM
                    // No additional filtering needed
                } else if (filterValue === 'high-to-low') {
                    // Already sorted in the DOM
                    // No additional filtering needed
                } else if (filterValue === 'affordable') {
                    const userPoints = parseInt(searchInput.getAttribute('data-user-points') || 0);
                    showCard = showCard && (rewardPoints <= userPoints);
                }
                
                card.style.display = showCard ? 'block' : 'none';
            });
        };
        
        searchInput.addEventListener('input', filterRewards);
        filterSelect.addEventListener('change', filterRewards);
    }
});
