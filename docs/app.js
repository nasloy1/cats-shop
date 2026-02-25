'use strict';

// ============================================================
//  КОНФИГУРАЦИЯ API
//  После того как Railway даст публичный URL — вставьте его сюда
//  Пример: 'https://cats-shop-production-xxxx.up.railway.app'
// ============================================================
const BOT_API_URL = 'https://cats-shop-production.up.railway.app';
const API_SECRET  = 'cats-shop-secret2026';  // ← Должен совпадать с API_SECRET в Railway

// ============================================================
//  CATALOG DATA — загружается из API бота
// ============================================================
let CATS = [];

async function loadCats() {
  if (!BOT_API_URL) return;
  const grid = document.getElementById('catalog-grid');
  try {
    const resp = await fetch(BOT_API_URL + '/cats');
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    CATS = await resp.json();
  } catch (err) {
    console.error('[loadCats]', err);
    if (grid) {
      grid.innerHTML = `
        <div class="no-results">
          <div class="no-results-emoji">😿</div>
          <h3>Не удалось загрузить каталог</h3>
          <p>Проверьте подключение и попробуйте снова</p>
          <button class="btn-primary" style="max-width:200px;margin-top:12px" onclick="retryLoadCats()">
            Повторить
          </button>
        </div>`;
    }
  }
}

async function retryLoadCats() {
  const grid = document.getElementById('catalog-grid');
  if (grid) {
    grid.innerHTML = '<div class="no-results"><div class="no-results-emoji">⏳</div><p>Загрузка...</p></div>';
  }
  await loadCats();
  renderCatalog();
}

// ============================================================
//  STATE
// ============================================================
const state = {
  page: 'catalog',
  prevPage: null,
  cart: [],
  category: 'all',
  search: '',
  detailCatId: null,
};

// ============================================================
//  INIT
// ============================================================
document.addEventListener('DOMContentLoaded', async () => {
  // Restore cart from localStorage
  try {
    const saved = localStorage.getItem('tg_cats_cart');
    if (saved) state.cart = JSON.parse(saved);
  } catch (_) {
    state.cart = [];
  }

  // Telegram WebApp setup
  const tg = window.Telegram?.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
    tg.BackButton.onClick(goBack);
  }

  // Show loading while fetching catalog
  const grid = document.getElementById('catalog-grid');
  if (grid) {
    grid.innerHTML = '<div class="no-results"><div class="no-results-emoji">⏳</div><p>Загрузка каталога...</p></div>';
  }

  await loadCats();
  renderCatalog();
  updateCartBadge();
});

// ============================================================
//  NAVIGATION
// ============================================================
const PAGE_TITLES = {
  catalog:  '🐱 Питомник котов',
  detail:   'Карточка кота',
  cart:     '🛒 Корзина',
  order:    '📦 Оформление заказа',
  feedback: '💬 Обратная связь',
  about:    'ℹ️ О нас',
};

function navigate(page, data) {
  if (page === state.page) return;

  // Hide current page
  const curr = document.getElementById('page-' + state.page);
  if (curr) curr.classList.remove('active');

  // Update nav highlights
  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.page === page);
  });

  // Track history for Back button
  state.prevPage = state.page;
  state.page = page;

  // Back button visibility
  const showBack = page === 'detail' || page === 'order';
  const tg = window.Telegram?.WebApp;
  if (tg) showBack ? tg.BackButton.show() : tg.BackButton.hide();
  document.getElementById('btn-back').classList.toggle('hidden', !showBack);

  // Show new page
  const next = document.getElementById('page-' + page);
  if (next) {
    next.classList.add('active');
    next.scrollTop = 0;
  }

  // Update title
  if (page === 'detail') {
    const cat = CATS.find(c => c.id === data);
    document.getElementById('header-title').textContent = cat ? cat.name : 'Кот';
  } else {
    document.getElementById('header-title').textContent = PAGE_TITLES[page] || '';
  }

  // Render page
  switch (page) {
    case 'catalog':  renderCatalog(); break;
    case 'detail':   state.detailCatId = data; renderDetail(data); break;
    case 'cart':     renderCart(); break;
    case 'order':    renderOrderForm(); break;
  }
}

function goBack() {
  navigate(state.prevPage || 'catalog');
}

// ============================================================
//  CATALOG
// ============================================================
function renderCatalog() {
  const cats = getFilteredCats();
  const grid = document.getElementById('catalog-grid');

  if (!cats.length) {
    grid.innerHTML = `
      <div class="no-results">
        <div class="no-results-emoji">🔍</div>
        <h3>Ничего не найдено</h3>
        <p>Попробуйте изменить фильтры или поисковый запрос</p>
      </div>`;
    return;
  }

  grid.innerHTML = cats.map(cat => `
    <div class="cat-card" onclick="navigate('detail', ${cat.id})">
      ${!cat.available ? '<div class="sold-overlay"><div class="sold-label">Продан</div></div>' : ''}
      <img
        class="cat-card-img"
        src="${cat.image}"
        alt="${cat.name}"
        loading="lazy"
        onerror="this.outerHTML='<div class=\\'cat-img-placeholder\\'>🐱</div>'"
      >
      <div class="cat-card-body">
        <div class="cat-avail-badge ${cat.available ? 'available' : 'sold'}">
          ${cat.available ? '✓ Доступен' : '✗ Продан'}
        </div>
        <div class="cat-card-name">${cat.name}</div>
        <div class="cat-card-breed">${cat.breed}</div>
        <div class="cat-card-footer">
          <div class="cat-card-price">${formatPrice(cat.price)}</div>
          <div class="cat-card-gender">${cat.gender === 'male' ? '♂' : '♀'}</div>
        </div>
      </div>
    </div>
  `).join('');
}

function getFilteredCats() {
  const q = state.search.toLowerCase();
  return CATS.filter(cat => {
    const catMatch = state.category === 'all' || cat.category === state.category;
    const searchMatch = !q
      || cat.name.toLowerCase().includes(q)
      || cat.breed.toLowerCase().includes(q)
      || cat.color.toLowerCase().includes(q);
    return catMatch && searchMatch;
  });
}

function setCategory(cat, btn) {
  state.category = cat;
  document.querySelectorAll('.chip').forEach(el => el.classList.remove('active'));
  btn.classList.add('active');
  renderCatalog();
}

function handleSearch(value) {
  state.search = value;
  const clearBtn = document.getElementById('search-clear');
  if (clearBtn) clearBtn.classList.toggle('hidden', !value);
  renderCatalog();
}

function clearSearch() {
  const input = document.getElementById('search-input');
  if (input) input.value = '';
  handleSearch('');
}

// ============================================================
//  CAT DETAIL
// ============================================================
function renderDetail(catId) {
  const cat = CATS.find(c => c.id === catId);
  if (!cat) return;

  const inCart = state.cart.includes(cat.id);

  document.getElementById('detail-content').innerHTML = `
    <img
      class="detail-image"
      src="${cat.image}"
      alt="${cat.name}"
      onerror="this.outerHTML='<div class=\\'detail-image-placeholder\\'>🐱</div>'"
    >
    <div class="detail-body">
      <div class="detail-header">
        <div class="detail-name">${cat.name}</div>
        <div class="detail-price">${formatPrice(cat.price)}</div>
      </div>
      <div class="detail-breed">${cat.breed}</div>
      <div class="detail-tags">
        <span class="tag">📅 ${formatAge(cat.age_months)}</span>
        <span class="tag">${cat.gender === 'male' ? '♂ Кот' : '♀ Кошка'}</span>
        <span class="tag">🎨 ${cat.color}</span>
        ${cat.vaccinated ? '<span class="tag">💉 Привит</span>' : ''}
        ${cat.pedigree ? '<span class="tag">📜 Родословная</span>' : ''}
      </div>
      <div class="detail-section-label">Описание</div>
      <div class="detail-desc">${cat.description}</div>
      ${cat.available
        ? `<button
            id="btn-add-${cat.id}"
            class="btn-add-cart"
            onclick="addToCart(${cat.id})"
            ${inCart ? 'disabled' : ''}
           >
             ${inCart ? '✓ Уже в корзине' : '🛒 Добавить в корзину'}
           </button>`
        : `<button class="btn-add-cart" disabled>Котёнок уже продан</button>`
      }
    </div>
  `;
}

// ============================================================
//  CART
// ============================================================
function addToCart(catId) {
  if (state.cart.includes(catId)) return;
  state.cart.push(catId);
  saveCart();
  updateCartBadge();
  showToast('Добавлено в корзину 🛒', 'success');

  const btn = document.getElementById('btn-add-' + catId);
  if (btn) {
    btn.textContent = '✓ Уже в корзине';
    btn.disabled = true;
  }
}

function removeFromCart(catId) {
  state.cart = state.cart.filter(id => id !== catId);
  saveCart();
  updateCartBadge();
  renderCart();
}

function clearCart() {
  state.cart = [];
  saveCart();
  updateCartBadge();
}

function saveCart() {
  try { localStorage.setItem('tg_cats_cart', JSON.stringify(state.cart)); } catch (_) {}
}

function updateCartBadge() {
  const count = state.cart.length;
  ['cart-badge', 'nav-cart-badge'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = count;
    el.classList.toggle('hidden', count === 0);
  });
}

function renderCart() {
  const el = document.getElementById('cart-content');

  if (!state.cart.length) {
    el.innerHTML = `
      <div class="cart-empty">
        <div class="cart-empty-emoji">🛒</div>
        <h2>Корзина пуста</h2>
        <p>Выберите котят из каталога</p>
        <button class="btn-primary" style="max-width:220px" onclick="navigate('catalog')">
          Перейти в каталог
        </button>
      </div>`;
    return;
  }

  const items = state.cart.map(id => CATS.find(c => c.id === id)).filter(Boolean);
  const total = items.reduce((s, c) => s + c.price, 0);

  el.innerHTML = `
    <div class="cart-wrap">
      ${items.map(cat => `
        <div class="cart-item">
          <img
            class="cart-item-img"
            src="${cat.image}"
            alt="${cat.name}"
            onerror="this.style.visibility='hidden'"
          >
          <div class="cart-item-info">
            <div class="cart-item-name">${cat.name}</div>
            <div class="cart-item-breed">${cat.breed}</div>
            <div class="cart-item-price">${formatPrice(cat.price)}</div>
          </div>
          <button class="cart-item-remove" onclick="removeFromCart(${cat.id})" title="Удалить">✕</button>
        </div>
      `).join('')}

      <div class="cart-total">
        <div class="cart-total-row">
          <span class="cart-total-label">
            Итого: ${items.length} котёнк${pluralCats(items.length)}
          </span>
          <span class="cart-total-value">${formatPrice(total)}</span>
        </div>
      </div>

      <button class="btn-primary" onclick="navigate('order')">Оформить заказ</button>
      <button class="btn-secondary" onclick="confirmClearCart()">Очистить корзину</button>
    </div>`;
}

function confirmClearCart() {
  if (window.confirm('Очистить корзину?')) {
    clearCart();
    renderCart();
  }
}

// ============================================================
//  ORDER FORM
// ============================================================
function renderOrderForm() {
  const items = state.cart.map(id => CATS.find(c => c.id === id)).filter(Boolean);
  const total = items.reduce((s, c) => s + c.price, 0);

  const preview = document.getElementById('order-items-preview');
  if (preview) {
    preview.innerHTML = `
      <div class="preview-title">Выбранные котята (${items.length})</div>
      ${items.map(cat => `
        <div class="preview-item">
          <span>🐱 ${cat.name} — ${cat.breed}</span>
          <span>${formatPrice(cat.price)}</span>
        </div>
      `).join('')}
      <div class="order-total-text">Итого: ${formatPrice(total)}</div>
    `;
  }

  // Pre-fill name from Telegram user data
  const user = window.Telegram?.WebApp?.initDataUnsafe?.user;
  if (user) {
    const nameField = document.getElementById('order-name');
    if (nameField && !nameField.value) {
      nameField.value = [user.first_name, user.last_name].filter(Boolean).join(' ');
    }
  }
}

// ============================================================
//  FORM SUBMISSIONS
// ============================================================
function submitOrder(e) {
  e.preventDefault();

  const items = state.cart.map(id => CATS.find(c => c.id === id)).filter(Boolean);
  if (!items.length) {
    showToast('Корзина пуста', 'error');
    return;
  }

  const data = {
    type: 'order',
    name:    document.getElementById('order-name').value.trim(),
    phone:   document.getElementById('order-phone').value.trim(),
    address: document.getElementById('order-address').value.trim(),
    comment: document.getElementById('order-comment').value.trim(),
    items:   items.map(c => ({ id: c.id, name: c.name, breed: c.breed, price: c.price })),
    total:   items.reduce((s, c) => s + c.price, 0),
    ts:      new Date().toISOString(),
  };

  sendToBot(data);
  clearCart();
  document.getElementById('order-form').reset();
  navigate('catalog');
  showToast('Заказ отправлен! ✅', 'success');
}

function submitFeedback(e) {
  e.preventDefault();

  const subjectMap = {
    question: 'Вопрос о котах',
    booking:  'Запись на просмотр',
    review:   'Отзыв о питомнике',
    delivery: 'Вопрос о доставке',
    other:    'Другое',
  };

  const data = {
    type:    'feedback',
    name:    document.getElementById('fb-name').value.trim(),
    contact: document.getElementById('fb-contact').value.trim(),
    subject: subjectMap[document.getElementById('fb-subject').value] || 'Другое',
    message: document.getElementById('fb-message').value.trim(),
    ts:      new Date().toISOString(),
  };

  sendToBot(data);
  document.getElementById('feedback-form').reset();
  showToast('Сообщение отправлено! ✅', 'success');
}

/** Отправляем данные боту через HTTP API */
async function sendToBot(data) {
  // Если URL не задан — выводим в консоль (режим разработки)
  if (!BOT_API_URL) {
    console.log('[Bot data — API URL не задан]', data);
    return true;
  }

  const endpoint = data.type === 'order' ? '/order' : '/feedback';

  try {
    const resp = await fetch(BOT_API_URL + endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Secret': API_SECRET,
      },
      body: JSON.stringify(data),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.error || 'Server error ' + resp.status);
    }
    return true;
  } catch (err) {
    console.error('[Bot API]', err);
    showToast('Ошибка отправки. Попробуйте ещё раз.', 'error');
    return false;
  }
}

// ============================================================
//  UTILS
// ============================================================
function formatPrice(price) {
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    maximumFractionDigits: 0,
  }).format(price);
}

function formatAge(months) {
  if (months < 12) {
    const s = months === 1 ? 'месяц' : months < 5 ? 'месяца' : 'месяцев';
    return `${months} ${s}`;
  }
  const y = Math.floor(months / 12);
  const m = months % 12;
  const ys = y === 1 ? 'год' : y < 5 ? 'года' : 'лет';
  if (!m) return `${y} ${ys}`;
  const ms = m === 1 ? 'мес.' : 'мес.';
  return `${y} ${ys} ${m} ${ms}`;
}

function pluralCats(n) {
  if (n % 10 === 1 && n % 100 !== 11) return 'ок';
  if ([2,3,4].includes(n % 10) && ![12,13,14].includes(n % 100)) return 'ёнка';
  return 'ят';
}

// ============================================================
//  TOAST NOTIFICATIONS
// ============================================================
function showToast(message, type = '') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast${type ? ' ' + type : ''}`;
  toast.textContent = message;
  container.appendChild(toast);

  // Animate in
  requestAnimationFrame(() => {
    requestAnimationFrame(() => toast.classList.add('show'));
  });

  // Animate out
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 300);
  }, 2600);
}
