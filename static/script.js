// ===== CLEVER SHOP - Premium JavaScript v4 =====

// Safe localStorage wrapper
const storage = {
    isAvailable: (function() {
        try {
            const test = '__storage_test__';
            localStorage.setItem(test, test);
            localStorage.removeItem(test);
            return true;
        } catch(e) {
            return false;
        }
    })(),
    
    getItem: function(key) {
        if (!this.isAvailable) return null;
        try {
            return localStorage.getItem(key);
        } catch(e) {
            console.error('localStorage getItem error:', e);
            return null;
        }
    },
    
    setItem: function(key, value) {
        if (!this.isAvailable) return false;
        try {
            localStorage.setItem(key, value);
            return true;
        } catch(e) {
            console.error('localStorage setItem error:', e);
            return false;
        }
    },
    
    removeItem: function(key) {
        if (!this.isAvailable) return false;
        try {
            localStorage.removeItem(key);
            return true;
        } catch(e) {
            console.error('localStorage removeItem error:', e);
            return false;
        }
    }
};

// Cart & Wishlist State
let cart = [];
let wishlist = [];
try {
    cart = JSON.parse(storage.getItem('cart')) || [];
} catch(e) { cart = []; storage.removeItem('cart'); }
try {
    wishlist = JSON.parse(storage.getItem('wishlist')) || [];
} catch(e) { wishlist = []; storage.removeItem('wishlist'); }

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    updateCartCount();
    updateWishlistCount();
    initWishlistButtons();
    initScrollEffects();
    initToastContainer();
});

// ===== CART FUNCTIONS =====
function updateCartCount() {
    const count = cart.reduce((sum, item) => sum + (item.quantity || 1), 0);
    const countEl = document.getElementById('cart-count');
    const countTopEl = document.getElementById('cart-count-top');
    
    if (countEl) countEl.textContent = count;
    if (countTopEl) {
        countTopEl.textContent = count;
        countTopEl.style.display = count > 0 ? 'flex' : 'none';
    }
}

function addToCart(btn) {
    const id = btn.dataset.id;
    const name = btn.dataset.pname;
    const price = parseFloat(btn.dataset.pprice);
    const brand = btn.dataset.brand || '';

    // Get sizes from the product card
    const card = btn.closest('.product-card');
    const sizesRaw = card ? card.dataset.sizes : '';

    // Parse sizes (supports "XS,S,M" and "XS:1,S:0,M:1" formats)
    const sizes = sizesRaw ? sizesRaw.split(',').map(s => {
        s = s.trim();
        if (s.includes(':')) {
            const [size, stock] = s.split(':');
            return { size: size.trim(), inStock: stock.trim() === '1' };
        }
        return { size: s, inStock: true };
    }).filter(s => s.size) : [];

    const availableSizes = sizes.filter(s => s.inStock);

    // If no sizes defined or only one available — add directly
    if (availableSizes.length === 0) {
        _doAddToCart({ id, name, price, size: '', quantity: 1 }, btn, brand);
        return;
    }
    if (availableSizes.length === 1) {
        _doAddToCart({ id, name, price, size: availableSizes[0].size, quantity: 1 }, btn, brand);
        return;
    }

    // Open size picker modal
    openSizePicker({ id, name, price, brand }, sizes, btn);
}

let _sizePickerData = null;
let _sizePickerBtn = null;

function openSizePicker(productData, sizes, triggerBtn) {
    _sizePickerData = productData;
    _sizePickerBtn = triggerBtn;

    document.getElementById('size-picker-name').textContent = productData.name;

    const container = document.getElementById('size-picker-options');
    container.innerHTML = sizes.map(s => `
        <button type="button"
            class="size-btn${!s.inStock ? ' size-unavailable' : ''}"
            onclick="${s.inStock ? 'selectSizePicker(this)' : 'void(0)'}"
            ${!s.inStock ? 'title="Немає в наявності"' : ''}>
            ${s.size}
        </button>
    `).join('');

    const modal = document.getElementById('size-picker-modal');
    modal.style.display = 'block';
    document.body.style.overflow = 'hidden';
}

function selectSizePicker(btn) {
    document.querySelectorAll('#size-picker-options .size-btn').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
}

function closeSizePicker() {
    document.getElementById('size-picker-modal').style.display = 'none';
    document.body.style.overflow = '';
    _sizePickerData = null;
    _sizePickerBtn = null;
}

function confirmSizePicker() {
    const selected = document.querySelector('#size-picker-options .size-btn.selected');
    if (!selected) {
        showToast('Оберіть розмір', 'error');
        return;
    }
    const size = selected.textContent.trim();
    closeSizePicker();
    _doAddToCart({ ..._sizePickerData, size, quantity: 1 }, _sizePickerBtn, _sizePickerData?.brand || '');
}

function _doAddToCart(item, btn, brand) {
    const existingIndex = cart.findIndex(i => i.id === item.id && i.size === item.size);
    if (existingIndex > -1) {
        cart[existingIndex].quantity++;
    } else {
        cart.push(item);
    }

    storage.setItem('cart', JSON.stringify(cart));
    updateCartCount();

    if (typeof gtag !== 'undefined') trackAddToCart(item.id, item.name, item.price, brand);
    if (typeof fbq !== 'undefined') trackFBAddToCart(item.price);

    // Fly animation toward cart icon
    var prefersReduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var cartBadge = document.getElementById('cart-count-top');

    if (!prefersReduced && btn) {
        var card = btn.closest('.product-card') || btn.closest('.product-gallery');
        var imgEl = card ? (card.querySelector('.product-image img') || card.querySelector('img')) : null;
        var cartTarget = cartBadge || document.querySelector('.header-btn[aria-label="Кошик"]');

        if (imgEl && cartTarget) {
            var imgRect = imgEl.getBoundingClientRect();
            var cartRect = cartTarget.getBoundingClientRect();
            var flyImg = document.createElement('img');
            flyImg.src = imgEl.src;
            flyImg.className = 'cart-fly-img';
            flyImg.style.left = imgRect.left + imgRect.width / 2 - 30 + 'px';
            flyImg.style.top = imgRect.top + imgRect.height / 2 - 30 + 'px';
            flyImg.style.opacity = '1';
            document.body.appendChild(flyImg);

            var dx = cartRect.left + cartRect.width / 2 - 30 - parseFloat(flyImg.style.left);
            var dy = cartRect.top + cartRect.height / 2 - 30 - parseFloat(flyImg.style.top);

            requestAnimationFrame(function() {
                flyImg.style.transform = 'translate(' + dx + 'px, ' + dy + 'px) scale(0.2)';
                flyImg.style.opacity = '0.3';
            });

            flyImg.addEventListener('transitionend', function handler() {
                flyImg.removeEventListener('transitionend', handler);
                flyImg.remove();
                if (cartBadge) {
                    cartBadge.classList.remove('cart-badge-bounce');
                    void cartBadge.offsetWidth;
                    cartBadge.classList.add('cart-badge-bounce');
                }
            });

            // Safety cleanup
            setTimeout(function() { if (flyImg.parentNode) flyImg.remove(); }, 700);
        }
    } else if (cartBadge) {
        // Reduced motion: simple fade on badge
        cartBadge.classList.remove('cart-badge-fade');
        void cartBadge.offsetWidth;
        cartBadge.classList.add('cart-badge-fade');
    }

    if (btn) {
        const originalText = btn.innerHTML;
        btn.innerHTML = '✓ Додано';
        btn.style.background = 'linear-gradient(135deg, #059669 0%, #047857 100%)';
        btn.style.transform = 'scale(1.05)';
        setTimeout(() => {
            btn.innerHTML = originalText;
            btn.style.background = '';
            btn.style.transform = '';
        }, 1500);
    }

    showToast('Товар додано в кошик', 'success');
}

function openCart() {
    const modal = document.getElementById('cart-modal');
    const itemsContainer = document.getElementById('cart-items');
    const totalEl = document.getElementById('cart-total');
    
    if (cart.length === 0) {
        itemsContainer.innerHTML = `
            <div class="cart-empty">
                <div class="cart-empty-icon">🛒</div>
                <p style="font-size:1.1rem;color:var(--gray-500);margin-bottom:0.5rem;">Кошик порожній</p>
                <p style="font-size:0.9rem;color:var(--gray-400);margin-bottom:1.5rem;">Додайте товари з каталогу</p>
                <a href="/#products" onclick="closeCart()" class="btn btn-primary" style="text-decoration:none;">🛍️ Перейти до каталогу</a>
            </div>`;
        totalEl.textContent = '0';
    } else {
        let html = '';
        let total = 0;
        
        cart.forEach((item, index) => {
            const itemTotal = item.price * item.quantity;
            total += itemTotal;
            html += `
                <div class="cart-item" style="animation: fadeIn 0.3s ease ${index * 0.1}s both;">
                    <div class="cart-item-info">
                        <h4>${item.name}</h4>
                        <p>${item.size ? 'Розмір: ' + item.size + ' · ' : ''}Кількість: ${item.quantity}</p>
                    </div>
                    <div class="cart-item-price">${itemTotal.toLocaleString('uk-UA')} грн</div>
                    <button class="cart-item-remove" onclick="removeFromCart(${index})" aria-label="Видалити">✕</button>
                </div>
            `;
        });
        
        // Free shipping hint
        if (total < 5000) {
            html += '<div style="padding:0.75rem 1rem;background:var(--primary-50,#ECFDF5);border-radius:8px;margin-top:0.75rem;font-size:0.85rem;color:var(--primary-dark,#059669);text-align:center;">🚚 До безкоштовної доставки залишилось <strong>' + (5000 - total).toLocaleString('uk-UA') + ' грн</strong></div>';
        } else {
            html += '<div style="padding:0.75rem 1rem;background:var(--primary-50,#ECFDF5);border-radius:8px;margin-top:0.75rem;font-size:0.85rem;color:var(--primary-dark,#059669);text-align:center;">✅ Безкоштовна доставка!</div>';
        }
        
        itemsContainer.innerHTML = html;
        totalEl.textContent = total.toLocaleString('uk-UA');
    }
    
    modal.style.display = 'block';
    document.body.style.overflow = 'hidden';
}

function closeCart() {
    document.getElementById('cart-modal').style.display = 'none';
    document.body.style.overflow = '';
}

function removeFromCart(index) {
    const item = cart[index];
    cart.splice(index, 1);
    storage.setItem('cart', JSON.stringify(cart));
    updateCartCount();
    showToast('Товар видалено з кошика', 'success');
    openCart();
}

function goToCheckout() {
    if (cart.length === 0) {
        showToast('Кошик порожній', 'error');
        return;
    }
    closeCart();
    window.location.href = '/checkout';
}

// ===== WISHLIST FUNCTIONS =====
function updateWishlistCount() {
    const count = wishlist.length;
    const countEl = document.getElementById('wish-count');
    if (countEl) {
        countEl.textContent = count;
        countEl.style.display = count > 0 ? 'flex' : 'none';
    }
}

function initWishlistButtons() {
    document.querySelectorAll('.wishlist-btn').forEach(btn => {
        const card = btn.closest('.product-card');
        if (card) {
            const id = card.querySelector('[data-id]')?.dataset.id;
            if (id && wishlist.includes(parseInt(id))) {
                btn.classList.add('active');
                btn.textContent = '♥';
            }
        }
    });
}

function toggleWishlist(btn, id) {
    const index = wishlist.indexOf(id);
    if (index > -1) {
        wishlist.splice(index, 1);
        btn.classList.remove('active');
        btn.textContent = '♡';
        showToast('Видалено зі списку бажань', 'success');
    } else {
        wishlist.push(id);
        btn.classList.add('active');
        btn.textContent = '♥';
        btn.style.transform = 'scale(1.3)';
        setTimeout(() => btn.style.transform = '', 300);
        showToast('Додано до списку бажань', 'success');
    }
    storage.setItem('wishlist', JSON.stringify(wishlist));
    updateWishlistCount();
}

// ===== PRODUCT PAGE FUNCTIONS =====
function selectSize(btn) {
    if (btn.classList.contains('size-unavailable')) return;
    document.querySelectorAll('.size-btn').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    const statusEl = document.getElementById('size-stock-status');
    if (statusEl) {
        statusEl.innerHTML = '<span style="color:var(--success,#10b981);">● В наявності</span>';
    }
}

function changeQuantity(delta) {
    const input = document.getElementById('qty-input');
    let val = parseInt(input.value) || 1;
    val = Math.max(1, Math.min(99, val + delta));
    input.value = val;
}

function addToCartWithSize() {
    const selectedSize = document.querySelector('.size-btn.selected');
    if (!selectedSize) {
        showToast('Будь ласка, оберіть розмір', 'error');
        return;
    }
    
    const btn = document.querySelector('.add-to-cart-btn');
    const qty = parseInt(document.getElementById('qty-input')?.value) || 1;
    
    const item = {
        id: btn.dataset.id,
        name: btn.dataset.pname,
        price: parseFloat(btn.dataset.pprice),
        size: selectedSize.textContent,
        quantity: qty
    };
    
    const existingIndex = cart.findIndex(i => i.id === item.id && i.size === item.size);
    if (existingIndex > -1) {
        cart[existingIndex].quantity += qty;
    } else {
        cart.push(item);
    }
    
    storage.setItem('cart', JSON.stringify(cart));
    updateCartCount();
    
    const originalText = btn.innerHTML;
    btn.innerHTML = '✓ Додано в кошик';
    btn.style.background = 'linear-gradient(135deg, #059669 0%, #047857 100%)';
    
    showToast(`${item.name} додано в кошик`, 'success');
    
    setTimeout(() => {
        btn.innerHTML = originalText;
        btn.style.background = '';
    }, 2000);
}

function buyNow() {
    const selectedSize = document.querySelector('.size-btn.selected');
    if (!selectedSize) {
        showToast('Будь ласка, оберіть розмір', 'error');
        return;
    }
    
    addToCartWithSize();
    setTimeout(() => window.location.href = '/checkout', 300);
}

// ===== PHOTO MODAL =====
let _photoModalImages = [];
let _photoModalIndex = 0;
let _photoZoomLevel = 1;

function openPhotoModal(src) {
    // Collect all gallery images
    const thumbs = document.querySelectorAll('.gallery-thumb img');
    if (thumbs.length > 0) {
        _photoModalImages = Array.from(thumbs).map(img => img.src);
    } else {
        _photoModalImages = [src];
    }
    _photoModalIndex = _photoModalImages.indexOf(src);
    if (_photoModalIndex < 0) _photoModalIndex = 0;
    _photoZoomLevel = 1;

    const modal = document.getElementById('photo-modal');
    const img = document.getElementById('modal-photo');
    img.style.transform = 'scale(1)';
    img.style.cursor = 'zoom-in';
    img.src = _photoModalImages[_photoModalIndex];
    modal.style.display = 'flex';
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
    _updatePhotoArrows();
}

function closePhotoModal() {
    const modal = document.getElementById('photo-modal');
    modal.classList.remove('active');
    modal.style.display = 'none';
    document.body.style.overflow = '';
    document.body.style.position = '';
    document.body.style.width = '';
    _photoZoomLevel = 1;
    document.getElementById('modal-photo').style.transform = 'scale(1)';
}

function photoModalNav(dir) {
    _photoModalIndex = (_photoModalIndex + dir + _photoModalImages.length) % _photoModalImages.length;
    _photoZoomLevel = 1;
    const img = document.getElementById('modal-photo');
    img.style.opacity = '0';
    img.style.transform = 'scale(1)';
    setTimeout(() => {
        img.src = _photoModalImages[_photoModalIndex];
        img.style.opacity = '1';
    }, 150);
    _updatePhotoArrows();
}

function _updatePhotoArrows() {
    const prev = document.querySelector('.photo-modal-prev');
    const next = document.querySelector('.photo-modal-next');
    if (!prev || !next) return;
    const show = _photoModalImages.length > 1;
    prev.style.display = show ? 'flex' : 'none';
    next.style.display = show ? 'flex' : 'none';
}

function photoZoom(factor) {
    _photoZoomLevel = Math.min(4, Math.max(1, _photoZoomLevel * factor));
    const img = document.getElementById('modal-photo');
    img.style.transform = `scale(${_photoZoomLevel})`;
    img.style.cursor = _photoZoomLevel > 1 ? 'zoom-out' : 'zoom-in';
}

function photoZoomReset() {
    _photoZoomLevel = 1;
    const img = document.getElementById('modal-photo');
    img.style.transform = 'scale(1)';
    img.style.cursor = 'zoom-in';
}

// Click on image to toggle zoom
document.addEventListener('click', function(e) {
    if (e.target.id === 'modal-photo') {
        if (_photoZoomLevel > 1) photoZoomReset();
        else photoZoom(2);
    }
});

// Swipe support for photo modal
(function() {
    let touchStartX = 0;
    document.addEventListener('touchstart', e => {
        if (document.getElementById('photo-modal')?.classList.contains('active'))
            touchStartX = e.touches[0].clientX;
    }, { passive: true });
    document.addEventListener('touchend', e => {
        if (!document.getElementById('photo-modal')?.classList.contains('active')) return;
        const diff = touchStartX - e.changedTouches[0].clientX;
        if (Math.abs(diff) > 50) photoModalNav(diff > 0 ? 1 : -1);
    }, { passive: true });
})();

function changeMainImage(src, thumb) {
    const mainImg = document.getElementById('main-product-image');
    mainImg.style.opacity = '0';
    setTimeout(() => {
        mainImg.src = src;
        mainImg.style.opacity = '1';
    }, 150);
    document.querySelectorAll('.gallery-thumb').forEach(t => t.classList.remove('active'));
    thumb.classList.add('active');
}

// Gallery arrow navigation
var _galleryIndex = 0;
function galleryNav(direction) {
    var thumbs = document.querySelectorAll('.gallery-thumb');
    if (!thumbs.length) return;
    _galleryIndex += direction;
    if (_galleryIndex < 0) _galleryIndex = thumbs.length - 1;
    if (_galleryIndex >= thumbs.length) _galleryIndex = 0;
    thumbs[_galleryIndex].click();
}

// ===== CHECKOUT FUNCTIONS =====
function loadCheckoutCart() {
    const container = document.getElementById('checkout-items');
    const totalEl = document.getElementById('checkout-total');
    
    if (!container) return;
    
    if (cart.length === 0) {
        container.innerHTML = '<p style="text-align:center;color:var(--gray-500);padding:2rem;">Кошик порожній</p>';
        if (totalEl) totalEl.textContent = '0';
        return;
    }
    
    let html = '';
    let total = 0;
    
    cart.forEach(item => {
        const itemTotal = item.price * item.quantity;
        total += itemTotal;
        html += `
            <div class="summary-item">
                <div>
                    <div class="item-name">${item.name}</div>
                    <div class="item-details">${item.size ? 'Розмір: ' + item.size + ' • ' : ''}×${item.quantity}</div>
                </div>
                <div class="item-price">${itemTotal.toLocaleString('uk-UA')} грн</div>
            </div>
        `;
    });
    
    container.innerHTML = html;
    if (totalEl) totalEl.textContent = total.toLocaleString('uk-UA');
}

function submitOrder(event) {
    event.preventDefault();
    
    const form = event.target;
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;
    
    submitBtn.innerHTML = '<span class="loader-spinner" style="width:20px;height:20px;border-width:2px;"></span> Обробка...';
    submitBtn.disabled = true;
    
    const name = form.querySelector('[name="name"]').value;
    const phone = form.querySelector('[name="phone"]').value;
    const email = form.querySelector('[name="email"]')?.value || '';
    const city = form.querySelector('[name="city"]')?.value || '';
    const warehouse = form.querySelector('[name="warehouse"]')?.value || '';
    
    const delivery = city + (warehouse ? ', ' + warehouse : '');
    const total = cart.reduce((sum, item) => sum + item.price * item.quantity, 0);
    
    fetch('/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, phone, email, delivery, items: cart, total })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            cart = [];
            storage.setItem('cart', JSON.stringify(cart));
            window.location.href = '/thank-you/' + data.order_id;
        } else {
            showToast('Помилка при оформленні замовлення', 'error');
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        }
    })
    .catch(err => {
        showToast('Помилка: ' + err.message, 'error');
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
    });
}

// Initialize checkout
if (window.location.pathname === '/checkout') {
    document.addEventListener('DOMContentLoaded', loadCheckoutCart);
}

// ===== SCROLL EFFECTS =====
function initScrollEffects() {
    // Header scroll effect
    const header = document.querySelector('header');
    let ticking = false;
    
    window.addEventListener('scroll', () => {
        if (!ticking) {
            requestAnimationFrame(() => {
                const currentScroll = window.scrollY;
                
                if (header) {
                    header.classList.toggle('scrolled', currentScroll > 50);
                }
                
                // Scroll to top button
                const scrollBtn = document.getElementById('scroll-top');
                if (scrollBtn) {
                    scrollBtn.classList.toggle('visible', currentScroll > 500);
                }
                
                ticking = false;
            });
            ticking = true;
        }
    }, { passive: true });
    
    // Scroll animations
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
            }
        });
    }, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });
    
    document.querySelectorAll('.animate-on-scroll').forEach(el => observer.observe(el));
}

// ===== TOAST NOTIFICATIONS =====
function initToastContainer() {
    if (!document.querySelector('.toast-container')) {
        const container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
}

function showToast(message, type = 'success') {
    const container = document.querySelector('.toast-container');
    if (!container) return;
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${type === 'success' ? '✓' : '⚠'}</span>
        <span class="toast-message">${message}</span>
        <button class="toast-close" onclick="this.parentElement.remove()">×</button>
    `;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ===== MODAL CLOSE ON OUTSIDE CLICK =====
window.addEventListener('click', function(event) {
    const cartModal = document.getElementById('cart-modal');
    const photoModal = document.getElementById('photo-modal');
    const sizeModal = document.getElementById('size-picker-modal');
    
    if (event.target === cartModal) closeCart();
    if (event.target === sizeModal) closeSizePicker();
    if (event.target === photoModal) closePhotoModal();
});

// Close modals on Escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeCart();
        closeSizePicker();
        const photoModal = document.getElementById('photo-modal');
        if (photoModal && photoModal.classList.contains('active')) closePhotoModal();
    }
    if (e.key === 'ArrowLeft' && document.getElementById('photo-modal')?.classList.contains('active')) photoModalNav(-1);
    if (e.key === 'ArrowRight' && document.getElementById('photo-modal')?.classList.contains('active')) photoModalNav(1);
});


// ===== RECENTLY VIEWED PRODUCTS =====
const MAX_RECENTLY_VIEWED = 8;

function getRecentlyViewed() {
    return JSON.parse(storage.getItem('recentlyViewed')) || [];
}

function addToRecentlyViewed(product) {
    if (!product || !product.id) return;
    
    let viewed = getRecentlyViewed();
    
    // Remove if already exists
    viewed = viewed.filter(p => p.id !== product.id);
    
    // Add to beginning
    viewed.unshift(product);
    
    // Keep only last N items
    viewed = viewed.slice(0, MAX_RECENTLY_VIEWED);
    
    storage.setItem('recentlyViewed', JSON.stringify(viewed));
}

function renderRecentlyViewed(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    const viewed = getRecentlyViewed();
    
    if (viewed.length === 0) {
        container.style.display = 'none';
        return;
    }
    
    container.style.display = 'block';
    const grid = container.querySelector('.recently-viewed-grid');
    if (!grid) return;
    
    grid.innerHTML = viewed.map(p => `
        <div class="recently-viewed-item" onclick="window.location='/product/${p.id}'">
            <div class="rv-image">
                ${p.image ? `<img src="${p.image}" alt="${p.name}" loading="lazy">` : '<div class="no-image" style="height:100%;">📷</div>'}
            </div>
            <div class="rv-info">
                <h4>${p.name}</h4>
                <p class="rv-brand">${p.brand || ''}</p>
                <p class="rv-price">${p.price ? p.price.toLocaleString('uk-UA') + ' грн' : ''}</p>
            </div>
        </div>
    `).join('');
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    renderRecentlyViewed('recently-viewed-section');
});

// ===== Task 3.1: Spoiler Block Toggle =====
function initSpoilerBlocks() {
    var toggles = document.querySelectorAll('.spoiler-block-toggle');
    toggles.forEach(function(btn) {
        btn.addEventListener('click', function() {
            var content = btn.previousElementSibling;
            if (!content || !content.classList.contains('spoiler-block-content')) return;

            var isExpanded = content.classList.contains('expanded');
            if (isExpanded) {
                content.classList.remove('expanded');
                btn.textContent = 'Читати далі ▼';
                btn.setAttribute('aria-expanded', 'false');
                // Scroll back to the section so user sees the collapsed state
                var block = btn.closest('.spoiler-block');
                if (block) {
                    block.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            } else {
                content.classList.add('expanded');
                btn.textContent = 'Згорнути ▲';
                btn.setAttribute('aria-expanded', 'true');
            }
        });
    });
}

document.addEventListener('DOMContentLoaded', function() {
    initSpoilerBlocks();
});

// ===== Task 5.4: Hover Gallery (Second Image on Hover) =====
function initHoverGallery() {
    // Respect prefers-reduced-motion
    var prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    // Only apply on desktop (non-touch devices)
    var isTouchDevice = window.matchMedia('(hover: none)').matches;
    if (isTouchDevice) return;

    var cards = document.querySelectorAll('.product-card[data-images]');
    if (!cards.length) return;

    // Use IntersectionObserver to preload second image when card enters viewport
    var observer = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
            if (!entry.isIntersecting) return;

            var card = entry.target;
            var imagesStr = card.getAttribute('data-images');
            if (!imagesStr) return;

            var images = imagesStr.split(',').map(function(s) { return s.trim(); }).filter(Boolean);
            if (images.length < 2) return;

            // Preload the second image
            var preloadImg = new Image();
            preloadImg.src = images[1];

            // Store images data on the card element
            card._hoverImages = images;
            card._hoverPreloaded = true;

            // Stop observing once preloaded
            observer.unobserve(card);
        });
    }, { rootMargin: '200px 0px' });

    cards.forEach(function(card) {
        var imagesStr = card.getAttribute('data-images');
        if (!imagesStr) return;
        var images = imagesStr.split(',').map(function(s) { return s.trim(); }).filter(Boolean);
        if (images.length < 2) return;

        // Observe for preloading
        observer.observe(card);

        // Set up hover gallery container
        var imgWrap = card.querySelector('.product-image-wrap');
        if (!imgWrap) return;

        var primaryImg = imgWrap.querySelector('img');
        if (!primaryImg) return;

        // Create hover overlay image
        var hoverImg = document.createElement('img');
        hoverImg.className = 'hover-gallery-img';
        hoverImg.alt = primaryImg.alt || '';
        hoverImg.loading = 'lazy';
        hoverImg.src = images[1];
        hoverImg.setAttribute('aria-hidden', 'true');
        imgWrap.appendChild(hoverImg);

        // Add hover class to wrap for CSS targeting
        imgWrap.classList.add('has-hover-gallery');

        // Mouse events
        card.addEventListener('mouseenter', function() {
            if (!card._hoverPreloaded && !card._hoverImages) return;
            if (prefersReducedMotion) {
                hoverImg.style.transition = 'none';
            }
            hoverImg.classList.add('visible');
        });

        card.addEventListener('mouseleave', function() {
            if (prefersReducedMotion) {
                hoverImg.style.transition = 'none';
            }
            hoverImg.classList.remove('visible');
        });
    });
}

document.addEventListener('DOMContentLoaded', function() {
    initHoverGallery();
});
