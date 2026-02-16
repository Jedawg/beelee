import React, { useState, useMemo, useCallback, useEffect } from 'react';
import * as XLSX from 'xlsx';
import { Upload, ArrowUpDown, Search, X, ChefHat, Plus, Trash2, ShoppingCart, Save, BookOpen, ShoppingBag, TrendingDown, Share2, Mail, MessageCircle, MessageSquare } from 'lucide-react';

// ==================== STORAGE ====================
const recipeStorage = {
  async list() {
    if (!window.storage) return [];
    try {
      const result = await window.storage.list('recipe:');
      if (!result || !result.keys) return [];
      const recipes = [];
      for (const key of result.keys) {
        const data = await window.storage.get(key);
        if (data) recipes.push(JSON.parse(data.value));
      }
      return recipes;
    } catch {
      return [];
    }
  },
  async save(recipe) {
    if (!window.storage) return;
    await window.storage.set(`recipe:${recipe.id}`, JSON.stringify(recipe));
  },
  async remove(id) {
    if (!window.storage) return;
    await window.storage.delete(`recipe:${id}`);
  }
};

// ==================== UTILS ====================
const fileCache = new Map();

async function parseExcel(file) {
  if (fileCache.has(file.name)) return fileCache.get(file.name);
  const buffer = await file.arrayBuffer();
  const wb = XLSX.read(buffer);
  const ws = wb.Sheets[wb.SheetNames[0]];
  const rows = XLSX.utils.sheet_to_json(ws);
  const products = rows.map(row => ({
    id: crypto.randomUUID(),
    title: row.title || 'Unknown',
    price: Number(row.price) || 0,
    category: row.category || 'Uncategorized',
    store: row.store || 'Unknown',
    imageBase64: row.image_base64 || null,
    offerExpiryDate: row.offer_expiry_date || null,
    remainingDays: row.remaining_days !== undefined ? Number(row.remaining_days) : null
  }));
  fileCache.set(file.name, products);
  return products;
}

function calculateDaysRemaining(expiryDate) {
  if (!expiryDate) return null;
  const expiry = new Date(expiryDate);
  const now = new Date();
  const diffTime = expiry - now;
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  return diffDays > 0 ? diffDays : 0;
}

function getStoreColor(store) {
  const colors = {
    'Rema1000': { bg: 'bg-blue-100', text: 'text-blue-700', name: 'REMA 1000' },
    'Netto': { bg: 'bg-yellow-100', text: 'text-yellow-700', name: 'NETTO' },
    'Min Kobman': { bg: 'bg-green-100', text: 'text-green-700', name: 'MIN KØBMAND' },
    'Spar': { bg: 'bg-red-100', text: 'text-red-700', name: 'SPAR' },
    'Nemlig.com': { bg: 'bg-purple-100', text: 'text-purple-700', name: 'NEMLIG.COM' }
  };
  return colors[store] || { bg: 'bg-gray-100', text: 'text-gray-700', name: store.toUpperCase() };
}

function findCheapestProduct(productsById, searchTerm) {
  const matches = Object.values(productsById).filter(p =>
    p.title.toLowerCase().includes(searchTerm.toLowerCase())
  );
  if (matches.length === 0) return null;
  return matches.reduce((cheapest, current) =>
    current.price < cheapest.price ? current : cheapest
  );
}

function getCheapestByCategory(productsById) {
  const byCategory = {};
  Object.values(productsById).forEach(product => {
    const cat = product.category;
    if (!byCategory[cat] || product.price < byCategory[cat].price) {
      byCategory[cat] = product;
    }
  });
  return Object.values(byCategory).sort((a, b) => a.category.localeCompare(b.category));
}

// ==================== SHARE FUNCTION ====================
function generateBasketText(basket, productsById) {
  const storeGroups = {};
  let totalPrice = 0;

  basket.forEach(item => {
    const product = productsById[item.productId];
    if (!product) return;
    
    if (!storeGroups[product.store]) {
      storeGroups[product.store] = { items: [], total: 0 };
    }
    
    const itemTotal = product.price * item.quantity;
    storeGroups[product.store].items.push({
      title: product.title,
      quantity: item.quantity,
      price: product.price,
      total: itemTotal
    });
    storeGroups[product.store].total += itemTotal;
    totalPrice += itemTotal;
  });

  let text = '🛒 SHOPPING BASKET\n';
  text += '═══════════════════════════════\n\n';

  Object.entries(storeGroups).forEach(([store, data]) => {
    const storeInfo = getStoreColor(store);
    text += `📍 ${storeInfo.name}\n`;
    text += `───────────────────────────────\n`;
    
    data.items.forEach(item => {
      text += `• ${item.title}\n`;
      text += `  ${item.quantity}x ${item.price.toFixed(2)} kr = ${item.total.toFixed(2)} kr\n`;
    });
    
    text += `\nStore Total: ${data.total.toFixed(2)} kr\n\n`;
  });

  text += '═══════════════════════════════\n';
  text += `GRAND TOTAL: ${totalPrice.toFixed(2)} kr\n`;
  text += `Total Items: ${basket.reduce((sum, item) => sum + item.quantity, 0)}\n`;
  text += `Stores: ${Object.keys(storeGroups).length}\n`;
  text += '═══════════════════════════════\n';
  text += `Generated: ${new Date().toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' })}\n`;

  return text;
}

async function shareBasket(basket, productsById) {
  const text = generateBasketText(basket, productsById);
  
  try {
    // Try Web Share API first (mobile devices)
    if (navigator.share) {
      await navigator.share({
        title: 'Shopping Basket',
        text: text
      });
      return;
    }
  } catch (err) {
    console.log('Share failed:', err);
    // Continue to clipboard fallback if share fails or is cancelled
    if (err.name === 'AbortError') {
      return; // User cancelled
    }
  }
  
  // Fallback: Copy to clipboard
  try {
    // Method 1: Modern Clipboard API
    await navigator.clipboard.writeText(text);
    alert('✅ Copied to clipboard!\n\nPaste it into WhatsApp, Messages, or any app.');
    return;
  } catch (err) {
    console.log('Clipboard API failed:', err);
  }
  
  // Method 2: Legacy textarea method
  try {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'absolute';
    textArea.style.opacity = '0';
    textArea.style.left = '-9999px';
    document.body.appendChild(textArea);
    
    textArea.select();
    textArea.setSelectionRange(0, 99999);
    
    const successful = document.execCommand('copy');
    document.body.removeChild(textArea);
    
    if (successful) {
      alert('✅ Copied to clipboard!\n\nPaste it into WhatsApp, Messages, or any app.');
      return;
    }
  } catch (err) {
    console.log('execCommand failed:', err);
  }
  
  // Method 3: Show text for manual copy
  const userCopy = prompt('Press Cmd+C (Mac) or Ctrl+C (Windows) to copy:', text);
  if (userCopy !== null) {
    alert('Please try copying the text from the dialog box.');
  }
}

function fallbackToCopy(text) {
  // Deprecated - kept for compatibility
  alert('✅ Copied to clipboard!');
}

// ==================== HOOKS ====================
function useProducts() {
  const [productsById, setProductsById] = useState({});
  const [productIds, setProductIds] = useState([]);

  const addProductsFromFile = useCallback(async (file) => {
    const newProducts = await parseExcel(file);
    setProductsById(prev => {
      const next = { ...prev };
      newProducts.forEach(p => { if (!next[p.id]) next[p.id] = p; });
      return next;
    });
    setProductIds(prev => {
      const set = new Set(prev);
      newProducts.forEach(p => set.add(p.id));
      return Array.from(set);
    });
  }, []);

  return { productsById, productIds, addProductsFromFile };
}

function useRecipes(productsById) {
  const [recipes, setRecipes] = useState([]);
  const [currentRecipe, setCurrentRecipe] = useState({ id: null, name: '', ingredients: [] });

  useEffect(() => { recipeStorage.list().then(setRecipes); }, []);

  const saveRecipe = useCallback(async () => {
    if (!currentRecipe.name.trim() || currentRecipe.ingredients.length === 0) {
      alert('Please enter a recipe name and add ingredients');
      return;
    }
    const recipe = {
      id: currentRecipe.id || crypto.randomUUID(),
      name: currentRecipe.name,
      ingredients: currentRecipe.ingredients,
      createdAt: currentRecipe.id ? recipes.find(r => r.id === currentRecipe.id)?.createdAt || new Date().toISOString() : new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };
    await recipeStorage.save(recipe);
    if (currentRecipe.id) {
      setRecipes(prev => prev.map(r => r.id === recipe.id ? recipe : r));
      alert('Recipe updated!');
    } else {
      setRecipes(prev => [...prev, recipe]);
      alert('Recipe saved!');
    }
    setCurrentRecipe({ id: recipe.id, name: recipe.name, ingredients: recipe.ingredients });
  }, [currentRecipe, recipes]);

  const loadRecipe = useCallback((recipe) => {
    setCurrentRecipe({ id: recipe.id, name: recipe.name, ingredients: recipe.ingredients });
  }, []);

  const deleteRecipe = useCallback(async (id) => {
    try {
      console.log('Deleting recipe:', id);
      
      // Remove from storage
      if (window.storage) {
        await window.storage.delete(`recipe:${id}`);
        console.log('Deleted from storage');
      }
      
      // Update local state
      setRecipes(prev => {
        const updated = prev.filter(r => r.id !== id);
        console.log('Recipes after delete:', updated.length);
        return updated;
      });
      
      // Clear current recipe if it's the one being deleted
      if (currentRecipe.id === id) {
        setCurrentRecipe({ id: null, name: '', ingredients: [] });
      }
    } catch (error) {
      console.error('Error deleting recipe:', error);
      
      // Still update UI even if storage fails
      setRecipes(prev => prev.filter(r => r.id !== id));
      if (currentRecipe.id === id) {
        setCurrentRecipe({ id: null, name: '', ingredients: [] });
      }
    }
  }, [currentRecipe.id]);

  const updateRecipeName = useCallback((name) => {
    setCurrentRecipe(prev => ({ ...prev, name }));
  }, []);

  const addIngredient = useCallback((productId, quantity, searchTerm) => {
    setCurrentRecipe(prev => {
      const existing = prev.ingredients.find(i => i.productId === productId);
      if (existing) {
        return { ...prev, ingredients: prev.ingredients.map(i => i.productId === productId ? { ...i, quantity: i.quantity + quantity } : i) };
      }
      return { ...prev, ingredients: [...prev.ingredients, { productId, quantity, searchTerm }] };
    });
  }, []);

  const removeIngredient = useCallback((productId) => {
    setCurrentRecipe(prev => ({ ...prev, ingredients: prev.ingredients.filter(i => i.productId !== productId) }));
  }, []);

  const updateIngredientQuantity = useCallback((productId, quantity) => {
    if (quantity <= 0) {
      removeIngredient(productId);
    } else {
      setCurrentRecipe(prev => ({ ...prev, ingredients: prev.ingredients.map(i => i.productId === productId ? { ...i, quantity } : i) }));
    }
  }, [removeIngredient]);

  const createNewRecipe = useCallback(() => {
    setCurrentRecipe({ id: null, name: '', ingredients: [] });
  }, []);

  return { recipes, currentRecipe, saveRecipe, loadRecipe, deleteRecipe, updateRecipeName, addIngredient, removeIngredient, updateIngredientQuantity, createNewRecipe };
}

function useBasket() {
  const [basket, setBasket] = useState([]);

  const addToBasket = useCallback((productId, quantity = 1) => {
    setBasket(prev => {
      const existing = prev.find(item => item.productId === productId);
      if (existing) {
        return prev.map(item => item.productId === productId ? { ...item, quantity: item.quantity + quantity } : item);
      }
      return [...prev, { productId, quantity }];
    });
  }, []);

  const removeFromBasket = useCallback((productId) => {
    setBasket(prev => prev.filter(item => item.productId !== productId));
  }, []);

  const updateBasketQuantity = useCallback((productId, quantity) => {
    if (quantity <= 0) {
      removeFromBasket(productId);
    } else {
      setBasket(prev => prev.map(item => item.productId === productId ? { ...item, quantity } : item));
    }
  }, [removeFromBasket]);

  const clearBasket = useCallback(() => { setBasket([]); }, []);

  const addRecipeToBasket = useCallback((ingredients) => {
    setBasket(prev => {
      const updated = [...prev];
      ingredients.forEach(ing => {
        const existingIndex = updated.findIndex(item => item.productId === ing.productId);
        if (existingIndex >= 0) {
          updated[existingIndex] = { ...updated[existingIndex], quantity: updated[existingIndex].quantity + ing.quantity };
        } else {
          updated.push({ productId: ing.productId, quantity: ing.quantity });
        }
      });
      return updated;
    });
  }, []);

  return { basket, addToBasket, removeFromBasket, updateBasketQuantity, clearBasket, addRecipeToBasket };
}

// ==================== COMPONENTS ====================
function StoreBadge({ store }) {
  const storeInfo = getStoreColor(store);
  return <span className={`text-xs ${storeInfo.bg} ${storeInfo.text} px-2 py-0.5 rounded font-semibold`}>{storeInfo.name}</span>;
}

function OfferExpiry({ expiryDate, remainingDays }) {
  // Prefer remainingDays from Excel if available
  const days = remainingDays !== null && remainingDays !== undefined 
    ? remainingDays 
    : calculateDaysRemaining(expiryDate);
  
  if (days === null) return null;
  
  const colorClass = days <= 1 ? 'bg-red-100 text-red-700' : 
                     days <= 3 ? 'bg-orange-100 text-orange-700' : 
                     'bg-green-100 text-green-700';
  
  return <span className={`text-xs ${colorClass} px-2 py-0.5 rounded font-semibold`}>{days}d</span>;
}

function ProductsTab({ productsById, productIds, onUpload, onAddToBasket }) {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('all');
  const [sortOrder, setSortOrder] = useState('asc');
  const [loading, setLoading] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState(null);

  const categories = useMemo(() => {
    const cats = new Set(Object.values(productsById).map(p => p.category));
    return ['all', ...Array.from(cats)];
  }, [productsById]);

  const products = useMemo(() => {
    return productIds
      .map(id => productsById[id])
      .filter(p => {
        const matchesSearch = !search || p.title.toLowerCase().includes(search.toLowerCase());
        const matchesCategory = category === 'all' || p.category === category;
        return matchesSearch && matchesCategory;
      })
      .sort((a, b) => sortOrder === 'asc' ? a.price - b.price : b.price - a.price);
  }, [productIds, productsById, search, category, sortOrder]);

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setLoading(true);
    try {
      await onUpload(file);
    } catch (error) {
      alert('Failed to load file: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      {selectedProduct && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" onClick={() => setSelectedProduct(null)}>
          <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="p-6">
              <div className="flex justify-between items-start mb-4">
                <h2 className="text-2xl font-bold text-gray-800">{selectedProduct.title}</h2>
                <button onClick={() => setSelectedProduct(null)} className="p-2 hover:bg-gray-100 rounded-lg">
                  <X className="w-6 h-6 text-gray-600" />
                </button>
              </div>
              
              <div className="mb-6">
                {selectedProduct.imageBase64 ? (
                  <img src={selectedProduct.imageBase64} alt={selectedProduct.title} className="w-full h-96 object-contain bg-gray-50 rounded-lg" />
                ) : (
                  <div className="w-full h-96 bg-gray-200 rounded-lg flex items-center justify-center">
                    <p className="text-gray-400">No image available</p>
                  </div>
                )}
              </div>

              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 flex-wrap">
                    <StoreBadge store={selectedProduct.store} />
                    <OfferExpiry expiryDate={selectedProduct.offerExpiryDate} remainingDays={selectedProduct.remainingDays} />
                  </div>
                  <p className="text-4xl font-bold text-indigo-600">{selectedProduct.price.toFixed(2)} kr</p>
                </div>

                <div className="border-t pt-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-sm text-gray-600">Category</p>
                      <p className="font-semibold text-gray-800">{selectedProduct.category}</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-600">Store</p>
                      <p className="font-semibold text-gray-800">{selectedProduct.store}</p>
                    </div>
                  </div>
                </div>

                {selectedProduct.remainingDays !== null && selectedProduct.remainingDays !== undefined && (
                  <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
                    <p className="text-sm font-semibold text-orange-800">Limited Time Offer</p>
                    <p className="text-sm text-orange-700">Expires in {selectedProduct.remainingDays} day{selectedProduct.remainingDays !== 1 ? 's' : ''}</p>
                  </div>
                )}

                <button
                  onClick={() => {
                    onAddToBasket(selectedProduct.id);
                    setSelectedProduct(null);
                  }}
                  className="w-full py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 font-semibold text-lg"
                >
                  Add to Basket
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="mb-6">
        <label className="flex flex-col items-center justify-center w-full h-32 md:h-40 border-2 border-dashed border-indigo-300 rounded-xl cursor-pointer hover:bg-indigo-50">
          <div className="flex flex-col items-center pt-5 pb-6">
            <Upload className="w-8 md:w-12 h-8 md:h-12 text-indigo-500 mb-3" />
            <p className="text-xs md:text-sm text-gray-600 font-semibold">Click to upload Excel file</p>
            <p className="text-xs text-gray-500 mt-1">Upload multiple files to compare stores</p>
          </div>
          <input type="file" className="hidden" accept=".xlsx,.xls" onChange={handleUpload} disabled={loading} />
        </label>
      </div>

      {loading && (
        <div className="text-center py-8">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      )}

      {productIds.length > 0 && (
        <div>
          <div className="mb-6 p-3 md:p-4 bg-blue-50 border-l-4 border-blue-600 rounded-lg">
            <div className="flex items-center gap-3 flex-wrap">
              <StoreBadge store="Rema1000" />
              <StoreBadge store="Netto" />
              <StoreBadge store="Min Kobman" />
              <StoreBadge store="Spar" />
              <StoreBadge store="Nemlig.com" />
              <div>
                <p className="text-xs md:text-sm font-semibold text-gray-800">{productIds.length} products</p>
              </div>
            </div>
          </div>

          <div className="flex flex-col md:flex-row gap-3 mb-6">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
              <input
                type="text"
                placeholder="Search products..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-10 pr-10 py-3 border border-gray-300 rounded-lg"
              />
              {search && (
                <button onClick={() => setSearch('')} className="absolute right-3 top-1/2 transform -translate-y-1/2">
                  <X className="w-5 h-5 text-gray-400" />
                </button>
              )}
            </div>
            <select value={category} onChange={(e) => setCategory(e.target.value)} className="px-4 py-3 border border-gray-300 rounded-lg">
              {categories.map(cat => <option key={cat} value={cat}>{cat === 'all' ? 'All Categories' : cat}</option>)}
            </select>
            <button onClick={() => setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc')} className="flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 font-semibold">
              <ArrowUpDown className="w-5 h-5" />
              <span className="hidden sm:inline">{sortOrder === 'asc' ? 'Cheapest' : 'Expensive'}</span>
            </button>
          </div>

          <div className="space-y-3 max-h-[600px] overflow-y-auto">
            {products.map((product) => (
              <div key={product.id} className="flex items-center gap-3 p-3 md:p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors cursor-pointer" onClick={() => setSelectedProduct(product)}>
                <div className="w-16 h-16 md:w-20 md:h-20 flex-shrink-0">
                  {product.imageBase64 ? (
                    <img src={product.imageBase64} alt={product.title} className="w-full h-full object-cover rounded-lg" />
                  ) : (
                    <div className="w-full h-full bg-gray-200 rounded-lg"></div>
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-sm md:text-base truncate">{product.title}</h3>
                  <div className="flex items-center gap-2 mt-1 flex-wrap">
                    <StoreBadge store={product.store} />
                    <OfferExpiry expiryDate={product.offerExpiryDate} remainingDays={product.remainingDays} />
                    <span className="text-xs text-gray-500 truncate">{product.category}</span>
                  </div>
                </div>
                <div className="text-right flex-shrink-0">
                  <p className="text-lg md:text-2xl font-bold text-indigo-600">{product.price.toFixed(2)} kr</p>
                  <button 
                    onClick={(e) => {
                      e.stopPropagation();
                      onAddToBasket(product.id);
                    }} 
                    className="mt-2 px-3 py-1 bg-green-600 text-white rounded-lg hover:bg-green-700 text-xs font-semibold"
                  >
                    + Basket
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function BestOffersTab({ productsById, onAddToBasket }) {
  const [searchTerm, setSearchTerm] = useState('');

  const cheapestProducts = useMemo(() => {
    const cheapest = getCheapestByCategory(productsById);
    if (!searchTerm) return cheapest;
    return cheapest.filter(p =>
      p.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.category.toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [productsById, searchTerm]);

  const totalSavings = useMemo(() => {
    return cheapestProducts.reduce((sum, product) => {
      const allInCategory = Object.values(productsById).filter(p => p.category === product.category);
      const maxPrice = Math.max(...allInCategory.map(p => p.price));
      return sum + (maxPrice - product.price);
    }, 0);
  }, [cheapestProducts, productsById]);

  if (Object.keys(productsById).length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-600 mb-4">Upload products first to see best offers</p>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6 p-4 bg-gradient-to-r from-green-50 to-blue-50 border-l-4 border-green-600 rounded-lg">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h2 className="text-lg font-bold text-gray-800">Best Offers by Category</h2>
            <p className="text-sm text-gray-600">Showing the cheapest product in each category</p>
          </div>
          <div className="text-right">
            <p className="text-2xl font-bold text-green-600">{totalSavings.toFixed(2)} kr</p>
            <p className="text-xs text-gray-600">Total savings</p>
          </div>
        </div>
      </div>

      <div className="mb-6">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
          <input
            type="text"
            placeholder="Search categories or products..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-10 py-3 border border-gray-300 rounded-lg"
          />
          {searchTerm && (
            <button onClick={() => setSearchTerm('')} className="absolute right-3 top-1/2 transform -translate-y-1/2">
              <X className="w-5 h-5 text-gray-400" />
            </button>
          )}
        </div>
      </div>

      <div className="space-y-4">
        {cheapestProducts.map((product) => {
          const allInCategory = Object.values(productsById).filter(p => p.category === product.category);
          const avgPrice = allInCategory.reduce((sum, p) => sum + p.price, 0) / allInCategory.length;
          const savings = ((avgPrice - product.price) / avgPrice * 100);

          return (
            <div key={product.id} className="bg-gradient-to-r from-white to-green-50 border-2 border-green-200 rounded-lg p-4">
              <div className="flex items-center gap-4">
                <div className="w-20 h-20 flex-shrink-0">
                  {product.imageBase64 ? (
                    <img src={product.imageBase64} alt={product.title} className="w-full h-full object-cover rounded-lg" />
                  ) : (
                    <div className="w-full h-full bg-gray-200 rounded-lg"></div>
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className="bg-green-100 text-green-700 text-xs font-bold px-2 py-1 rounded">BEST PRICE</span>
                    {savings > 5 && (
                      <span className="bg-orange-100 text-orange-700 text-xs font-bold px-2 py-1 rounded">{savings.toFixed(0)}% cheaper</span>
                    )}
                  </div>
                  <h3 className="font-bold text-lg truncate">{product.title}</h3>
                  <p className="text-sm text-gray-600 mb-2">{product.category}</p>
                  <div className="flex items-center gap-2 flex-wrap">
                    <StoreBadge store={product.store} />
                    <OfferExpiry expiryDate={product.offerExpiryDate} />
                    <span className="text-xs text-gray-500">{allInCategory.length} options</span>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-3xl font-bold text-green-600">{product.price.toFixed(2)} kr</p>
                  <p className="text-xs text-gray-500">Avg: {avgPrice.toFixed(2)} kr</p>
                  <button onClick={() => onAddToBasket(product.id)} className="mt-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm font-semibold">+ Basket</button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {cheapestProducts.length === 0 && (
        <div className="text-center py-12 bg-gray-50 rounded-lg">
          <p className="text-gray-600">No products match your search</p>
        </div>
      )}
    </div>
  );
}

function RecipesTab({ productsById, productIds, recipes, currentRecipe, onSave, onLoad, onDelete, onUpdateName, onAddIngredient, onRemoveIngredient, onUpdateQuantity, onCreateNew, onAddToBasket }) {
  const [showAddIngredient, setShowAddIngredient] = useState(false);
  const [showSavedRecipes, setShowSavedRecipes] = useState(false);
  const [ingredientSearch, setIngredientSearch] = useState('');
  const [deleteConfirm, setDeleteConfirm] = useState(null);

  const searchResults = useMemo(() => {
    if (!ingredientSearch) return [];
    return productIds
      .map(id => productsById[id])
      .filter(p => p.title.toLowerCase().includes(ingredientSearch.toLowerCase()))
      .sort((a, b) => a.price - b.price);
  }, [productIds, productsById, ingredientSearch]);

  const recipeTotal = useMemo(() => {
    return currentRecipe.ingredients.reduce((sum, ing) => {
      const product = productsById[ing.productId];
      return product ? sum + (product.price * ing.quantity) : sum;
    }, 0);
  }, [currentRecipe.ingredients, productsById]);

  const getRecipeTotal = useCallback((recipe) => {
    return recipe.ingredients.reduce((sum, ing) => {
      const product = productsById[ing.productId];
      return product ? sum + (product.price * ing.quantity) : sum;
    }, 0);
  }, [productsById]);

  const handleAddIngredient = (product) => {
    onAddIngredient(product.id, 1, ingredientSearch);
    setIngredientSearch('');
    setShowAddIngredient(false);
  };

  if (productIds.length === 0) {
    return (
      <div className="text-center py-12">
        <ChefHat className="w-16 h-16 text-gray-300 mx-auto mb-4" />
        <p className="text-gray-600 mb-4">Upload products first</p>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6">
        <label className="block text-sm font-semibold text-gray-700 mb-2">Recipe Name</label>
        <input
          type="text"
          placeholder="e.g., Bolognese"
          value={currentRecipe.name}
          onChange={(e) => onUpdateName(e.target.value)}
          className="w-full px-4 py-3 border border-gray-300 rounded-lg"
        />
      </div>

      <div className="flex gap-3 mb-6 flex-wrap">
        <button onClick={() => setShowAddIngredient(!showAddIngredient)} className="flex items-center gap-2 px-4 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 font-semibold">
          <Plus className="w-5 h-5" />
          Add Ingredient
        </button>
        <button onClick={() => setShowSavedRecipes(!showSavedRecipes)} className="flex items-center gap-2 px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 font-semibold">
          <BookOpen className="w-5 h-5" />
          Saved ({recipes.length})
        </button>
        {currentRecipe.id && (
          <button onClick={onCreateNew} className="flex items-center gap-2 px-4 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 font-semibold">
            <Plus className="w-5 h-5" />
            New Recipe
          </button>
        )}
      </div>

      {showSavedRecipes && recipes.length > 0 && (
        <div className="mb-6 p-4 bg-gray-50 rounded-lg">
          <h3 className="font-semibold mb-4">Saved Recipes</h3>
          <div className="space-y-3">
            {recipes.map((recipe) => (
              <div key={recipe.id} className="relative">
                {deleteConfirm === recipe.id && (
                  <div className="absolute inset-0 bg-white border-2 border-red-500 rounded-lg p-4 z-10 flex flex-col items-center justify-center">
                    <p className="font-semibold text-gray-800 mb-4">Delete "{recipe.name}"?</p>
                    <div className="flex gap-3">
                      <button
                        onClick={() => {
                          onDelete(recipe.id);
                          setDeleteConfirm(null);
                        }}
                        className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 font-semibold"
                      >
                        Yes, Delete
                      </button>
                      <button
                        onClick={() => setDeleteConfirm(null)}
                        className="px-4 py-2 bg-gray-200 text-gray-800 rounded-lg hover:bg-gray-300 font-semibold"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
                <div className="flex items-center justify-between p-4 bg-white rounded-lg border">
                  <div className="flex-1 min-w-0">
                    <h4 className="font-semibold">{recipe.name}</h4>
                    <p className="text-sm text-gray-600">
                      {recipe.ingredients.length} items - <span className="font-semibold text-indigo-600">{getRecipeTotal(recipe).toFixed(2)} kr</span>
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={() => onLoad(recipe)} className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 text-sm font-semibold">Load</button>
                    <button onClick={() => { onAddToBasket(recipe.ingredients); alert(`Added to basket!`); }} className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm font-semibold">+ Basket</button>
                    <button
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        setDeleteConfirm(recipe.id);
                      }}
                      className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                      type="button"
                      title="Delete recipe"
                    >
                      <Trash2 className="w-5 h-5" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {showAddIngredient && (
        <div className="mb-6 p-4 bg-gray-50 rounded-lg">
          <div className="relative mb-4">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
            <input
              type="text"
              placeholder="Search products... (sorted cheapest first)"
              value={ingredientSearch}
              onChange={(e) => setIngredientSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg"
              autoFocus
            />
          </div>
          {searchResults.length > 0 && (
            <div className="space-y-2 max-h-96 overflow-y-auto">
              <p className="text-xs text-gray-600 mb-2">
                Showing {searchResults.length} result{searchResults.length !== 1 ? 's' : ''} - sorted by price
              </p>
              {searchResults.map((product) => (
                <div key={product.id} onClick={() => handleAddIngredient(product)} className="flex items-center gap-3 p-3 bg-white rounded-lg hover:bg-indigo-50 cursor-pointer border border-gray-200 transition-colors">
                  <div className="w-16 h-16 flex-shrink-0">
                    {product.imageBase64 ? (
                      <img src={product.imageBase64} alt={product.title} className="w-full h-full object-cover rounded-lg" />
                    ) : (
                      <div className="w-full h-full bg-gray-200 rounded-lg"></div>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-sm truncate">{product.title}</p>
                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                      <StoreBadge store={product.store} />
                      <OfferExpiry expiryDate={product.offerExpiryDate} remainingDays={product.remainingDays} />
                      <span className="text-xs text-gray-500">{product.category}</span>
                    </div>
                  </div>
                  <p className="text-lg font-bold text-green-600">{product.price.toFixed(2)} kr</p>
                </div>
              ))}
            </div>
          )}
          {ingredientSearch && searchResults.length === 0 && (
            <p className="text-sm text-gray-500 text-center py-4">No products found</p>
          )}
        </div>
      )}

      {currentRecipe.ingredients.length > 0 && (
        <div>
          <div className="mb-6">
            <h3 className="text-lg font-semibold mb-4">Ingredients</h3>
            <div className="space-y-3">
              {currentRecipe.ingredients.map((ing) => {
                const product = productsById[ing.productId];
                if (!product) return null;
                return (
                  <div key={ing.productId} className="flex items-center gap-3 p-4 bg-white border rounded-lg">
                    <div className="w-16 h-16">
                      {product.imageBase64 && <img src={product.imageBase64} alt={product.title} className="w-full h-full object-cover rounded-lg" />}
                    </div>
                    <div className="flex-1">
                      <p className="font-semibold truncate">{product.title}</p>
                      <div className="flex items-center gap-2 mt-1 flex-wrap">
                        <StoreBadge store={product.store} />
                        <OfferExpiry expiryDate={product.offerExpiryDate} />
                      </div>
                      <p className="text-xs text-gray-600 mt-1">
                        {product.price.toFixed(2)} kr x {ing.quantity} = <span className="font-semibold text-indigo-600">{(product.price * ing.quantity).toFixed(2)} kr</span>
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <input
                        type="number"
                        min="1"
                        value={ing.quantity}
                        onChange={(e) => onUpdateQuantity(ing.productId, parseInt(e.target.value) || 1)}
                        className="w-16 px-2 py-1 border rounded text-center"
                      />
                      <button onClick={() => onRemoveIngredient(ing.productId)} className="p-2 text-red-600 hover:bg-red-50 rounded">
                        <Trash2 className="w-5 h-5" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="bg-white border-t-4 border-indigo-600 rounded-lg p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Total Cost</p>
                <p className="text-4xl font-bold text-indigo-600">{recipeTotal.toFixed(2)} kr</p>
                {currentRecipe.id && <p className="text-xs text-gray-500 mt-1">Editing existing recipe</p>}
              </div>
              <div className="flex gap-3">
                <button onClick={onSave} className="flex items-center gap-2 px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 font-semibold">
                  <Save className="w-5 h-5" />
                  {currentRecipe.id ? 'Update' : 'Save'}
                </button>
                <button onClick={onCreateNew} className="px-4 py-3 text-red-600 hover:bg-red-50 rounded-lg font-semibold">Clear</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {currentRecipe.ingredients.length === 0 && (
        <div className="text-center py-12 bg-gray-50 rounded-lg">
          <ChefHat className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-600">No ingredients yet</p>
        </div>
      )}
    </div>
  );
}

function BasketTab({ basket, productsById, onUpdateQuantity, onRemove, onClear }) {
  const [showShareModal, setShowShareModal] = useState(false);
  const [basketText, setBasketText] = useState('');

  // Group basket items by store
  const basketByStore = useMemo(() => {
    const storeGroups = {};
    
    basket.forEach(item => {
      const product = productsById[item.productId];
      if (!product) return;
      
      if (!storeGroups[product.store]) {
        storeGroups[product.store] = {
          items: [],
          total: 0
        };
      }
      
      storeGroups[product.store].items.push({ ...item, product });
      storeGroups[product.store].total += product.price * item.quantity;
    });
    
    // Sort stores alphabetically
    return Object.entries(storeGroups).sort((a, b) => a[0].localeCompare(b[0]));
  }, [basket, productsById]);

  const total = useMemo(() => {
    return basket.reduce((sum, item) => {
      const product = productsById[item.productId];
      return product ? sum + (product.price * item.quantity) : sum;
    }, 0);
  }, [basket, productsById]);

  const handleShare = async () => {
    const text = generateBasketText(basket, productsById);
    
    // Try native share first (works on mobile)
    if (navigator.share) {
      try {
        await navigator.share({
          title: 'Shopping Basket',
          text: text
        });
        return;
      } catch (err) {
        if (err.name === 'AbortError') return;
      }
    }
    
    // Fallback: show modal with text
    setBasketText(text);
    setShowShareModal(true);
  };

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(basketText);
      alert('✅ Copied to clipboard!');
      setShowShareModal(false);
    } catch (err) {
      // If clipboard fails, the text is already selected in the textarea
      alert('Please select all text (Cmd+A / Ctrl+A) and copy (Cmd+C / Ctrl+C)');
    }
  };

  const shareToWhatsApp = async () => {
    try {
      await navigator.clipboard.writeText(basketText);
      alert('✅ Text copied to clipboard!\n\nNow:\n1. Open WhatsApp on your Mac\n2. Select a contact or group\n3. Paste (Cmd+V) and send');
      setShowShareModal(false);
    } catch (err) {
      alert('Please copy the text manually and paste it into WhatsApp');
    }
  };

  const shareToMessages = async () => {
    try {
      await navigator.clipboard.writeText(basketText);
      alert('✅ Text copied to clipboard!\n\nNow:\n1. Open Messages on your Mac\n2. Select a contact\n3. Paste (Cmd+V) and send');
      setShowShareModal(false);
    } catch (err) {
      alert('Please copy the text manually and paste it into Messages');
    }
  };

  const shareToMail = async () => {
    try {
      await navigator.clipboard.writeText(basketText);
      alert('✅ Text copied to clipboard!\n\nNow:\n1. Open Mail on your Mac\n2. Create a new email\n3. Paste (Cmd+V) the basket list');
      setShowShareModal(false);
    } catch (err) {
      alert('Please copy the text manually and paste it into Mail');
    }
  };

  if (basket.length === 0) {
    return (
      <div className="text-center py-12">
        <ShoppingBag className="w-16 h-16 text-gray-300 mx-auto mb-4" />
        <p className="text-gray-600 mb-4">Your basket is empty</p>
      </div>
    );
  }

  return (
    <div>
      {/* Share Modal */}
      {showShareModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" onClick={() => setShowShareModal(false)}>
          <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col" onClick={(e) => e.stopPropagation()}>
            <div className="p-6 border-b flex items-center justify-between">
              <h2 className="text-2xl font-bold text-gray-800">Share Your Basket</h2>
              <button onClick={() => setShowShareModal(false)} className="p-2 hover:bg-gray-100 rounded-lg">
                <X className="w-6 h-6 text-gray-600" />
              </button>
            </div>
            
            {/* Quick Share Buttons */}
            <div className="p-6 border-b bg-gray-50">
              <p className="text-sm font-semibold text-gray-700 mb-3">Quick Share:</p>
              <div className="grid grid-cols-3 gap-3">
                <button
                  onClick={shareToWhatsApp}
                  className="flex flex-col items-center gap-2 p-4 bg-white border-2 border-green-500 rounded-lg hover:bg-green-50 transition-colors"
                >
                  <MessageCircle className="w-8 h-8 text-green-600" />
                  <span className="text-sm font-semibold text-gray-800">WhatsApp</span>
                </button>
                <button
                  onClick={shareToMessages}
                  className="flex flex-col items-center gap-2 p-4 bg-white border-2 border-blue-500 rounded-lg hover:bg-blue-50 transition-colors"
                >
                  <MessageSquare className="w-8 h-8 text-blue-600" />
                  <span className="text-sm font-semibold text-gray-800">Messages</span>
                </button>
                <button
                  onClick={shareToMail}
                  className="flex flex-col items-center gap-2 p-4 bg-white border-2 border-red-500 rounded-lg hover:bg-red-50 transition-colors"
                >
                  <Mail className="w-8 h-8 text-red-600" />
                  <span className="text-sm font-semibold text-gray-800">Mail</span>
                </button>
              </div>
            </div>
            
            <div className="p-6 overflow-y-auto flex-1">
              <p className="text-sm text-gray-600 mb-4">Or copy the text manually:</p>
              <textarea
                value={basketText}
                readOnly
                className="w-full h-64 p-4 border-2 border-gray-300 rounded-lg font-mono text-sm resize-none focus:outline-none focus:border-indigo-500"
                onClick={(e) => e.target.select()}
              />
            </div>

            <div className="p-6 border-t bg-gray-50 flex gap-3 justify-end">
              <button
                onClick={() => setShowShareModal(false)}
                className="px-6 py-3 text-gray-700 hover:bg-gray-200 rounded-lg font-semibold"
              >
                Close
              </button>
              <button
                onClick={copyToClipboard}
                className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 font-semibold"
              >
                Copy to Clipboard
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-bold">Your Basket</h2>
          <div className="flex gap-2 text-sm text-gray-600">
            <span>{basket.reduce((sum, item) => sum + item.quantity, 0)} items</span>
            <span>•</span>
            <span>{basketByStore.length} store{basketByStore.length !== 1 ? 's' : ''}</span>
          </div>
        </div>

        {/* Grouped by Store */}
        <div className="space-y-6">
          {basketByStore.map(([storeName, storeData]) => {
            const storeInfo = getStoreColor(storeName);
            return (
              <div key={storeName} className="border-2 border-gray-200 rounded-xl overflow-hidden">
                <div className={`${storeInfo.bg} ${storeInfo.text} px-4 py-3 flex items-center justify-between`}>
                  <h3 className="font-bold text-lg">{storeInfo.name}</h3>
                  <div className="text-right">
                    <p className="font-bold">{storeData.total.toFixed(2)} kr</p>
                    <p className="text-xs opacity-75">{storeData.items.length} item{storeData.items.length !== 1 ? 's' : ''}</p>
                  </div>
                </div>
                
                <div className="bg-white">
                  {storeData.items.map((item) => {
                    const product = item.product;
                    return (
                      <div key={item.productId} className="flex items-center gap-4 p-4 border-b last:border-b-0 hover:bg-gray-50">
                        <div className="w-16 h-16 md:w-20 md:h-20 flex-shrink-0">
                          {product.imageBase64 ? (
                            <img src={product.imageBase64} alt={product.title} className="w-full h-full object-cover rounded-lg" />
                          ) : (
                            <div className="w-full h-full bg-gray-200 rounded-lg"></div>
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <h3 className="font-semibold text-sm md:text-base truncate">{product.title}</h3>
                          <div className="flex items-center gap-2 mt-1 flex-wrap">
                            <OfferExpiry expiryDate={product.offerExpiryDate} remainingDays={product.remainingDays} />
                            <span className="text-xs text-gray-500">{product.category}</span>
                          </div>
                          <p className="text-xs md:text-sm text-gray-600 mt-1">
                            {product.price.toFixed(2)} kr × {item.quantity} = <span className="font-semibold text-indigo-600">{(product.price * item.quantity).toFixed(2)} kr</span>
                          </p>
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          <input
                            type="number"
                            min="1"
                            value={item.quantity}
                            onChange={(e) => onUpdateQuantity(item.productId, parseInt(e.target.value) || 1)}
                            className="w-16 md:w-20 px-2 md:px-3 py-2 border border-gray-300 rounded text-center"
                          />
                          <button onClick={() => onRemove(item.productId)} className="p-2 text-red-600 hover:bg-red-50 rounded-lg">
                            <Trash2 className="w-4 h-4 md:w-5 md:h-5" />
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="bg-white border-t-4 border-green-600 rounded-lg p-6 sticky bottom-0 shadow-lg">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <p className="text-sm text-gray-600">Grand Total</p>
            <p className="text-3xl md:text-4xl font-bold text-green-600">{total.toFixed(2)} kr</p>
            <p className="text-sm text-gray-500 mt-1">
              {basket.reduce((sum, item) => sum + item.quantity, 0)} items across {basketByStore.length} store{basketByStore.length !== 1 ? 's' : ''}
            </p>
          </div>
          <div className="flex gap-3 flex-wrap">
            <button onClick={onClear} className="px-4 md:px-6 py-3 text-red-600 hover:bg-red-50 rounded-lg font-semibold">
              Clear Basket
            </button>
            <button 
              onClick={handleShare}
              className="flex items-center gap-2 px-4 md:px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 font-semibold"
            >
              <Share2 className="w-5 h-5" />
              Share
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ==================== MAIN APP ====================
export default function App() {
  const [activeTab, setActiveTab] = useState('products');
  const { productsById, productIds, addProductsFromFile } = useProducts();
  const { recipes, currentRecipe, saveRecipe, loadRecipe, deleteRecipe, updateRecipeName, addIngredient, removeIngredient, updateIngredientQuantity, createNewRecipe } = useRecipes(productsById);
  const { basket, addToBasket, removeFromBasket, updateBasketQuantity, clearBasket, addRecipeToBasket } = useBasket();

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-3 md:p-6">
      <div className="max-w-6xl mx-auto">
        <div className="bg-white rounded-2xl shadow-xl p-4 md:p-8">
          <h1 className="text-2xl md:text-4xl font-bold text-gray-800 mb-2">Product Price Sorter</h1>
          <p className="text-sm md:text-base text-gray-600 mb-6">Compare products across 5 stores with smart pricing</p>

          <div className="flex gap-2 mb-6 border-b border-gray-200 overflow-x-auto">
            <button onClick={() => setActiveTab('products')} className={`flex items-center gap-2 px-4 py-3 font-semibold whitespace-nowrap ${activeTab === 'products' ? 'text-indigo-600 border-b-2 border-indigo-600' : 'text-gray-500'}`}>
              <ShoppingCart className="w-5 h-5" />
              <span className="hidden sm:inline">Products</span>
            </button>
            <button onClick={() => setActiveTab('offers')} className={`flex items-center gap-2 px-4 py-3 font-semibold whitespace-nowrap ${activeTab === 'offers' ? 'text-green-600 border-b-2 border-green-600' : 'text-gray-500'}`}>
              <TrendingDown className="w-5 h-5" />
              <span className="hidden sm:inline">Best Offers</span>
            </button>
            <button onClick={() => setActiveTab('recipes')} className={`flex items-center gap-2 px-4 py-3 font-semibold whitespace-nowrap ${activeTab === 'recipes' ? 'text-indigo-600 border-b-2 border-indigo-600' : 'text-gray-500'}`}>
              <ChefHat className="w-5 h-5" />
              <span className="hidden sm:inline">Recipes</span>
            </button>
            <button onClick={() => setActiveTab('basket')} className={`flex items-center gap-2 px-4 py-3 font-semibold whitespace-nowrap ${activeTab === 'basket' ? 'text-indigo-600 border-b-2 border-indigo-600' : 'text-gray-500'}`}>
              <ShoppingBag className="w-5 h-5" />
              <span className="hidden sm:inline">Basket</span>
              {basket.length > 0 && <span className="bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">{basket.length}</span>}
            </button>
          </div>

          {activeTab === 'products' && <ProductsTab productsById={productsById} productIds={productIds} onUpload={addProductsFromFile} onAddToBasket={addToBasket} />}
          {activeTab === 'offers' && <BestOffersTab productsById={productsById} onAddToBasket={addToBasket} />}
          {activeTab === 'recipes' && <RecipesTab productsById={productsById} productIds={productIds} recipes={recipes} currentRecipe={currentRecipe} onSave={saveRecipe} onLoad={loadRecipe} onDelete={deleteRecipe} onUpdateName={updateRecipeName} onAddIngredient={addIngredient} onRemoveIngredient={removeIngredient} onUpdateQuantity={updateIngredientQuantity} onCreateNew={createNewRecipe} onAddToBasket={addRecipeToBasket} />}
          {activeTab === 'basket' && <BasketTab basket={basket} productsById={productsById} onUpdateQuantity={updateBasketQuantity} onRemove={removeFromBasket} onClear={clearBasket} />}
        </div>
      </div>
    </div>
  );
}