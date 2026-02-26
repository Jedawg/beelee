// indexeddb-helper.js
// IndexedDB wrapper for storing products efficiently

const DB_NAME = 'BeeProductsDB';
const DB_VERSION = 1;
const STORE_NAME = 'products';

class ProductDB {
  constructor() {
    this.db = null;
  }

  // Initialize database
  async init() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.db = request.result;
        resolve(this.db);
      };

      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        
        // Create object store if it doesn't exist
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          const objectStore = db.createObjectStore(STORE_NAME, { keyPath: 'id' });
          
          // Create indexes for efficient querying
          objectStore.createIndex('store', 'store', { unique: false });
          objectStore.createIndex('category', 'category', { unique: false });
          objectStore.createIndex('price', 'price', { unique: false });
        }
      };
    });
  }

  // Save all products (batch insert)
  async saveProducts(products) {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction([STORE_NAME], 'readwrite');
      const objectStore = transaction.objectStore(STORE_NAME);

      // Clear existing products
      objectStore.clear();

      // Add all products
      products.forEach(product => {
        objectStore.add(product);
      });

      transaction.oncomplete = () => resolve(products.length);
      transaction.onerror = () => reject(transaction.error);
    });
  }

  // Get all products
  async getAllProducts() {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction([STORE_NAME], 'readonly');
      const objectStore = transaction.objectStore(STORE_NAME);
      const request = objectStore.getAll();

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  // Get products by store
  async getProductsByStore(storeName) {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction([STORE_NAME], 'readonly');
      const objectStore = transaction.objectStore(STORE_NAME);
      const index = objectStore.index('store');
      const request = index.getAll(storeName);

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  // Get products by category
  async getProductsByCategory(category) {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction([STORE_NAME], 'readonly');
      const objectStore = transaction.objectStore(STORE_NAME);
      const index = objectStore.index('category');
      const request = index.getAll(category);

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  // Get products in batches (for progressive loading)
  async getProductsBatch(offset = 0, limit = 100) {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction([STORE_NAME], 'readonly');
      const objectStore = transaction.objectStore(STORE_NAME);
      const request = objectStore.openCursor();
      
      const results = [];
      let advanced = 0;
      let collected = 0;

      request.onsuccess = (event) => {
        const cursor = event.target.result;
        
        if (cursor) {
          // Skip to offset
          if (advanced < offset) {
            advanced++;
            cursor.continue();
            return;
          }

          // Collect up to limit
          if (collected < limit) {
            results.push(cursor.value);
            collected++;
            cursor.continue();
          } else {
            resolve(results);
          }
        } else {
          // No more results
          resolve(results);
        }
      };

      request.onerror = () => reject(request.error);
    });
  }

  // Count total products
  async count() {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction([STORE_NAME], 'readonly');
      const objectStore = transaction.objectStore(STORE_NAME);
      const request = objectStore.count();

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  // Clear all products
  async clear() {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db.transaction([STORE_NAME], 'readwrite');
      const objectStore = transaction.objectStore(STORE_NAME);
      const request = objectStore.clear();

      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  }
}

// Export singleton instance
const productDB = new ProductDB();

// Make it available globally
if (typeof window !== 'undefined') {
  window.ProductDB = productDB;
}
