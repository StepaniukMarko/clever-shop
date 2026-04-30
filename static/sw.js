const CACHE_NAME = 'clever-shop-v2';
const urlsToCache = [
  '/',
  '/static/style.css',
  '/static/script.js',
  '/static/logo.png',
  '/static/manifest.json'
];

// Install event - cache resources
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Opened cache');
        // Додаємо файли по одному, щоб один невдалий не зупинив весь процес
        return Promise.allSettled(
          urlsToCache.map(url => 
            cache.add(url).catch(err => console.log('Failed to cache:', url))
          )
        );
      })
  );
  // Активувати новий SW одразу
  self.skipWaiting();
});

// Fetch event - serve from cache when offline
self.addEventListener('fetch', event => {
  // Ігноруємо не-GET запити
  if (event.request.method !== 'GET') return;
  
  // Ігноруємо зовнішні запити
  if (!event.request.url.startsWith(self.location.origin)) return;
  
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // Return cached version or fetch from network
        if (response) {
          return response;
        }
        
        return fetch(event.request).then(response => {
          // Кешуємо нові успішні відповіді
          if (response && response.status === 200 && response.type === 'basic') {
            const responseToCache = response.clone();
            caches.open(CACHE_NAME).then(cache => {
              cache.put(event.request, responseToCache);
            });
          }
          return response;
        });
      })
      .catch(() => {
        // Повертаємо офлайн сторінку якщо є
        return caches.match('/');
      })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            console.log('Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  // Активувати SW для всіх клієнтів
  return self.clients.claim();
});

// Push notification event
self.addEventListener('push', event => {
  const options = {
    body: event.data ? event.data.text() : 'Нові товари в Clever Shop!',
    icon: '/static/logo.png',
    badge: '/static/logo.png',
    vibrate: [100, 50, 100],
    data: {
      dateOfArrival: Date.now(),
      primaryKey: 1
    },
    actions: [
      {
        action: 'explore',
        title: 'Переглянути'
      },
      {
        action: 'close',
        title: 'Закрити'
      }
    ]
  };

  event.waitUntil(
    self.registration.showNotification('Clever Shop', options)
  );
});

// Notification click event
self.addEventListener('notificationclick', event => {
  event.notification.close();

  if (event.action === 'explore') {
    event.waitUntil(
      clients.openWindow('/')
    );
  }
});